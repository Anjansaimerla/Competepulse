"""Tests for the semantic chunking engine."""

from competepulse.chunking import chunk_markdown, prepare_chunks, strip_boilerplate


def test_strip_boilerplate_removes_cookie_and_footer_noise():
    markdown = """# Pricing

Pro plan costs $49/month.

Sign up for a free trial

All rights reserved. Copyright © 2026 Competitor Inc.

Cookie banner: we use cookies to improve your experience.
"""
    cleaned = strip_boilerplate(markdown)
    assert "Pro plan costs" in cleaned
    assert "Sign up" not in cleaned
    assert "All rights reserved" not in cleaned
    assert "Cookie banner" not in cleaned


def test_chunk_markdown_respects_max_size_and_splits_headings():
    markdown = "\n\n".join(
        f"# Section {i}\n\n" + ("word " * 250) for i in range(3)  # ~1250 chars each
    )
    chunks = chunk_markdown(markdown, max_chars=800, overlap_chars=100)
    assert len(chunks) > 3  # oversized sections get sliding-window split
    for chunk in chunks:
        assert len(chunk) <= 800


def test_prepare_chunks_drops_empty_input():
    assert prepare_chunks("") == []
    assert prepare_chunks("   \n\n  ") == []


def test_prepare_chunks_keeps_semantic_content():
    markdown = "# Terms of Service\n\nWe may update these terms at any time.\n\n## Liability\n\nLiability is capped at fees paid."
    chunks = prepare_chunks(markdown)
    assert any("terms" in c.lower() for c in chunks)
    assert any("Liability" in c for c in chunks)
