"""Tests for the ingestion layer (pure functions, no network)."""

from competepulse.ingestion import _extract_markdown, build_urls
from competepulse.state import PageType


def test_build_urls_maps_page_types_to_candidate_paths():
    urls = build_urls(
        "stripe.com",
        [PageType.PRICING, PageType.CHANGELOG, PageType.TERMS],
    )
    assert urls[PageType.PRICING] == ["https://stripe.com/pricing"]
    assert urls[PageType.CHANGELOG] == ["https://stripe.com/blog", "https://stripe.com/changelog"]
    assert urls[PageType.TERMS] == ["https://stripe.com/terms", "https://stripe.com/privacy"]


def test_extract_markdown_from_object_payload():
    class Payload:
        markdown = "# Hello"

    assert _extract_markdown(Payload()) == "# Hello"


def test_extract_markdown_from_dict_payload():
    assert _extract_markdown({"data": {"markdown": "# World"}}) == "# World"
    assert _extract_markdown({"markdown": "# Direct"}) == "# Direct"


def test_extract_markdown_returns_none_for_garbage():
    assert _extract_markdown(None) is None
    assert _extract_markdown({"data": {"markdown": "   "}}) is None
    assert _extract_markdown(42) is None


async def test_scrape_url_failure_preserves_page_type(monkeypatch):
    from competepulse.config import Settings
    from competepulse.ingestion import scrape_url

    settings = Settings(_env_file=None)

    async def _mock_direct_fetch(url):
        raise RuntimeError("network down")

    monkeypatch.setattr("competepulse.ingestion._scrape_direct_fetch", _mock_direct_fetch)

    res = await scrape_url(settings, "https://stripe.com/terms", PageType.TERMS)
    assert not res.ok
    assert res.page_type == PageType.TERMS
    assert "network down" in res.error
