"""Tests for the distribution layer (dry-run + dead-letter, no network)."""

import asyncio
import json
from pathlib import Path

from competepulse import distribution
from competepulse.config import Settings
from competepulse.state import ExecutiveBrief


def _settings(tmp_path: Path, **overrides) -> Settings:
    return Settings(
        reports_dir=tmp_path,
        distribution_dry_run=True,
        _env_file=None,
        **overrides,
    )


def test_dry_run_slack_saves_pdf_locally(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    brief = ExecutiveBrief(executive_summary="Test summary")

    delivered = asyncio.run(
        distribution.send_slack_notification(_settings(tmp_path), pdf, brief)
    )

    assert delivered is True
    saved = list((tmp_path / "failed_deliveries" / "dry_run" / "slack").glob("*.pdf"))
    assert saved and saved[0].read_bytes().startswith(b"%PDF")


def test_dry_run_email_saves_payload(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    brief = ExecutiveBrief(executive_summary="Test summary")

    delivered = asyncio.run(
        distribution.send_email_report(
            _settings(tmp_path, sendgrid_api_key="SG.test", recipient_emails=["a@b.com"]),
            pdf,
            brief,
        )
    )

    assert delivered is True
    payloads = list((tmp_path / "failed_deliveries" / "dry_run" / "email").glob("*payload.json"))
    assert payloads


def test_distribute_records_dead_letter_when_channel_fails(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = tmp_path / "brief.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    brief = ExecutiveBrief(executive_summary="Test summary")

    async def _boom(*args, **kwargs):
        raise RuntimeError("slack down")

    settings = Settings(_env_file=None, reports_dir=tmp_path, distribution_dry_run=False)
    monkeypatch.setattr(distribution, "send_slack_notification", _boom)
    monkeypatch.setattr(
        distribution,
        "send_email_report",
        lambda *a, **k: asyncio.sleep(0, result=True),
    )

    delivered = asyncio.run(distribution.distribute(settings, pdf, brief))
    assert delivered == ["email"]
    dead_letters = list((tmp_path / "failed_deliveries").glob("*.json"))
    assert dead_letters and "slack" in dead_letters[0].read_text()
