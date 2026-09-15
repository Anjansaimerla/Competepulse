"""Tests for the ReportLab PDF engine (real compilation, no network)."""

from datetime import datetime
from pathlib import Path

from competepulse.reporting import generate_executive_pdf
from competepulse.state import ExecutiveBrief, PricingShift


def test_generate_executive_pdf_creates_valid_file(tmp_path: Path):
    brief = ExecutiveBrief(
        executive_summary="Pro pricing rose $10; a new enterprise tier appeared; terms updated re: data retention.",
        pricing_shifts=[
            PricingShift(tier_name="Pro", change_type="Price Increase", details="$49 -> $59 / month")
        ],
        product_launches=["Shipped an AI Copilot beta"],
        terms_updates=["Data retention window shortened from 24 to 12 months"],
        key_takeaways=["Prepare win-back campaign for price-sensitive accounts"],
    )

    path = generate_executive_pdf(
        brief, "example.com", output_dir=tmp_path, generated_at=datetime(2026, 9, 14, 6, 0)
    )

    assert path.exists()
    assert path.name == "competepulse_brief_example.com_2026-09-14.pdf"
    data = path.read_bytes()
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
    # Document metadata (uncompressed in the Info dict) carries the brand name
    assert b"Competepulse" in data


def test_generate_executive_pdf_handles_empty_brief(tmp_path: Path):
    brief = ExecutiveBrief(executive_summary="No significant changes detected this week.")
    path = generate_executive_pdf(brief, "calm.com", output_dir=tmp_path)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")
