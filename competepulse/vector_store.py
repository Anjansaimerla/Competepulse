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
    """Batch-embed chunks with OpenAI embeddings (1536 dims)."""
    response = client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
        dimensions=settings.embedding_dimensions,
    )
    return [item.embedding for item in response.data]


def query_match_snapshots(
    supabase: Any, embedding: list[float], settings: Settings, domain: str, url: str
) -> list[dict[str, Any]]:
    """Call the match_snapshots RPC; returns [{id, content, similarity}]."""
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

    embeddings = embed_texts(settings, openai_client, chunks)
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


def save_monitored_target(settings: Settings, domain: str, page_types: list[str] | None = None) -> bool:
    """Save or update a competitor target in Supabase (and local targets.json)."""
    clean_domain = domain.split("//")[-1].split("/")[0].lower().strip()
    if not clean_domain:
        return False
    pages = page_types or ["pricing", "changelog", "terms"]

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

    try:
        from pathlib import Path
        targets_path = Path(settings.targets_path)
        existing = []
        if targets_path.exists():
            try:
                existing = json.loads(targets_path.read_text(encoding="utf-8"))
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
        targets_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass

    return True


def get_monitored_targets(settings: Settings) -> list[Target]:
    """Retrieve all active monitored competitor targets from Supabase and local targets.json."""
    from .state import Target
    targets_dict: dict[str, list[str]] = {}

    # 1. Try Supabase registry
    if settings.has_vector_store():
        try:
            supabase = get_supabase(settings)
            response = supabase.table("competitors").select("domain, page_types").eq("active", True).execute()
            if response.data:
                for row in response.data:
                    d = str(row.get("domain", "")).lower().strip()
                    if d:
                        targets_dict[d] = row.get("page_types") or ["pricing", "changelog", "terms"]
        except Exception as exc:
            logger.debug("Could not fetch targets from Supabase: %s", exc)

    # 2. Local targets.json
    try:
        from pathlib import Path
        targets_path = Path(settings.targets_path)
        if targets_path.exists():
            local_list = json.loads(targets_path.read_text(encoding="utf-8"))
            if isinstance(local_list, list):
                for item in local_list:
                    if isinstance(item, dict) and item.get("domain"):
                        d = str(item["domain"]).lower().strip()
                        if d not in targets_dict:
                            targets_dict[d] = item.get("page_types") or ["pricing", "changelog", "terms"]
    except Exception:
        pass

    results: list[Target] = []
    for dom, ptypes in targets_dict.items():
        results.append(
            Target(
                domain=dom,
                page_types=[PageType(pt) for pt in ptypes if pt in [e.value for e in PageType]] or [PageType.PRICING, PageType.CHANGELOG, PageType.TERMS],
            )
        )
    return results


def delete_monitored_target(settings: Settings, domain: str) -> bool:
    """Deactivate target in Supabase and remove from local targets.json."""
    clean_domain = domain.split("//")[-1].split("/")[0].lower().strip()
    if settings.has_vector_store():
        try:
            supabase = get_supabase(settings)
            supabase.table("competitors").update({"active": False}).eq("domain", clean_domain).execute()
        except Exception as exc:
            logger.debug("Failed to deactivate target in Supabase: %s", exc)

    try:
        from pathlib import Path
        targets_path = Path(settings.targets_path)
        if targets_path.exists():
            existing = json.loads(targets_path.read_text(encoding="utf-8"))
            filtered = [item for item in existing if item.get("domain") != clean_domain]
            targets_path.write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    except Exception:
        pass
    return True
