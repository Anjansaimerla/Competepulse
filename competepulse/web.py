"""Async Web Dashboard backend for Competepulse using aiohttp.web.

Provides REST endpoints for:
- Monitoring integration health (Firecrawl, Supabase, NVIDIA NIM, Slack)
- Competitor target management (list, add, update, delete in targets.json)
- On-demand pipeline triggering with live progress and log capture
- Browsing, viewing, and downloading executive PDF briefs
"""

import asyncio
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web

from .config import PAGE_TYPES, Settings, get_settings
from .logging_utils import get_logger
from .pipeline import load_targets, run_domain_pipeline
from .state import PageType, Target

logger = get_logger("competepulse.web")

STATIC_DIR = Path(__file__).resolve().parent / "static"


class PipelineRunner:
    """Manages background agent execution and live log streaming."""

    def __init__(self) -> None:
        self.is_running = False
        self.current_domain: str | None = None
        self.current_step: str = "idle"
        self.logs: list[dict[str, str]] = []
        self.last_run_time: str | None = None
        self.last_status: str | None = None
        self._lock = asyncio.Lock()

    def add_log(self, level: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logs.append({"timestamp": timestamp, "level": level, "message": message})
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    async def execute(self, settings: Settings, targets: list[Target]) -> dict[str, Any]:
        async with self._lock:
            if self.is_running:
                return {"error": "A pipeline run is already in progress."}
            self.is_running = True
            self.logs = []
            self.last_status = "running"

        try:
            self.add_log("INFO", f"Starting Competepulse run for {len(targets)} target domain(s)")
            results = []
            for target in targets:
                self.current_domain = target.domain
                self.current_step = f"Ingesting & Analyzing {target.domain}"
                self.add_log("INFO", f"=== Ingesting competitor: {target.domain} ===")

                state = await run_domain_pipeline(settings, target)
                results.append({
                    "domain": target.domain,
                    "pdf_path": state.pdf_path,
                    "delivered_to": state.delivered_to,
                    "errors": state.errors,
                    "executive_summary": state.analysis.executive_summary if state.analysis else None,
                })
                self.add_log("INFO", f"Finished {target.domain}: PDF={state.pdf_path} Delivered={state.delivered_to}")

            self.current_step = "Complete"
            self.last_status = "success"
            self.last_run_time = datetime.now(timezone.utc).isoformat()
            self.add_log("INFO", "Pipeline execution finished successfully.")
            return {"status": "success", "results": results}
        except Exception as exc:
            self.last_status = "error"
            self.add_log("ERROR", f"Pipeline encountered error: {exc}")
            logger.exception("Pipeline runner error: %s", exc)
            return {"status": "error", "error": str(exc)}
        finally:
            self.is_running = False
            self.current_domain = None


runner = PipelineRunner()


# --- REST Handlers ---


async def handle_index(request: web.Request) -> web.Response:
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return web.Response(text="Competepulse Web Dashboard: static/index.html not found.", content_type="text/plain")
    return web.FileResponse(index_file)


async def handle_status(request: web.Request) -> web.Response:
    settings = get_settings()
    reports_dir = settings.reports_dir
    reports_count = len(list(reports_dir.glob("*.pdf"))) if reports_dir.exists() else 0
    targets = load_targets(settings)

    status_payload = {
        "integrations": {
            "firecrawl": bool(settings.firecrawl_api_key),
            "supabase": bool(settings.supabase_url and settings.supabase_key),
            "nvidia_nim": bool(settings.nvidia_api_key),
            "openai": bool(settings.openai_api_key),
            "slack": bool(settings.slack_webhook_url or (settings.slack_bot_token and settings.slack_channel_id)),
            "sendgrid": bool(settings.sendgrid_api_key and settings.recipient_emails),
        },
        "config": {
            "model_name": settings.model_name,
            "embedding_model": settings.embedding_model,
            "similarity_threshold": settings.similarity_threshold,
            "dry_run": settings.distribution_dry_run,
        },
        "stats": {
            "monitored_domains_count": len(targets),
            "reports_count": reports_count,
            "last_run_time": runner.last_run_time,
            "is_running": runner.is_running,
        },
    }
    return web.json_response(status_payload)


async def handle_get_targets(request: web.Request) -> web.Response:
    settings = get_settings()
    targets = load_targets(settings)
    return web.json_response([
        {"domain": t.domain, "page_types": [pt.value for pt in t.page_types]}
        for t in targets
    ])


async def handle_add_target(request: web.Request) -> web.Response:
    settings = get_settings()
    data = None
    try:
        data = await request.json()
    except Exception:
        try:
            raw = await request.read()
            if raw:
                data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = None

    if not isinstance(data, dict):
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    domain = str(data.get("domain", "")).strip().lower()
    if not domain:
        return web.json_response({"error": "Domain is required"}, status=400)

    # Clean domain if full URL was pasted
    domain = domain.split("//")[-1].split("/")[0]

    raw_page_types = data.get("page_types") or ["pricing", "changelog", "terms"]
    valid_pages = [p for p in raw_page_types if p in PAGE_TYPES]
    if not valid_pages:
        valid_pages = ["pricing", "changelog", "terms"]

    targets_path = Path(settings.targets_path)
    existing_targets = []
    if targets_path.exists():
        try:
            existing_targets = json.loads(targets_path.read_text(encoding="utf-8"))
        except Exception:
            existing_targets = []

    # Update if exists, or append
    updated = False
    for item in existing_targets:
        if item.get("domain") == domain:
            item["page_types"] = valid_pages
            updated = True
            break
    if not updated:
        existing_targets.append({"domain": domain, "page_types": valid_pages})

    targets_path.write_text(json.dumps(existing_targets, indent=2), encoding="utf-8")
    return web.json_response({"status": "success", "domain": domain, "page_types": valid_pages})


async def handle_delete_target(request: web.Request) -> web.Response:
    settings = get_settings()
    domain = request.match_info.get("domain", "").strip().lower()
    targets_path = Path(settings.targets_path)

    if not targets_path.exists():
        return web.json_response({"error": "Targets file not found"}, status=404)

    try:
        existing_targets = json.loads(targets_path.read_text(encoding="utf-8"))
    except Exception:
        existing_targets = []

    filtered = [item for item in existing_targets if item.get("domain") != domain]
    targets_path.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    return web.json_response({"status": "deleted", "domain": domain})


async def handle_trigger_run(request: web.Request) -> web.Response:
    settings = get_settings()
    if runner.is_running:
        return web.json_response({"error": "A pipeline run is already in progress"}, status=409)

    data = {}
    try:
        data = await request.json()
    except Exception:
        pass

    target_domain = data.get("domain")
    if target_domain:
        raw_pages = data.get("page_types") or ["pricing", "changelog", "terms"]
        page_types = [PageType(pt) for pt in raw_pages if pt in [e.value for e in PageType]] or [
            PageType.PRICING, PageType.CHANGELOG, PageType.TERMS
        ]
        targets = [Target(domain=target_domain, page_types=page_types)]
    else:
        targets = load_targets(settings)

    if not targets:
        return web.json_response({"error": "No competitor targets configured to run."}, status=400)

    # Launch task in background so HTTP response is immediate
    asyncio.create_task(runner.execute(settings, targets))
    return web.json_response({"status": "started", "target_count": len(targets)})


async def handle_run_status(request: web.Request) -> web.Response:
    return web.json_response({
        "is_running": runner.is_running,
        "current_domain": runner.current_domain,
        "current_step": runner.current_step,
        "last_status": runner.last_status,
        "last_run_time": runner.last_run_time,
        "logs": runner.logs,
    })


async def handle_list_reports(request: web.Request) -> web.Response:
    settings = get_settings()
    reports_dir = settings.reports_dir
    reports = []
    if reports_dir.exists():
        for pdf in sorted(reports_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = pdf.stat()
            reports.append({
                "filename": pdf.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "download_url": f"/api/reports/{pdf.name}",
            })
    return web.json_response(reports)


async def handle_get_report(request: web.Request) -> web.Response:
    settings = get_settings()
    filename = request.match_info.get("filename", "")
    safe_name = Path(filename).name
    report_path = settings.reports_dir / safe_name

    if not report_path.exists() or not report_path.is_file():
        return web.json_response({"error": "Report not found"}, status=404)

    return web.FileResponse(
        report_path,
        headers={
            "Content-Type": "application/pdf",
            "Content-Disposition": f'inline; filename="{safe_name}"',
        },
    )


async def handle_instant_scrape(request: web.Request) -> web.Response:
    """Instant live scrape of any arbitrary user-specified URL."""
    settings = get_settings()
    try:
        data = await request.json()
    except Exception:
        try:
            raw = await request.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}

    url = str(data.get("url", "")).strip()
    if not url:
        return web.json_response({"error": "URL is required"}, status=400)

    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"

    from .ingestion import scrape_url
    from .state import PageType

    # Infer page type from URL string
    page_type = PageType.PRICING
    url_lower = url.lower()
    if "terms" in url_lower or "privacy" in url_lower:
        page_type = PageType.TERMS
    elif "blog" in url_lower or "changelog" in url_lower or "news" in url_lower:
        page_type = PageType.CHANGELOG

    result = await scrape_url(settings, url, page_type)
    return web.json_response({
        "url": url,
        "page_type": page_type.value,
        "ok": result.ok,
        "content": result.content or "",
        "char_count": len(result.content) if result.content else 0,
        "error": result.error,
    })


async def handle_instant_analyze(request: web.Request) -> web.Response:
    """Perform instant DeepSeek synthesis and generate a PDF brief for provided markdown."""
    settings = get_settings()
    try:
        data = await request.json()
    except Exception:
        try:
            raw = await request.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}

    url = str(data.get("url", "")).strip()
    content = str(data.get("content", "")).strip()
    domain = str(data.get("domain", "")).strip()

    if not domain and url:
        domain = url.split("//")[-1].split("/")[0]

    if not domain:
        domain = "competitor.com"

    if not content:
        return web.json_response({"error": "Content is required for analysis"}, status=400)

    from .chunking import prepare_chunks
    from .intelligence import analyze_changes
    from .reporting import generate_executive_pdf
    from .state import ChangeType, ChunkDiff, ExecutiveBrief, PageDiff, PageType
    from .vector_store import build_json_diff_payload

    chunks = prepare_chunks(content)
    page_diff = PageDiff(page_type=PageType.PRICING, url=url or f"https://{domain}")
    for chunk in chunks[:5]:
        page_diff.diffs.append(
            ChunkDiff(
                page_type=PageType.PRICING,
                url=url or f"https://{domain}",
                change_type=ChangeType.NEW_CONTENT,
                current_chunk=chunk,
            )
        )

    payload = build_json_diff_payload([page_diff])

    if settings.has_llm():
        try:
            brief = await asyncio.to_thread(analyze_changes, settings, payload)
        except Exception as exc:
            logger.warning("Instant LLM analysis failed: %s — using fallback", exc)
            brief = ExecutiveBrief.fallback_from_diffs(domain, [page_diff])
    else:
        brief = ExecutiveBrief.fallback_from_diffs(domain, [page_diff])

    pdf_path = await asyncio.to_thread(
        generate_executive_pdf,
        brief,
        domain,
        settings.reports_dir,
    )

    # Optional slack alert if configured
    delivered_to = []
    if not settings.distribution_dry_run and (settings.slack_webhook_url or settings.slack_bot_token):
        from .distribution import distribute
        delivered_to = await distribute(settings, pdf_path, brief)

    return web.json_response({
        "status": "success",
        "domain": domain,
        "pdf_filename": pdf_path.name,
        "download_url": f"/api/reports/{pdf_path.name}",
        "delivered_to": delivered_to,
        "brief": {
            "executive_summary": brief.executive_summary,
            "pricing_shifts": [s.model_dump() for s in brief.pricing_shifts],
            "product_launches": brief.product_launches,
            "terms_updates": brief.terms_updates,
            "key_takeaways": brief.key_takeaways,
        },
    })


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/targets", handle_get_targets)
    app.router.add_post("/api/targets", handle_add_target)
    app.router.add_delete("/api/targets/{domain}", handle_delete_target)
    app.router.add_post("/api/run", handle_trigger_run)
    app.router.add_get("/api/run/status", handle_run_status)
    app.router.add_get("/api/reports", handle_list_reports)
    app.router.add_get("/api/reports/{filename}", handle_get_report)
    app.router.add_post("/api/scrape", handle_instant_scrape)
    app.router.add_post("/api/analyze-content", handle_instant_analyze)

    if STATIC_DIR.exists():
        app.router.add_static("/static/", STATIC_DIR)

    return app


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    import threading
    app = create_app()
    logger.info("Starting Competepulse Web Dashboard on http://%s:%d", host, port)
    is_main = threading.current_thread() is threading.main_thread()
    web.run_app(app, host=host, port=port, handle_signals=is_main)


if __name__ == "__main__":
    run_server()
