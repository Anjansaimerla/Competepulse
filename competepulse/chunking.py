"""Semantic text chunking engine.

Rules (sysrules.md §3 + multirules.md §3):
- Split markdown into semantic blocks with a maximum size (~512 tokens)
  and overlap (~64 tokens) so micro-changes can be isolated.
- Strip boilerplate (nav bars, cookie banners, copyright footers) before
  vectorization to prevent false positives in similarity comparisons.
"""

import re

# Rough token estimate: ~4 characters per token for English prose.
CHARS_PER_TOKEN = 4
MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64

MAX_CHUNK_CHARS = MAX_CHUNK_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN

# Lines that are pure boilerplate and must not reach the vector store.
_BOILERPLATE_PATTERNS = [
    re.compile(r"^\s*(accept|reject|manage)\s+(all\s+)?cookies\s*$", re.IGNORECASE),
    re.compile(r"cookie (banner|consent|settings|policy)", re.IGNORECASE),
    re.compile(r"we use (cookies|essential cookies)", re.IGNORECASE),
    re.compile(r"^\s*(skip to (main )?content|back to top)\s*$", re.IGNORECASE),
    re.compile(r"sign( )?up|log( )?in|get started|book a demo|contact sales|try for free", re.IGNORECASE),
    re.compile(r"all rights reserved", re.IGNORECASE),
    re.compile(r"^copyright ©?.*$", re.IGNORECASE),
    re.compile(r"^\s*\[!?\[.*\]\(.*\)\]\(.*\)\s*$"),  # standalone linked images
]

_HEADING_SPLIT = re.compile(r"\n(?=#{1,6}\s)")


def strip_boilerplate(markdown: str) -> str:
    """Remove nav/footer/cookie noise lines from raw Firecrawl markdown."""
    kept: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if any(p.search(stripped) for p in _BOILERPLATE_PATTERNS):
            continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def chunk_markdown(
    markdown: str,
    max_chars: int = MAX_CHUNK_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> list[str]:
    """Split markdown into semantic chunks.

    Strategy: prefer splitting on markdown headings, then on blank-line
    paragraphs; pack small siblings together and split oversized blocks with
    a sliding overlap window so nothing is lost across boundaries.
    """
    if not markdown or not markdown.strip():
        return []

    sections: list[str] = []
    for section in _HEADING_SPLIT.split(markdown):
        paragraphs = [p.strip() for p in section.split("\n\n") if p.strip()]
        if not paragraphs:
            continue

        current = paragraphs[0]
        for para in paragraphs[1:]:
            if len(current) + len(para) + 2 <= max_chars:
                current = f"{current}\n\n{para}"
            else:
                sections.append(current)
                current = para
        sections.append(current)

    chunks: list[str] = []
    for section in sections:
        if len(section) <= max_chars:
            chunks.append(section)
            continue
        # Sliding window for oversized sections.
        start = 0
        step = max(max_chars - overlap_chars, 1)
        while start < len(section):
            window = section[start : start + max_chars]
            if start + max_chars < len(section) and " " in window:
                cut = window.rfind(" ", int(len(window) * 0.7))
                if cut > 0:
                    window = window[:cut]
            chunks.append(window.strip())
            start += step if window else max_chars
        chunks = [c for c in chunks if c]

    return chunks


def prepare_chunks(markdown: str) -> list[str]:
    """Full cleansing pipeline: strip boilerplate, then chunk."""
    return chunk_markdown(strip_boilerplate(markdown))
