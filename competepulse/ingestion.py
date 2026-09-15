"""Ingestion layer: async multi-page scraping via Firecrawl.

Rules (multirules.md):
- Never crawl a single competitor's pages sequentially — asyncio.gather.
- Raw HTML never leaves this layer: only clean Markdown is returned.
- Graceful degradation: a missing/broken page logs a non-fatal warning and
  the run continues with the remaining pages.
- Every fetch is wrapped with a timeout and a single automatic retry.
"""

import asyncio
from typing import Any

import httpx

from .config import TARGET_ENDPOINTS, Settings
from .logging_utils import get_logger
from .state import PageType, ScrapeResult

logger = get_logger("competepulse.ingestion")

REQUEST_TIMEOUT_SECONDS = 15
SINGLE_RETRY = 1

FALLBACK_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def build_urls(domain: str, page_types: list[PageType]) -> dict[PageType, list[str]]:
    """Map each requested page type to its candidate endpoint paths."""
    urls: dict[PageType, list[str]] = {}
    for page_type in page_types:
        paths = TARGET_ENDPOINTS.get(page_type.value, [f"/{page_type.value}"])
        urls[page_type] = [f"https://{domain}{path}" for path in paths]
    return urls


def _extract_markdown(payload: Any) -> str | None:
    """Firecrawl SDK versions return objects or dicts; normalize both."""
    if payload is None:
        return None
    markdown = getattr(payload, "markdown", None)
    if isinstance(markdown, str) and markdown.strip():
        return markdown
    if isinstance(payload, dict):
        data = payload.get("data") or payload
        markdown = data.get("markdown") if isinstance(data, dict) else None
        if isinstance(markdown, str) and markdown.strip():
            return markdown
    return None


async def _scrape_firecrawl(settings: Settings, url: str) -> str | None:
    """Primary scraper: Firecrawl managed API (JS rendering + anti-bot)."""
    from firecrawl import FirecrawlApp  # imported lazily so tests run without it

    app = FirecrawlApp(api_key=settings.firecrawl_api_key)

    def _call() -> Any:
        try:
            if hasattr(app, "scrape"):
                return app.scrape(url, formats=["markdown"], timeout=30000)
            return app.scrape_url(url, formats=["markdown"], timeout=30000)
        except TypeError:
            try:
                return app.scrape_url(url, params={"formats": ["markdown"], "timeout": 30000})
            except Exception:
                return app.scrape_url(url)

    return _extract_markdown(await asyncio.to_thread(_call))


async def _scrape_direct_fetch(url: str) -> str | None:
    """Fallback scraper: plain async HTTP GET + naive HTML-to-text.

    Multirules.md fallback protocol — used when Firecrawl hits a rate limit
    or 403. Not as robust as Playwright, but dependency-free and often
    sufficient for static marketing pages.
    """
    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": FALLBACK_UA},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text

    import re

    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip() or None


async def scrape_url(settings: Settings, url: str, page_type: PageType) -> ScrapeResult:
    """Scrape one URL with timeout + single retry, then fallback scraper."""
    exceptions: list[str] = []
    for attempt in range(SINGLE_RETRY + 1):
        try:
            if settings.has_scraper():
                markdown = await asyncio.wait_for(
                    _scrape_firecrawl(settings, url), timeout=REQUEST_TIMEOUT_SECONDS + 15
                )
            else:
                markdown = None
            if markdown:
                return ScrapeResult(page_type=page_type, url=url, content=markdown)
            break  # no scraper configured or empty result -> try fallback
        except Exception as exc:  # noqa: BLE001 — boundary must not crash the run
            exceptions.append(f"firecrawl[{attempt}]: {type(exc).__name__}: {exc}")
            if attempt < SINGLE_RETRY:
                await asyncio.sleep(2 * (attempt + 1))

    # Fallback protocol (multirules.md §2)
    try:
        markdown = await _scrape_direct_fetch(url)
        if markdown:
            return ScrapeResult(page_type=page_type, url=url, content=markdown)
        exceptions.append("fallback: empty content")
    except Exception as exc:  # noqa: BLE001
        exceptions.append(f"fallback: {type(exc).__name__}: {exc}")

    detail = "; ".join(exceptions)
    logger.warning("Scrape failed for %s — %s", url, detail)
    return ScrapeResult(page_type=page_type, url=url, error=detail)


async def scrape_domain(
    settings: Settings, domain: str, page_types: list[PageType]
) -> list[ScrapeResult]:
    """Concurrently scrape every candidate URL for one competitor domain.

    The first successful URL per page type wins; failures degrade gracefully.
    """
    url_map = build_urls(domain, page_types)
    tasks: list[asyncio.Task[ScrapeResult]] = []
    task_keys: list[tuple[PageType, str]] = []

    async def _fetch(page_type: PageType, url: str) -> ScrapeResult:
        return await scrape_url(settings, url, page_type)

    for page_type, urls in url_map.items():
        for url in urls:
            task_keys.append((page_type, url))
            tasks.append(asyncio.create_task(_fetch(page_type, url)))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    best: dict[PageType, ScrapeResult] = {}
    for (page_type, url), outcome in zip(task_keys, results, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning("Task crashed for %s: %s", url, outcome)
            continue
        if outcome.ok and (page_type not in best or not best[page_type].ok):
            best[page_type] = outcome
        elif page_type not in best:
            best[page_type] = outcome

    ordered = [best[pt] for pt in url_map if pt in best]
    ok_count = sum(1 for r in ordered if r.ok)
    logger.info("Scraped %s: %d/%d page types succeeded", domain, ok_count, len(url_map))
    return ordered
