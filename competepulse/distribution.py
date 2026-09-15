"""Distribution layer: Slack webhook/file upload + SendGrid email.

Rules (autorules.md):
- Environment-based toggles: a channel is used only when its credentials exist.
- DISTRIBUTION_DRY_RUN=true bypasses all external calls and writes payloads
  to ./failed_deliveries/ for local inspection.
- Retries with exponential backoff; dead-letter file when all retries fail.
"""

import asyncio
import base64
import os
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .logging_utils import get_logger
from .state import ExecutiveBrief

logger = get_logger("competepulse.distribution")

FAILED_DELIVERY_DIR = Path("failed_deliveries")
MAX_RETRIES = 3


def summary_excerpt(analysis: ExecutiveBrief, limit: int = 280) -> str:
    text = analysis.executive_summary.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def _post_with_retry(url: str, *, headers: dict[str, str] | None = None, **kwargs: Any) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 — retry boundary
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(2**attempt)
    raise RuntimeError(f"POST {url} failed after {MAX_RETRIES} attempts: {last_exc}")


def _dead_letter(name: str, payload: dict[str, Any]) -> None:
    FAILED_DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    target = FAILED_DELIVERY_DIR / name
    if isinstance(payload.get("pdf_bytes"), bytes):
        pdf = payload.pop("pdf_bytes")
        target = target.with_suffix(".pdf")
        target.write_bytes(pdf)
        payload_path = FAILED_DELIVERY_DIR / f"{target.stem}_payload.json"
        payload_path.write_text(str(payload), encoding="utf-8")
    else:
        target.with_suffix(".json").write_text(str(payload), encoding="utf-8")
    logger.error("Delivery dead-lettered to %s", target)


def _dry_run_save(channel: str, name: str, payload: dict[str, Any]) -> None:
    out_dir = FAILED_DELIVERY_DIR / "dry_run" / channel
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = payload.pop("pdf_bytes", None)
    if pdf:
        (out_dir / f"{name}.pdf").write_bytes(pdf)
    (out_dir / f"{name}_payload.json").write_text(str(payload), encoding="utf-8")
    logger.info("[DRY RUN] %s payload saved to %s", channel, out_dir)


async def send_slack_notification(
    settings: Settings, pdf_path: Path, analysis: ExecutiveBrief
) -> bool:
    """Post a text alert via webhook, then upload the PDF via the Files API."""
    webhook_url = settings.slack_webhook_url
    bot_token = settings.slack_bot_token

    if settings.distribution_dry_run or (not webhook_url and not bot_token):
        _dry_run_save("slack", pdf_path.stem, {
            "event": "slack notification",
            "pdf": str(pdf_path),
            "excerpt": summary_excerpt(analysis),
            "pdf_bytes": pdf_path.read_bytes() if pdf_path.exists() else b"",
        })
        return True

    delivered = False
    text = (
        ":bar_chart: *Competepulse Weekly Brief*\n\n> "
        + summary_excerpt(analysis)
    )
    if webhook_url:
        await _post_with_retry(webhook_url, json={"text": text})
        delivered = True
        logger.info("Slack webhook alert posted")

    if bot_token and settings.slack_channel_id:
        # Slack's modern two-step upload: get an upload URL, then POST the file.
        async with httpx.AsyncClient(timeout=30) as client:
            init_response = await client.post(
                "https://slack.com/api/files.getUploadURLExternal",
                headers={"Authorization": f"Bearer {bot_token}"},
                data={"filename": pdf_path.name, "length": str(pdf_path.stat().st_size)},
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            if not init_data.get("ok"):
                raise RuntimeError(f"Slack upload URL request failed: {init_data.get('error')}")

            with pdf_path.open("rb") as f:
                upload_response = await client.post(
                    init_data["upload_url"],
                    files={"file": (pdf_path.name, f, "application/pdf")},
                )
            upload_response.raise_for_status()

            complete_response = await client.post(
                "https://slack.com/api/files.completeUploadExternal",
                headers={"Authorization": f"Bearer {bot_token}"},
                data={
                    "files": f'[{{"id":"{init_data["file_id"]}"}}]',
                    "channel_id": settings.slack_channel_id,
                    "initial_comment": "Here is this week's executive brief.",
                },
            )
            complete_json = complete_response.json()
            if not complete_json.get("ok"):
                logger.error("Slack file upload completion response: %s", str(complete_json))
                raise RuntimeError(f"Slack file upload completion failed: {complete_json.get('error')}")
        delivered = True
        logger.info("Slack PDF uploaded to channel %s", settings.slack_channel_id)

    return delivered


async def send_email_report(settings: Settings, pdf_path: Path, analysis: ExecutiveBrief) -> bool:
    """Send the PDF as a Base64 attachment via SendGrid."""
    recipients = settings.recipient_emails
    if settings.distribution_dry_run or not (settings.sendgrid_api_key and recipients):
        _dry_run_save("email", pdf_path.stem, {
            "event": "email report",
            "pdf": str(pdf_path),
            "recipients": recipients,
            "excerpt": summary_excerpt(analysis),
            "pdf_bytes": pdf_path.read_bytes() if pdf_path.exists() else b"",
        })
        return True

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Attachment,
        Disposition,
        FileContent,
        FileName,
        FileType,
        Mail,
    )

    encoded = base64.b64encode(pdf_path.read_bytes()).decode()
    message = Mail(
        from_email=settings.sender_email,
        to_emails=recipients,
        subject=f"Competepulse Weekly Brief — {pdf_path.stem}",
        html_content=(
            "<p><strong>Automated Weekly Competitor Briefing</strong></p>"
            f"<p>{summary_excerpt(analysis)}</p>"
        ),
    )
    message.attachment = Attachment(
        FileContent(encoded),
        FileName(pdf_path.name),
        FileType("application/pdf"),
        Disposition("attachment"),
    )

    def _send() -> Any:
        return SendGridAPIClient(settings.sendgrid_api_key).send(message)

    response = await asyncio.to_thread(_send)
    status = getattr(response, "status_code", 0)
    if status != 202:
        raise RuntimeError(f"SendGrid returned unexpected status {status}")
    logger.info("Email dispatched to %d recipient(s)", len(recipients))
    return True


async def distribute(settings: Settings, pdf_path: Path, analysis: ExecutiveBrief) -> list[str]:
    """Fan out to every configured channel; record which ones succeeded."""
    delivered_to: list[str] = []
    channels: list[tuple[str, Any]] = [
        ("slack", send_slack_notification(settings, pdf_path, analysis)),
        ("email", send_email_report(settings, pdf_path, analysis)),
    ]
    for name, task in channels:
        try:
            if await task:
                delivered_to.append(name)
        except Exception as exc:  # noqa: BLE001 — one channel failing must not kill the other
            logger.error("%s delivery failed: %s", name, exc)
            _dead_letter(pdf_path.stem, {"channel": name, "error": str(exc), "pdf": str(pdf_path)})
    return delivered_to
