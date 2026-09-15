"""Tests for pipeline state models and the fallback brief builder."""

from competepulse.state import (
    ChangeType,
    ChunkDiff,
    ExecutiveBrief,
    PageDiff,
    PageType,
    week_of_today,
)


def _page(page_type: PageType, url: str, change: ChangeType) -> PageDiff:
    return PageDiff(
        page_type=page_type,
        url=url,
        diffs=[
            ChunkDiff(
                page_type=page_type,
                url=url,
                change_type=change,
                current_chunk="Pro plan now $59/month (was $49).",
                previous_chunk="Pro plan is $49/month." if change == ChangeType.SEMANTIC_SHIFT else None,
                similarity=0.71 if change == ChangeType.SEMANTIC_SHIFT else None,
            )
        ],
    )


def test_week_of_today_is_a_monday():
    assert week_of_today().weekday() == 0


def test_fallback_categorizes_by_page_type():
    diffs = [
        _page(PageType.PRICING, "https://x.com/pricing", ChangeType.SEMANTIC_SHIFT),
        _page(PageType.CHANGELOG, "https://x.com/blog", ChangeType.NEW_CONTENT),
        _page(PageType.TERMS, "https://x.com/terms", ChangeType.SEMANTIC_SHIFT),
    ]
    brief = ExecutiveBrief.fallback_from_diffs("x.com", diffs)
    assert len(brief.pricing_shifts) == 1
    assert len(brief.product_launches) == 1
    assert len(brief.terms_updates) == 1
    assert "fallback" in brief.executive_summary.lower()


def test_fallback_reports_no_changes():
    brief = ExecutiveBrief.fallback_from_diffs("x.com", [])
    assert "No significant changes" in brief.executive_summary
    assert brief.pricing_shifts == []


def test_parse_args_domain_flag():
    from competepulse.pipeline import parse_args
    args = parse_args(["--domain", "linear.app", "--pages", "pricing,terms"])
    assert args.domain == "linear.app"
    assert args.pages == "pricing,terms"
