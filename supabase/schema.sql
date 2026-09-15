-- =============================================================
-- Competepulse: Supabase / PostgreSQL schema
-- Run this in the Supabase SQL Editor (or via `supabase db push`).
-- Idempotent: safe to execute multiple times.
-- =============================================================

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Competitor registry (domain metadata + monitoring config)
create table if not exists competitors (
    id uuid primary key default gen_random_uuid(),
    domain text not null unique,
    display_name text,
    page_types text[] not null default '{pricing,changelog,terms}',
    frequency text not null default 'weekly',
    active boolean not null default true,
    created_at timestamptz not null default timezone('utc'::text, now())
);

-- 3. Snapshot storage: raw markdown chunks + embeddings
create table if not exists competitor_snapshots (
    id bigserial primary key,
    domain text not null,
    url text not null,
    page_type text not null,            -- 'pricing' | 'changelog' | 'blog' | 'terms'
    content text not null,              -- raw markdown chunk
    content_hash text,                  -- sha256 of the chunk (exact-duplicate guard)
    week_of date not null default (date_trunc('week', now()))::date,
    embedding vector(1536),             -- OpenAI text-embedding-3-small
    created_at timestamptz not null default timezone('utc'::text, now())
);

-- 4. Exact + weekly idempotency guards (re-runs never duplicate rows)
create unique index if not exists competitor_snapshots_dedupe_idx
    on competitor_snapshots (domain, url, content_hash, week_of);

create index if not exists competitor_snapshots_domain_idx
    on competitor_snapshots (domain, page_type, week_of);

-- 5. Fast cosine similarity search
create index if not exists competitor_snapshots_embedding_idx
    on competitor_snapshots using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 6. Semantic similarity RPC (cosine distance)
create or replace function match_snapshots (
    query_embedding vector(1536),
    match_threshold float,
    match_count int,
    target_domain text,
    target_url text
)
returns table (
    id bigint,
    content text,
    similarity float
)
language sql stable
as $$
    select
        s.id,
        s.content,
        1 - (s.embedding <=> query_embedding) as similarity
    from competitor_snapshots as s
    where s.domain = target_domain
      and s.url = target_url
      and s.embedding is not null
      and 1 - (s.embedding <=> query_embedding) > match_threshold
    order by s.embedding <=> query_embedding
    limit match_count;
$$;
