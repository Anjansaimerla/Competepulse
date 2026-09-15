"""Vector storage & semantic change detection (Supabase + pgvector).

Implements Vector-Backed Change Detection.md:
1. Chunk content -> embed via OpenAI text-embedding-3-small.
2. Query historical snapshots through the `match_snapshots` RPC.
3. similarity >= threshold -> unchanged; below -> flagged for the LLM;
   no match at all -> new content.
4. Persist the new snapshot (idempotent on domain+url+hash+week).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .chunking import prepare_chunks
from .config import Settings
from .logging_utils import get_logger
from .state import ChangeType, ChunkDiff, PageDiff, PageType, ScrapeResult, Target, week_of_today

logger = get_logger("competepulse.vector_store")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_supabase(settings: Settings) -> Any:
    from supabase import create_client  # lazy import keeps tests dependency-light

    return create_client(settings.supabase_url, settings.supabase_key)


def get_openai(settings: Settings) -> Any:
    from openai import OpenAI

    api_key = settings.openai_api_key or settings.effective_llm_api_key
    base_url = None if settings.openai_api_key else settings.effective_llm_base_url
    return OpenAI(api_key=api_key, base_url=base_url)


def embed_texts(settings: Settings, client: Any, texts: list[str]) -> list[list[float]]:
    """Batch-embed chunks with OpenAI or NVIDIA NIM embeddings."""
    model = settings.embedding_model
    if not settings.openai_api_key and settings.nvidia_api_key:
        if "text-embedding" in model or "e5-v5" in model:
            model = "baai/bge-large-en-v1.5"
        try:
            response = client.embeddings.create(
                model=model,
                input=texts,
                extra_body={"input_type": "passage", "truncate": "END"},
            )
            return [item.embedding for item in response.data]
        except Exception:
            pass

    kwargs: dict[str, Any] = {"model": model, "input": texts}
    if settings.openai_api_key and settings.embedding_dimensions:
        kwargs["dimensions"] = settings.embedding_dimensions

    response = client.embeddings.create(**kwargs)
    return [item.embedding for item in response.data]


def query_match_snapshots(
    supabase: Any, embedding: list[float], settings: Settings, domain: str, url: str
) -> list[dict[str, Any]]:
    """Call the match_snapshots RPC; returns [{id, content, similarity}]."""
    try:
        response = supabase.rpc(
            "match_snapshots",
            {
                "query_embedding": embedding,
                "match_threshold": settings.similarity_threshold,
                "match_count": 1,
                "target_domain": domain,
                "target_url": url,
            },
        ).execute()
        return list(response.data or [])
    except Exception as exc:
        logger.debug("RPC match_snapshots unavailable or failed (%s); treating as new content", exc)
        return []


def insert_snapshot(
    supabase: Any,
    *,
    domain: str,
    url: str,
    page_type: PageType,
    chunk: str,
    embedding: list[float],
    week_of: str,
) -> bool:
    """Idempotent insert: ignore rows already stored for this week."""
    try:
        payload = {
            "domain": domain,
            "url": url,
            "page_type": page_type.value,
            "content": chunk,
            "content_hash": content_hash(chunk),
            "week_of": week_of,
            "embedding": embedding,
        }
        response = supabase.table("competitor_snapshots").upsert(
            payload,
            on_conflict="domain,url,content_hash,week_of",
        ).execute()
        return bool(response.data)
    except Exception as exc:
        logger.debug("Could not insert snapshot to Supabase (%s)", exc)
        return False


def domain_of(url: str) -> str:
    """Extract the bare domain from an absolute URL (e.g. stripe.com)."""
    return url.split("//")[-1].split("/")[0].lower()


def detect_page_changes(
    settings: Settings,
    supabase: Any,
    openai_client: Any,
    scrape_result: ScrapeResult,
) -> PageDiff:
    """Chunk, embed, compare, and store one scraped page."""
    assert scrape_result.content is not None
    chunks = prepare_chunks(scrape_result.content)
    page_diff = PageDiff(page_type=scrape_result.page_type, url=scrape_result.url)

    if not chunks:
        logger.warning("No usable chunks for %s after boilerplate stripping", scrape_result.url)
        return page_diff

    embeddings: list[list[float]] | None = None
    try:
        embeddings = embed_texts(settings, openai_client, chunks)
    except Exception as exc:
        logger.info("Embedding step bypassed (%s); treating content as new", exc)

    if not embeddings or len(embeddings) != len(chunks):
        for chunk in chunks:
            page_diff.diffs.append(
                ChunkDiff(
                    page_type=scrape_result.page_type,
                    url=scrape_result.url,
                    change_type=ChangeType.NEW_CONTENT,
                    current_chunk=chunk,
                )
            )
        return page_diff

    week_of = week_of_today().isoformat()
    domain = domain_of(scrape_result.url)

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        matches = query_match_snapshots(supabase, embedding, settings, domain, scrape_result.url)

        if not matches:
            change_type = ChangeType.NEW_CONTENT
            diff = ChunkDiff(
                page_type=scrape_result.page_type,
                url=scrape_result.url,
                change_type=change_type,
                current_chunk=chunk,
            )
        else:
            best = matches[0]
            similarity = float(best["similarity"])
            if similarity >= settings.similarity_threshold:
                change_type = ChangeType.UNCHANGED
                diff = ChunkDiff(
                    page_type=scrape_result.page_type,
                    url=scrape_result.url,
                    change_type=change_type,
                    current_chunk=chunk,
                    previous_chunk=best["content"],
                    similarity=similarity,
                )
            else:
                change_type = ChangeType.SEMANTIC_SHIFT
                diff = ChunkDiff(
                    page_type=scrape_result.page_type,
                    url=scrape_result.url,
                    change_type=change_type,
                    current_chunk=chunk,
                    previous_chunk=best["content"],
                    similarity=similarity,
                )

        page_diff.diffs.append(diff)
        insert_snapshot(
            supabase,
            domain=domain,
            url=scrape_result.url,
            page_type=scrape_result.page_type,
            chunk=chunk,
            embedding=embedding,
            week_of=week_of,
        )

    changed = len(page_diff.changed_chunks)
    logger.info(
        "Change detection for %s: %d chunk(s), %d flagged",
        scrape_result.url,
        len(page_diff.diffs),
        changed,
    )
    return page_diff


def build_json_diff_payload(diffs: list[PageDiff], max_chars_per_chunk: int = 1200) -> str:
    """Serialize flagged diffs into the JSON payload handed to the LLM."""
    payload: list[dict[str, Any]] = []
    for page in diffs:
        for diff in page.changed_chunks:
            payload.append(
                {
                    "page_type": page.page_type.value,
                    "url": page.url,
                    "change_type": diff.change_type.value,
                    "similarity": diff.similarity,
                    "previous_content": (diff.previous_chunk or "")[:max_chars_per_chunk],
                    "current_content": diff.current_chunk[:max_chars_per_chunk],
                }
            )
    return json.dumps(payload, indent=2)


def _get_candidate_target_paths(settings: Settings) -> list[Path]:
    paths = []
    p = Path(settings.targets_path)
    paths.append(p)
    if str(settings.targets_path) in ("targets.json", "targets.yaml") or os.environ.get("VERCEL"):
        tmp_p = Path("/tmp/targets.json")
        if tmp_p not in paths:
            paths.append(tmp_p)
    return paths


def _get_deleted_targets_path() -> Path:
    return Path("/tmp/deleted_targets.json")


def _read_deleted_targets() -> set[str]:
    p = _get_deleted_targets_path()
    if p.exists():
        try:
            items = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(items, list):
                return {str(x).lower().strip() for x in items if x}
        except Exception:
            pass
    return set()


def _record_deleted_target(domain: str) -> None:
    p = _get_deleted_targets_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        current = _read_deleted_targets()
        current.add(domain.lower().strip())
        p.write_text(json.dumps(list(current)), encoding="utf-8")
    except Exception:
        pass


def _unrecord_deleted_target(domain: str) -> None:
    p = _get_deleted_targets_path()
    try:
        current = _read_deleted_targets()
        clean = domain.lower().strip()
        if clean in current:
            current.remove(clean)
            p.write_text(json.dumps(list(current)), encoding="utf-8")
    except Exception:
        pass


def save_monitored_target(settings: Settings, domain: str, page_types: list[str] | None = None) -> bool:
    """Save or update a competitor target in Supabase (and local/tmp targets.json)."""
    clean_domain = domain.split("//")[-1].split("/")[0].lower().strip()
    if not clean_domain:
        return False
    pages = page_types or ["pricing", "changelog", "terms"]

    _unrecord_deleted_target(clean_domain)

    if settings.has_vector_store():
        try:
            supabase = get_supabase(settings)
            supabase.table("competitors").upsert({
                "domain": clean_domain,
                "display_name": clean_domain.capitalize(),
                "page_types": pages,
                "active": True,
            }, on_conflict="domain").execute()
            logger.info("Saved competitor %s to Supabase registry", clean_domain)
        except Exception as exc:
            logger.debug("Could not persist target to Supabase: %s", exc)

    for p in _get_candidate_target_paths(settings):
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if p.exists():
                try:
                    existing = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            updated = False
            for item in existing:
                if item.get("domain") == clean_domain:
                    item["page_types"] = pages
                    updated = True
                    break
            if not updated:
                existing.append({"domain": clean_domain, "page_types": pages})
            p.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass

    return True


def get_monitored_targets(settings: Settings) -> list[Target]:
    """Retrieve all active monitored competitor targets from Supabase and local targets.json."""
    from .state import Target

    targets_dict: dict[str, list[str]] = {}
    deleted_set = _read_deleted_targets()

    # 1. Try Supabase registry
    if settings.has_vector_store():
        try:
            supabase = get_supabase(settings)
            # Find inactive domains in Supabase
            inactive_res = supabase.table("competitors").select("domain").eq("active", False).execute()
            if inactive_res.data:
                for row in inactive_res.data:
                    d = str(row.get("domain", "")).lower().strip()
                    if d:
                        deleted_set.add(d)

            response = supabase.table("competitors").select("domain, page_types").eq("active", True).execute()
            if response.data:
                for row in response.data:
                    d = str(row.get("domain", "")).lower().strip()
                    if d and d not in deleted_set:
                        targets_dict[d] = row.get("page_types") or ["pricing", "changelog", "terms"]
        except Exception as exc:
            logger.debug("Could not fetch targets from Supabase: %s", exc)

    # 2. Local candidate paths (targets.json and /tmp/targets.json)
    for p in _get_candidate_target_paths(settings):
        try:
            if p.exists():
                local_list = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(local_list, list):
                    for item in local_list:
                        if isinstance(item, dict) and item.get("domain"):
                            d = str(item["domain"]).lower().strip()
                            if d and d not in targets_dict and d not in deleted_set:
                                targets_dict[d] = item.get("page_types") or ["pricing", "changelog", "terms"]
        except Exception:
            pass

    results: list[Target] = []
    for dom, ptypes in targets_dict.items():
        if dom in deleted_set:
            continue
        results.append(
            Target(
                domain=dom,
                page_types=[PageType(pt) for pt in ptypes if pt in [e.value for e in PageType]] or [PageType.PRICING, PageType.CHANGELOG, PageType.TERMS],
            )
        )
    return results


def delete_monitored_target(settings: Settings, domain: str) -> bool:
    """Deactivate target in Supabase and remove from local/tmp targets.json."""
    clean_domain = domain.split("//")[-1].split("/")[0].lower().strip()
    if not clean_domain:
        return False

    _record_deleted_target(clean_domain)

    if settings.has_vector_store():
        try:
            supabase = get_supabase(settings)
            supabase.table("competitors").update({"active": False}).eq("domain", clean_domain).execute()
        except Exception as exc:
            logger.debug("Failed to deactivate target in Supabase: %s", exc)

    for p in _get_candidate_target_paths(settings):
        try:
            if p.exists():
                existing = json.loads(p.read_text(encoding="utf-8"))
                filtered = [item for item in existing if item.get("domain") != clean_domain]
                p.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
        except Exception:
            pass
    return True
