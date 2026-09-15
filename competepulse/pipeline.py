"""Pipeline orchestration: the linear, idempotent agent loop.

Flow (appflow.md): trigger -> state init -> async scraping -> vector diff ->
LLM synthesis -> PDF compilation -> distribution. Every stage appends to the
shared RunState; failures degrade gracefully instead of crashing the run.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from .chunking import prepare_chunks
from .config import PAGE_TYPES, Settings, get_settings
from .distribution import distribute
from .ingestion import scrape_domain
from .intelligence import AnalysisError, analyze_changes
from .logging_utils import get_logger
from .reporting import generate_executive_pdf
from .state import (
    ExecutiveBrief,
    PageDiff,
    PageType,
    RunState,
    ScrapeResult,
    Target,
)
from .vector_store import (
    build_json_diff_payload,
    detect_page_changes,
    domain_of,
    get_openai,
    get_supabase,
)

logger = get_logger("competepulse.pipeline")


def load_targets(settings: Settings) -> list[Target]:
    """Read the competitor target list (targets.json by default)."""
    path = Path(settings.targets_path)
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = []

    targets: list[Target] = []
    for item in raw:
        if isinstance(item, dict) and item.get("domain"):
            page_types = item.get("page_types") or list(PAGE_TYPES)
            targets.append(
                Target(
                    domain=item["domain"],
                    page_types=[PageType(pt) for pt in page_types],
                )
            )
    logger.info("Loaded %d target domain(s)", len(targets))
    return targets


def run_diff_stage(state: RunState, settings: Settings) -> None:
    """Vector-backed change detection for every successfully scraped page."""
    if not settings.has_vector_store() or not (settings.openai_api_key or settings.nvidia_api_key):
        logger.warning(
            "Supabase or embedding credentials missing — skipping vector diff stage "
            "(scraped snapshots will not be stored)."
        )
        # Still surface something to the LLM/report: treat all content as new.
        for result in state.scraped:
            if result.ok:
                state.diffs.append(_diff_without_store(result))
        return

    try:
        supabase = get_supabase(settings)
        openai_client = get_openai(settings)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not initialize vector store client: %s — skipping vector diff", exc)
        for result in state.scraped:
            if result.ok:
                state.diffs.append(_diff_without_store(result))
        return

    for result in state.scraped:
        if not result.ok:
            state.log_error(f"scrape failed: {result.url}: {result.error}")
            continue
        try:
            state.diffs.append(detect_page_changes(settings, supabase, openai_client, result))
        except Exception as exc:  # noqa: BLE001 — per-page isolation
            logger.error("Change detection failed for %s: %s", result.url, exc)
            state.log_error(f"change detection: {result.url}: {exc}")
            state.diffs.append(_diff_without_store(result))


def _diff_without_store(result: ScrapeResult) -> PageDiff:
    """Degraded mode: mark the whole page as new content (no history)."""
    assert result.content is not None
    chunks = prepare_chunks(result.content)
    page_diff = PageDiff(page_type=result.page_type, url=result.url)
    from .state import ChangeType, ChunkDiff

    for chunk in chunks[:3]:
        page_diff.diffs.append(
            ChunkDiff(
                page_type=result.page_type,
                url=result.url,
                change_type=ChangeType.NEW_CONTENT,
                current_chunk=chunk,
            )
        )
    return page_diff


def run_analysis_stage(state: RunState, settings: Settings) -> None:
    """LLM synthesis with deterministic fallback (intellirules Rule 4)."""
    payload = build_json_diff_payload(state.diffs)
    changed_pages = [page for page in state.diffs if page.changed_chunks]

    if not changed_pages:
        logger.info("No changes detected — skipping LLM analysis")
        state.analysis = ExecutiveBrief(
            executive_summary=f"No significant changes detected on {state.domain} this week.",
            key_takeaways=["All tracked pages are semantically stable."],
        )
        return

    if not settings.has_llm():
        logger.warning("OPENAI_API_KEY missing — using deterministic fallback brief")
        state.analysis = ExecutiveBrief.fallback_from_diffs(state.domain, state.diffs)
        return

    try:
        state.analysis = analyze_changes(settings, payload)
    except (AnalysisError, Exception) as exc:  # noqa: BLE001 — fallback path
        logger.error("LLM analysis failed: %s — using deterministic fallback", exc)
        state.log_error(f"llm analysis: {exc}")
        state.analysis = ExecutiveBrief.fallback_from_diffs(state.domain, state.diffs)


def run_reporting_stage(state: RunState, settings: Settings) -> None:
    assert state.analysis is not None
    state.pdf_path = str(
        generate_executive_pdf(
            state.analysis,
            state.domain,
            output_dir=settings.reports_dir,
            generated_at=state.run_at,
        )
    )


async def run_distribution_stage(state: RunState, settings: Settings) -> None:
    assert state.pdf_path is not None and state.analysis is not None
    state.delivered_to = await distribute(settings, Path(state.pdf_path), state.analysis)


async def run_domain_pipeline(settings: Settings, target: Target) -> RunState:
    """Execute the full pipeline for one competitor domain."""
    state = RunState(domain=target.domain)
    logger.info("=== Competepulse run: %s ===", target.domain)

    # 1. Ingestion (concurrent)
    state.scraped = await scrape_domain(settings, target.domain, target.page_types)

    # 2. Vector diff (sync stage run in a thread to keep the loop responsive)
    await asyncio.to_thread(run_diff_stage, state, settings)

    # 3. LLM analysis
    await asyncio.to_thread(run_analysis_stage, state, settings)

    # 4. PDF
    await asyncio.to_thread(run_reporting_stage, state, settings)

    # 5. Distribution
    await run_distribution_stage(state, settings)

    logger.info(
        "Run complete for %s: pdf=%s delivered=%s errors=%d",
        target.domain,
        state.pdf_path,
        state.delivered_to,
        len(state.errors),
    )
    return state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Competepulse: Autonomous Competitor Intelligence Agent")
    parser.add_argument(
        "-d", "--domain",
        type=str,
        help="Target competitor domain to check on-demand (e.g. stripe.com or linear.app)",
    )
    parser.add_argument(
        "-p", "--pages",
        type=str,
        default="pricing,changelog,terms",
        help="Comma-separated page types to crawl: pricing, changelog, blog, terms (default: pricing,changelog,terms)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: `python main.py` or `python main.py --domain <domain>`."""
    args = parse_args(argv)
    settings = get_settings()

    if args.domain:
        raw_pages = [p.strip() for p in args.pages.split(",") if p.strip()]
        page_types = [PageType(pt) for pt in raw_pages if pt in [e.value for e in PageType]] or [
            PageType.PRICING,
            PageType.CHANGELOG,
            PageType.TERMS,
        ]
        targets = [Target(domain=args.domain, page_types=page_types)]
        logger.info("Running on-demand check for target domain: %s (pages: %s)", args.domain, [pt.value for pt in page_types])
    else:
        targets = load_targets(settings)

    if not targets:
        logger.info("No competitor domains registered in targets.json. Add targets via dashboard or CLI to run pipeline.")
        return 0

    exit_code = 0

    for target in targets:
        try:
            state = asyncio.run(run_domain_pipeline(settings, target))
            if state.errors and not state.pdf_path:
                exit_code = max(exit_code, 1)
        except Exception as exc:  # noqa: BLE001 — one domain must not kill the rest
            logger.error("Pipeline failed for %s: %s", target.domain, exc)
            exit_code = 2

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
