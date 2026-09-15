"""Tests for vector_store helpers (no database required)."""

import json

from competepulse.state import ChangeType, ChunkDiff, PageDiff, PageType
from competepulse.vector_store import build_json_diff_payload, content_hash, domain_of


def test_domain_of_extracts_bare_domain():
    assert domain_of("https://stripe.com/pricing") == "stripe.com"
    assert domain_of("https://www.Notion.com/blog ") == "www.notion.com"


def test_content_hash_is_stable():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")


def test_build_json_diff_payload_only_includes_changed_chunks():
    page = PageDiff(
        page_type=PageType.PRICING,
        url="https://x.com/pricing",
        diffs=[
            ChunkDiff(
                page_type=PageType.PRICING,
                url="https://x.com/pricing",
                change_type=ChangeType.UNCHANGED,
                current_chunk="same old",
            ),
            ChunkDiff(
                page_type=PageType.PRICING,
                url="https://x.com/pricing",
                change_type=ChangeType.SEMANTIC_SHIFT,
                current_chunk="Pro is now $59",
                previous_chunk="Pro is $49",
                similarity=0.72,
            ),
        ],
    )
    payload = json.loads(build_json_diff_payload([page]))
    assert len(payload) == 1
    assert payload[0]["change_type"] == "semantic_shift"
    assert payload[0]["previous_content"] == "Pro is $49"
    assert payload[0]["current_content"] == "Pro is now $59"
