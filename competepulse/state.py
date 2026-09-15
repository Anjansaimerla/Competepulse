"""Pipeline state models (Pydantic) shared across every stage.

Implements the Immutable State Pattern from sysrules.md: each run builds one
`RunState` and stages transform it functionally — no global side effects.
Also defines the strict LLM output schema enforced before PDF generation
(Intelligent LLM Orchestration, Rule 2: no free-form text).
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def week_of_today() -> date:
    """Monday of the current week — the idempotency bucket for snapshots."""
    today = date.today()
    return date.fromordinal(today.toordinal() - today.weekday())


class ChangeType(str, Enum):
    NEW_CONTENT = "new_content"          # no historical match found
    SEMANTIC_SHIFT = "semantic_shift"    # matched but below threshold
    UNCHANGED = "unchanged"              # at/above threshold


class PageType(str, Enum):
    PRICING = "pricing"
    CHANGELOG = "changelog"
    BLOG = "blog"
    TERMS = "terms"


class ScrapeResult(BaseModel):
    page_type: PageType
    url: str
    content: str | None = None          # markdown, None when scraping failed
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.content is not None and bool(self.content.strip())


class ChunkDiff(BaseModel):
    page_type: PageType
    url: str
    change_type: ChangeType
    current_chunk: str
    previous_chunk: str | None = None
    similarity: float | None = None


class PageDiff(BaseModel):
    page_type: PageType
    url: str
    diffs: list[ChunkDiff] = Field(default_factory=list)

    @property
    def changed_chunks(self) -> list[ChunkDiff]:
        return [d for d in self.diffs if d.change_type != ChangeType.UNCHANGED]


class Target(BaseModel):
    domain: str
    page_types: list[PageType] = Field(
        default_factory=lambda: [PageType.PRICING, PageType.CHANGELOG, PageType.TERMS]
    )


class RunState(BaseModel):
    """The single state container threaded through the whole pipeline."""

    domain: str
    run_at: datetime = Field(default_factory=utc_now)
    week_of: date = Field(default_factory=week_of_today)
    scraped: list[ScrapeResult] = Field(default_factory=list)
    diffs: list[PageDiff] = Field(default_factory=list)
    analysis: "ExecutiveBrief | None" = None
    pdf_path: str | None = None
    delivered_to: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    def log_error(self, message: str) -> None:
        self.errors.append(message)


class PricingShift(BaseModel):
    tier_name: str = Field(description="Name of the pricing tier, e.g. Pro, Enterprise")
    change_type: str = Field(
        description="Price Increase, Price Decrease, Feature Added, or Feature Removed"
    )
    details: str = Field(description="Detailed explanation of what changed")


class ExecutiveBrief(BaseModel):
    """Strict schema enforced on LLM output before the PDF engine runs."""

    executive_summary: str = Field(
        description="High-level 3-sentence summary of all competitor movements."
    )
    pricing_shifts: list[PricingShift] = Field(default_factory=list)
    product_launches: list[str] = Field(default_factory=list)
    terms_updates: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    raw: dict[str, Any] | None = None  # reserved, never rendered

    @classmethod
    def fallback_from_diffs(cls, domain: str, diffs: list[PageDiff]) -> "ExecutiveBrief":
        """Deterministic summary used when the LLM fails (intellirules Rule 4)."""
        pricing: list[PricingShift] = []
        launches: list[str] = []
        terms: list[str] = []
        changed_pages: list[str] = []

        for page in diffs:
            changed = page.changed_chunks
            if not changed:
                continue
            changed_pages.append(page.page_type.value)
            snippet = changed[0].current_chunk[:300].replace("\n", " ")
            if page.page_type == PageType.PRICING:
                pricing.append(
                    PricingShift(
                        tier_name="Unspecified tier",
                        change_type="Detected Change",
                        details=f"Semantic change detected on {page.url}: {snippet}...",
                    )
                )
            elif page.page_type in (PageType.CHANGELOG, PageType.BLOG):
                launches.append(f"Update detected on {page.url}: {snippet}...")
            else:
                terms.append(f"Policy change detected on {page.url}: {snippet}...")

        if not changed_pages:
            summary = f"No significant changes detected on {domain} this week."
        else:
            summary = (
                f"Automatic fallback summary: {len(changed_pages)} tracked page(s) of "
                f"{domain} showed semantic changes ({', '.join(sorted(set(changed_pages)))}). "
                "LLM synthesis was unavailable; review the flagged diffs manually."
            )

        return cls(
            executive_summary=summary,
            pricing_shifts=pricing,
            product_launches=launches,
            terms_updates=terms,
            key_takeaways=["Generated via deterministic fallback — no LLM analysis available."],
        )


RunState.model_rebuild()
