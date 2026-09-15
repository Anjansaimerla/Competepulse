"""LLM intelligence layer: turns flagged semantic diffs into structured insights.

Rules (intellirules.md):
- The LLM is a stateless reasoning engine; the orchestrator owns all state.
- Strict structured output validated against the ExecutiveBrief schema.
- Retry on invalid JSON with error feedback, lower temperature on retries.
- Deterministic fallback summary if every attempt fails (handled by caller).
"""

import json
from typing import Any

from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings
from .logging_utils import get_logger
from .state import ExecutiveBrief

logger = get_logger("competepulse.intelligence")

SYSTEM_PROMPT = """You are an elite enterprise market intelligence analyst. \
Your job is to review competitor website changes and write an objective, \
high-impact executive brief. You will be provided with JSON records containing \
historical text snippets and new text snippets scraped one week apart. \
Ignore superficial layout changes, minor typos, rephrasing, or CSS updates. \
Focus exclusively on strategic shifts: pricing tier modifications, feature \
gating changes, new product launches, and legal/terms alterations. \
If nothing meaningful changed, say so explicitly. Never invent changes that \
are not supported by the provided content."""


class AnalysisError(Exception):
    """Raised when the LLM cannot produce schema-valid output."""


def _build_user_prompt(diff_payload: str) -> str:
    return (
        "Below are the semantic shifts detected on the target competitor's pages "
        "over the last 7 days (cosine similarity < 0.85 against historical chunks).\n\n"
        f"{diff_payload}\n\n"
        "Produce an executive brief as JSON with exactly these keys:\n"
        '{"executive_summary": string (3 sentences), '
        '"pricing_shifts": [{"tier_name": string, "change_type": string, "details": string}], '
        '"product_launches": [string], "terms_updates": [string], "key_takeaways": [string]}\n'
        "Use empty arrays when a category has no meaningful changes."
    )


def _extract_message_text(response: Any) -> str:
    message = response.choices[0].message
    content = getattr(message, "content", None)
    if content:
        return content
    reasoning = getattr(message, "reasoning", None) or getattr(message, "reasoning_content", None)
    if reasoning:
        logger.debug("Model reasoning present")
        return str(reasoning)
    return ""


def _validate_brief(raw_json: str) -> ExecutiveBrief:
    cleaned = raw_json.strip()
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()

    if "```" in cleaned:
        import re

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        else:
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

    data = json.loads(cleaned)
    if isinstance(data.get("pricing_shifts"), list):
        data["pricing_shifts"] = [
            item if isinstance(item, dict) else {"tier_name": str(item), "change_type": "Change", "details": str(item)}
            for item in data["pricing_shifts"]
        ]
    return ExecutiveBrief.model_validate(data)


@retry(
    retry=retry_if_exception_type(AnalysisError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
def analyze_changes(settings: Settings, diff_payload: str) -> ExecutiveBrief:
    """Call the LLM with JSON mode and validate against ExecutiveBrief."""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.effective_llm_api_key,
        base_url=settings.effective_llm_base_url,
        timeout=45.0,
    )
    temperature = 0.2

    last_error: Exception | None = None
    for attempt in range(2):
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(diff_payload)},
        ]
        if last_error is not None:
            messages.append(
                {
                    "role": "user",
                    "content": f"Your previous output failed schema validation: {last_error}. "
                    "Correct the formatting and return valid JSON matching the schema exactly.",
                }
            )
            temperature = 0.0

        try:
            try:
                response = client.chat.completions.create(
                    model=settings.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                    timeout=30.0,
                )
            except Exception:
                # Some NIM/custom endpoints don't support response_format or timeout
                response = client.chat.completions.create(
                    model=settings.model_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048,
                    timeout=30.0,
                )

            brief = _validate_brief(_extract_message_text(response))
            logger.info(
                "LLM analysis complete: %d pricing shift(s), %d launch(es), %d term update(s)",
                len(brief.pricing_shifts),
                len(brief.product_launches),
                len(brief.terms_updates),
            )
            return brief
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError, Exception) as exc:
            last_error = exc
            logger.warning("LLM output validation failed (attempt %d): %s", attempt + 1, exc)

    raise AnalysisError(str(last_error))
