# Competepulse

Autonomous market-intelligence agent: weekly it scrapes competitor pages (pricing / blog / terms), detects **semantic** changes with `pgvector` embeddings, synthesizes the shifts with an LLM, compiles a styled **executive PDF brief**, and delivers it to Slack / email — fully on autopilot.

```
[GitHub Actions Cron — Mondays 06:00 UTC]
        │
        ▼
[1. Async Ingestion — Firecrawl]──► clean Markdown (fallback: direct fetch)
        ▼
[2. Vector Diff — Supabase pgvector]──► flag chunks with similarity < 0.85
        ▼
[3. LLM Synthesis — GPT-4o JSON mode]──► validated ExecutiveBrief (Pydantic)
        ▼
[4. PDF Engine — ReportLab]──► reports/competepulse_brief_{domain}_{date}.pdf
        ▼
[5. Distribution — Slack webhook/files · SendGrid email]
```

## Quick start

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in your API keys
cp targets.example.json targets.json   # edit your competitor list

python main.py                # one full run
python -m pytest              # test suite (no network needed)
```

Minimum required env vars for a full run: `FIRECRAWL_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`. Distribution channels are optional; with `DISTRIBUTION_DRY_RUN=true` every outbound payload is saved to `failed_deliveries/dry_run/` instead of being sent.

**Degraded modes** (no credentials needed to try it): without Firecrawl the scraper falls back to direct HTTP fetches; without Supabase/OpenAI the run skips history and uses the deterministic fallback brief.

## Database setup

Run `supabase/schema.sql` once in the Supabase SQL editor. It creates:

- `competitors` — domain registry with monitoring config
- `competitor_snapshots` — markdown chunks + `vector(1536)` embeddings, with exact/weekly idempotency (unique on `domain, url, content_hash, week_of`) so re-runs never duplicate rows
- `match_snapshots(query_embedding, match_threshold, match_count, target_domain, target_url)` — cosine-similarity RPC

## Configuration

| Variable | Purpose |
| --- | --- |
| `FIRECRAWL_API_KEY` | Managed scraping (JS rendering, anti-bot bypass) |
| `SUPABASE_URL` / `SUPABASE_KEY` | Snapshot history + vector search |
| `OPENAI_API_KEY` | Embeddings + brief synthesis (`COMPETEPULSE_MODEL`, default `gpt-4o`) |
| `SLACK_WEBHOOK_URL` / `SLACK_BOT_TOKEN` / `SLACK_CHANNEL_ID` | Slack alert + PDF upload |
| `SENDGRID_API_KEY` / `SENDER_EMAIL` / `RECIPIENT_EMAILS` | Email delivery |
| `DISTRIBUTION_DRY_RUN` | `true` = save payloads locally instead of sending |
| `COMPETEPULSE_TARGETS` | Path to the targets JSON (default `targets.json`) |

## Deployment

- **Docker:** `docker build -t competepulse . && docker run --env-file .env competepulse`
- **GitHub Actions:** `.github/workflows/competepulse.yml` runs every Monday 06:00 UTC (`workflow_dispatch` for manual runs). Add your keys as repository secrets.

## Engineering rules honored

- Strict type hints; credentials only via env vars; timestamped, secret-masked logging (`rules.md`)
- Immutable state object threaded through every stage (`sysrules.md`)
- 512-token chunks with 64-token overlap; boilerplate stripped before embedding (`multirules.md`, `sysrules.md`)
- Graceful degradation per page; one failed page or channel never kills the run
- LLM output schema-validated with retry + deterministic fallback (`intellirules.md`)
