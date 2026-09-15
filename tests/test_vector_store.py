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


def test_target_persistence_fallback(tmp_path):
    from competepulse.config import Settings
    from competepulse.vector_store import (
        delete_monitored_target,
        get_monitored_targets,
        save_monitored_target,
    )

    tfile = tmp_path / "targets.json"
    settings = Settings(targets_path=str(tfile), supabase_url="", supabase_key="")

    # Initially empty
    targets = get_monitored_targets(settings)
    assert len(targets) == 0

    # Save domain
    save_monitored_target(settings, "https://example.com/pricing", ["pricing", "terms"])
    targets = get_monitored_targets(settings)
    assert len(targets) == 1
    assert targets[0].domain == "example.com"
    assert [p.value for p in targets[0].page_types] == ["pricing", "terms"]

    # Upsert domain
    save_monitored_target(settings, "example.com", ["pricing", "changelog", "terms"])
    targets = get_monitored_targets(settings)
    assert len(targets) == 1
    assert [p.value for p in targets[0].page_types] == ["pricing", "changelog", "terms"]

    # Delete domain
    delete_monitored_target(settings, "example.com")
    targets = get_monitored_targets(settings)
    assert len(targets) == 0

