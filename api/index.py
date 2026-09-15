"""Vercel Serverless API Handler for Competepulse.

Handles all /api/* requests on Vercel's Python runtime.
"""

import asyncio
import concurrent.futures
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from competepulse.chunking import prepare_chunks
from competepulse.config import PAGE_TYPES, Settings, get_settings
from competepulse.ingestion import scrape_url
from competepulse.intelligence import analyze_changes
from competepulse.pipeline import load_targets
from competepulse.reporting import generate_executive_pdf
from competepulse.state import ChangeType, ChunkDiff, ExecutiveBrief, PageDiff, PageType, Target
from competepulse.vector_store import build_json_diff_payload


def _run_async(coro):
    """Safely run an async coroutine across sync/async serverless contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result(timeout=25)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class handler(BaseHTTPRequestHandler):
    """Vercel Serverless HTTP Request Handler."""

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.rstrip("/")
            settings = get_settings()

            if path == "/api/status" or path == "/api/status/":
                targets = load_targets(settings)
                reports_dir = Path("/tmp/reports") if os.path.exists("/tmp") else settings.reports_dir
                reports_count = len(list(reports_dir.glob("*.pdf"))) if reports_dir.exists() else 0

                status_payload = {
                    "integrations": {
                        "firecrawl": bool(settings.firecrawl_api_key),
                        "supabase": bool(settings.supabase_url and settings.supabase_key),
                        "nvidia_nim": bool(settings.nvidia_api_key),
                        "openai": bool(settings.openai_api_key),
                        "slack": bool(settings.slack_webhook_url or (settings.slack_bot_token and settings.slack_channel_id)),
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
                        "is_running": False,
                    },
                }
                return self._send_json(status_payload)

            elif path == "/api/targets" or path == "/api/targets/":
                targets = load_targets(settings)
                return self._send_json([
                    {"domain": t.domain, "page_types": [pt.value for pt in t.page_types]}
                    for t in targets
                ])

            elif path == "/api/reports" or path == "/api/reports/":
                reports_dir = Path("/tmp/reports") if os.path.exists("/tmp") else settings.reports_dir
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
                return self._send_json(reports)

            elif path.startswith("/api/reports/"):
                filename = path.replace("/api/reports/", "")
                safe_name = Path(filename).name
                reports_dir = Path("/tmp/reports") if os.path.exists("/tmp") else settings.reports_dir
                report_path = reports_dir / safe_name
                if not report_path.exists() or not report_path.is_file():
                    return self._send_json({"error": "Report not found"}, status=404)

                pdf_bytes = report_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
                self.send_header("Content-Length", str(len(pdf_bytes)))
                self.end_headers()
                self.wfile.write(pdf_bytes)
                return

            elif path == "/api/run/status" or path == "/api/run/status/":
                return self._send_json({
                    "is_running": False,
                    "current_domain": None,
                    "current_step": "idle",
                    "last_status": "ready",
                    "logs": [{"timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"), "level": "INFO", "message": "Vercel Edge API online."}],
                })

            self._send_json({"error": f"Endpoint not found: {path}"}, status=404)
        except Exception as exc:
            traceback.print_exc()
            self._send_json({"error": f"Internal server error: {exc}"}, status=500)

    def do_POST(self) -> None:
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path.rstrip("/")
            settings = get_settings()

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"

            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                data = {}

            if path == "/api/scrape" or path == "/api/scrape/":
                url = str(data.get("url", "")).strip()
                if not url:
                    return self._send_json({"error": "URL is required"}, status=400)
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = f"https://{url}"

                page_type = PageType.PRICING
                url_lower = url.lower()
                if "terms" in url_lower or "privacy" in url_lower:
                    page_type = PageType.TERMS
                elif "blog" in url_lower or "changelog" in url_lower or "news" in url_lower:
                    page_type = PageType.CHANGELOG

                result = _run_async(scrape_url(settings, url, page_type))
                return self._send_json({
                    "url": url,
                    "page_type": page_type.value,
                    "ok": result.ok,
                    "content": result.content or "",
                    "char_count": len(result.content) if result.content else 0,
                    "error": result.error,
                })

            elif path == "/api/analyze-content" or path == "/api/analyze-content/":
                url = str(data.get("url", "")).strip()
                content = str(data.get("content", "")).strip()
                domain = str(data.get("domain", "")).strip()

                if not domain and url:
                    domain = url.split("//")[-1].split("/")[0]
                if not domain:
                    domain = "competitor.com"
                if not content:
                    return self._send_json({"error": "Content is required for analysis"}, status=400)

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
                        brief = analyze_changes(settings, payload)
                    except Exception as exc:
                        brief = ExecutiveBrief.fallback_from_diffs(domain, [page_diff])
                else:
                    brief = ExecutiveBrief.fallback_from_diffs(domain, [page_diff])

                reports_dir = Path("/tmp/reports") if os.path.exists("/tmp") else settings.reports_dir
                reports_dir.mkdir(parents=True, exist_ok=True)
                pdf_path = generate_executive_pdf(brief, domain, output_dir=reports_dir)

                return self._send_json({
                    "status": "success",
                    "domain": domain,
                    "brief": {
                        "executive_summary": brief.executive_summary,
                        "pricing_shifts": [s.model_dump() for s in brief.pricing_shifts],
                        "product_launches": brief.product_launches,
                        "terms_updates": brief.terms_updates,
                        "key_takeaways": brief.key_takeaways,
                    },
                    "pdf_filename": pdf_path.name,
                    "download_url": f"/api/reports/{pdf_path.name}",
                })

            elif path == "/api/targets" or path == "/api/targets/":
                domain = str(data.get("domain", "")).strip().lower()
                if not domain:
                    return self._send_json({"error": "Domain is required"}, status=400)
                domain = domain.split("//")[-1].split("/")[0]

                raw_pages = data.get("page_types") or ["pricing", "changelog", "terms"]
                valid_pages = [p for p in raw_pages if p in PAGE_TYPES] or ["pricing", "changelog", "terms"]

                targets_path = Path(settings.targets_path)
                existing = []
                if targets_path.exists():
                    try:
                        existing = json.loads(targets_path.read_text(encoding="utf-8"))
                    except Exception:
                        existing = []

                updated = False
                for item in existing:
                    if item.get("domain") == domain:
                        item["page_types"] = valid_pages
                        updated = True
                        break
                if not updated:
                    existing.append({"domain": domain, "page_types": valid_pages})

                try:
                    targets_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
                except Exception:
                    pass
                return self._send_json({"status": "success", "domain": domain, "page_types": valid_pages})

            self._send_json({"error": f"Endpoint not found: {path}"}, status=404)
        except Exception as exc:
            traceback.print_exc()
            self._send_json({"error": f"Internal server error: {exc}"}, status=500)
