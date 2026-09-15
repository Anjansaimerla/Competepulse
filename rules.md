## Competepulse: Engineering Rules & Architecture Spec

### 1. Project Philosophy & Engineering Principles

- **Simplicity First:** Keep the core agent loop linear and understandable. Avoid over-engineering frameworks when basic Python asynchronous scripts suffice.
    
      
    
- **Idempotency:** Re-running a failed workflow for the same week should safely update or bypass existing snapshots without corrupting historical data.
    
      
    
- **Fail-Safe Scraping:** Network requests and LLM calls must have robust error handling and fallbacks so a single broken page doesn't crash the entire weekly report.
    
      
    

### 2. Tech Stack & Environment

- **Language:** Python 3.11+
    
      
    
- **Asynchronous Engine:** `asyncio` for concurrent multi-page scraping
    
      
    
- **Scraping Provider:** Firecrawl API (primary), Playwright (headless fallback)
    
      
    
- **Database & Vector Store:** Supabase (`pgvector` extension enabled)
    
      
    
- **LLM Orchestration:** OpenAI API (`gpt-4o` or compatible model)
    
      
    
- **Document Generation:** ReportLab
    
      
    
- **Containerization & Hosting:** Docker, GitHub Actions (Cron), or Supabase Edge Functions
    
      
    

### 3. Core Database Schema (Supabase)

#### Table: `competitor_snapshots`

Stores raw scraped text blocks and their corresponding vector embeddings for diff analysis.

  

|**Column Name**|**Data Type**|**Description**|
|---|---|---|
|`id`|UUID (Primary Key)|Unique identifier for the chunk.|
|`domain`|VARCHAR(255)|Competitor domain name (e.g., `competitor.com`).|
|`page_type`|VARCHAR(50)|Category of page (`pricing`, `blog`, `terms`).|
|`content`|TEXT|Raw Markdown text extracted by Firecrawl.|
|`embedding`|VECTOR(1536)|OpenAI text embedding-3-small vector representation.|
|`created_at`|TIMESTAMPTZ|Automatic timestamp of the crawl.|

#### Vector Similarity Search Function (`match_snapshots`)

PostgreSQL function required in Supabase to query historical text by semantic similarity.

  

SQL

```
create or replace function match_snapshots (
  query_embedding vector,
  match_threshold float,
  match_count int,
  target_domain text
)
returns table (
  id uuid,
  content text,
  similarity float
)
language sql stable
as $$
  select
    competitor_snapshots.id,
    competitor_snapshots.content,
    1 - (competitor_snapshots.embedding <=> query_embedding) as similarity
  from competitor_snapshots
  where competitor_snapshots.domain = target_domain
    and 1 - (competitor_snapshots.embedding <=> query_embedding) > match_threshold
  order by competitor_snapshots.embedding <=> query_embedding
  limit match_count;
$$;
```

### 4. Workflow Rules & Execution Steps

1. **Trigger Phase:** GitHub Actions cron job triggers the container every Monday at 06:00 UTC.
    
      
    
2. **Ingestion Phase:**
    
      
    - Agent reads a target list of competitor domains from a configuration file.
        
          
        
    - `asyncio.gather` fires concurrent scraping requests via Firecrawl for `/pricing`, `/blog`, and `/terms`.
        
          
        
3. **Storage & Comparison Phase:**
    
      
    - Incoming text is chunked and embedded via OpenAI.
        
          
        
    - Agent queries Supabase via `match_snapshots` to pull the previous week's text.
        
          
        
    - If similarity falls below `0.85`, the delta is flagged as a _significant structural change_.
        
          
        
4. **Synthesis Phase:**
    
      
    - Changes and historical context are passed into the LLM system prompt.
        
          
        
    - The LLM generates a structured JSON summary covering pricing shifts, feature updates, and legal changes.
        
          
        
5. **Reporting & Distribution Phase:**
    
      
    - ReportLab compiles the structured summary into an executive PDF brief (`competepulse_brief_{domain}_{date}.pdf`).
        
          
        
    - The script pushes the PDF to Slack via webhook or sends it via SendGrid API.
        
          
        

### 5. Coding & Contribution Guidelines

- **Type Hinting:** All Python functions must include explicit type hints for inputs and outputs.
    
      
    
- **Environment Variables:** Never hardcode API keys. All credentials (`FIRECRAWL_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`) must load exclusively via a `.env` file or secure CI/CD secrets.
    
      
    
- **Logging:** Use Python's built-in `logging` module with timestamps to track scraping failures, embedding generation steps, and PDF compilation status.


3. [[systemarchitecture]]
4. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. 