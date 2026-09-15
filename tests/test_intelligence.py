"""Tests for the intelligence layer (validation logic only, no network)."""

import json

from competepulse.intelligence import _build_user_prompt, _validate_brief


VALID = json.dumps(
    {
        "executive_summary": "Competitor raised Pro pricing by $10 and shipped a new enterprise tier.",
        "pricing_shifts": [
            {"tier_name": "Pro", "change_type": "Price Increase", "details": "$49 -> $59"}
        ],
        "product_launches": ["New AI assistant feature"],
        "terms_updates": [],
        "key_takeaways": ["Expect churn pressure on price-sensitive segments."],
    }
)


def test_validate_brief_accepts_valid_schema():
    brief = _validate_brief(VALID)
    assert brief.pricing_shifts[0].tier_name == "Pro"
    assert brief.product_launches == ["New AI assistant feature"]


def test_validate_brief_normalizes_string_pricing_shifts():
    raw = json.loads(VALID)
    raw["pricing_shifts"] = ["Pro plan got more expensive"]
    brief = _validate_brief(json.dumps(raw))
    assert brief.pricing_shifts[0].tier_name == "Pro plan got more expensive"
    assert brief.pricing_shifts[0].change_type == "Change"


def test_validate_brief_rejects_missing_summary():
    raw = json.loads(VALID)
    del raw["executive_summary"]
    try:
        _validate_brief(json.dumps(raw))
    except Exception as exc:  # pydantic ValidationError
        assert "executive_summary" in str(exc)
    else:
        raise AssertionError("expected validation failure")


def test_user_prompt_includes_payload_and_schema_hint():
    prompt = _build_user_prompt('[{"page_type":"pricing"}]')
    assert "[{\"page_type\":\"pricing\"}]" in prompt
    assert "pricing_shifts" in prompt
    assert "executive_summary" in prompt
    assert "last 7 days" in prompt


def test_validate_brief_handles_markdown_fences():
    fenced = f"```json\n{VALID}\n```"
    brief = _validate_brief(fenced)
    assert brief.pricing_shifts[0].tier_name == "Pro"


def test_settings_nvidia_support():
    from competepulse.config import Settings
    s = Settings(_env_file=None, nvidia_api_key="nvapi-123")
    assert s.has_llm()
    assert s.effective_llm_api_key == "nvapi-123"
    assert s.effective_llm_base_url == "https://integrate.api.nvidia.com/v1"
