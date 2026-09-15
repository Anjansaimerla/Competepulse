"""Tests for the Competepulse Web Dashboard handlers."""

import asyncio
import json
from pathlib import Path
import pytest
from aiohttp.test_utils import make_mocked_request

from competepulse.config import Settings
from competepulse.web import (
    handle_add_target,
    handle_delete_target,
    handle_get_report,
    handle_get_targets,
    handle_index,
    handle_list_reports,
    handle_run_status,
    handle_status,
)


@pytest.mark.asyncio
async def test_handle_index():
    req = make_mocked_request("GET", "/")
    resp = await handle_index(req)
    assert resp.status == 200


@pytest.mark.asyncio
async def test_handle_status():
    req = make_mocked_request("GET", "/api/status")
    resp = await handle_status(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert "integrations" in data
    assert "stats" in data
    assert "config" in data


@pytest.mark.asyncio
async def test_handle_get_targets():
    req = make_mocked_request("GET", "/api/targets")
    resp = await handle_get_targets(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_handle_add_and_delete_target(tmp_path: Path, monkeypatch):
    targets_file = tmp_path / "targets.json"
    targets_file.write_text("[]", encoding="utf-8")

    from competepulse import web

    def _mock_settings():
        return Settings(_env_file=None, targets_path=targets_file)

    monkeypatch.setattr(web, "get_settings", _mock_settings)

    # Add target
    payload = {"domain": "new-test.com", "page_types": ["pricing", "terms"]}
    req = make_mocked_request("POST", "/api/targets")
    req.json = lambda: asyncio.sleep(0, result=payload)

    resp = await handle_add_target(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert data["domain"] == "new-test.com"

    # Delete target
    req_del = make_mocked_request("DELETE", "/api/targets/new-test.com", match_info={"domain": "new-test.com"})
    resp_del = await handle_delete_target(req_del)
    assert resp_del.status == 200
    data_del = json.loads(resp_del.text)
    assert data_del["status"] == "deleted"


@pytest.mark.asyncio
async def test_handle_list_and_get_reports(tmp_path: Path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pdf_file = reports_dir / "brief_test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 test")

    from competepulse import web

    def _mock_settings():
        return Settings(_env_file=None, reports_dir=reports_dir)

    monkeypatch.setattr(web, "get_settings", _mock_settings)

    # List reports
    req = make_mocked_request("GET", "/api/reports")
    resp = await handle_list_reports(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert len(data) == 1
    assert data[0]["filename"] == "brief_test.pdf"

    # Get existing report
    req_get = make_mocked_request("GET", "/api/reports/brief_test.pdf", match_info={"filename": "brief_test.pdf"})
    resp_get = await handle_get_report(req_get)
    assert resp_get.status == 200

    # Get non-existent report
    req_none = make_mocked_request("GET", "/api/reports/missing.pdf", match_info={"filename": "missing.pdf"})
    resp_none = await handle_get_report(req_none)
    assert resp_none.status == 404


@pytest.mark.asyncio
async def test_handle_instant_scrape(monkeypatch):
    from competepulse.state import PageType, ScrapeResult
    from competepulse.web import handle_instant_scrape

    async def _mock_scrape(settings, url, page_type):
        return ScrapeResult(page_type=page_type, url=url, content="# Pricing\nPro: $49/mo")

    monkeypatch.setattr("competepulse.ingestion.scrape_url", _mock_scrape)

    req = make_mocked_request("POST", "/api/scrape")
    req.json = lambda: asyncio.sleep(0, result={"url": "https://example.com/pricing"})
    resp = await handle_instant_scrape(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert data["ok"] is True
    assert "Pro: $49/mo" in data["content"]


@pytest.mark.asyncio
async def test_handle_instant_analyze(tmp_path: Path, monkeypatch):
    from competepulse import web
    from competepulse.web import handle_instant_analyze

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    def _mock_settings():
        return Settings(_env_file=None, reports_dir=reports_dir)

    monkeypatch.setattr(web, "get_settings", _mock_settings)

    payload = {
        "url": "https://competitor.com/pricing",
        "domain": "competitor.com",
        "content": "# Pricing\nNew Enterprise tier at $999/mo with dedicated support.",
    }
    req = make_mocked_request("POST", "/api/analyze-content")
    req.json = lambda: asyncio.sleep(0, result=payload)

    resp = await handle_instant_analyze(req)
    assert resp.status == 200
    data = json.loads(resp.text)
    assert data["status"] == "success"
    assert "brief" in data
    assert "download_url" in data
