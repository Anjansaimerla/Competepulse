# Technical Requirements Document (TRD): Competepulse

## 1. Project Overview & Objective

**Competepulse** is an autonomous market research agent designed to track competitor changes. Instead of manual monitoring, the system automatically scrapes specified target domains weekly, compares current snapshots against historical data using vector embeddings to detect meaningful shifts, and compiles the insights into an executive-level PDF report distributed via automated channels.

  

## 2. System Architecture & Tech Stack

- **Language:** Python 3.10+
    
      
    
- **Orchestration & Workflow:** `asyncio` for concurrent operations; LangGraph or modular Python functions for state management.
    
      
    
- **Scraping Layer:** Firecrawl API (primary Markdown extraction) with Playwright/BeautifulSoup fallback for custom handling.
    
      
    
- **Database & Vector Layer:** Supabase (PostgreSQL) leveraging the `pgvector` extension for storing text chunks and semantic embeddings.
    
      
    
- **LLM & Analysis:** OpenAI API (GPT-4o or text-embedding-3-small) for differential analysis and structured data extraction.
    
      
    
- **Reporting Engine:** ReportLab for programmatic PDF document compilation.
    
      
    
- **Infrastructure & Automation:** Docker for containerization, GitHub Actions (Cron schedule) for headless weekly execution, and Slack Webhooks / SendGrid for delivery.
    
      
    

## 3. Data Flow & State Management

The agent executes through a defined state machine lifecycle:

  

1. **Input Phase:** Triggered via cron schedule with target domains passed into the execution context.
    
      
    
2. **Scraping Phase:** Asynchronous requests fire against target endpoints (`/pricing`, `/blog`, `/terms`).
    
      
    
3. **Storage & Comparison Phase:**
    
      
    - Raw text is chunked and embedded.
        
          
        
    - New embeddings are queried against Supabase `pgvector` history via similarity thresholds ($\ge 0.85$) to isolate real changes from superficial updates.
        
          
        
    - New snapshots are committed to the database.
        
          
        
4. **Synthesis Phase:** LLM processes the structured diffs to generate a concise, multi-section executive summary.
    
      
    
5. **Reporting & Distribution Phase:** ReportLab compiles the summary into a styled PDF asset, which is subsequently pushed to Slack/Email and archived.
    
      
    

```
[Cron Trigger / GitHub Action] 
       │
       ▼
[Async Scraper (Firecrawl)] ──► [Text Chunking & Embedding Model]
                                         │
                                         ▼
[PDF Generation Engine] ◄── [LLM Analysis] ◄── [Supabase pgvector (Diff Lookup)]
       │
       ▼
[Slack / Email Distribution]
```

## 4. Component Specifications

### 4.1 Ingestion & Scraping Module

- **Inputs:** Target domain string (e.g., `competitor.com`).
    
      
    
- **Endpoints Targeted:**
    
      
    - `https://{domain}/pricing`
        
          
        
    - `https://{domain}/blog` or `/changelog`
        
          
        
    - `https://{domain}/terms`
        
          
        
- **Output:** Clean Markdown content mapped per endpoint using `asyncio.gather`.
    
      
    

### 4.2 Storage & Vector Matching Module

- **Database Schema Requirements (`Supabase`):**
    
      
    - `competitor_snapshots`: Table storing `id`, `domain`, `endpoint`, `content`, `embedding` (vector type), and `created_at`timestamp.
        
          
        
- **Vector Search Function:** A PostgreSQL RPC function (`match_snapshots`) configured to perform cosine distance searches to retrieve historical context efficiently.
    
      
    

### 4.3 Intelligence & LLM Module

- **Prompt Engineering Target:** Acts as an elite market intelligence analyst.
    
      
    
- **Output Schema (JSON):**
    
      
    
    JSON
    
    ```
    {
      "pricing_shifts": "Summary of pricing or tier adjustments",
      "product_launches": "Summary of new features or blog updates",
      "terms_updates": "Summary of legal or policy modifications"
    }
    ```
    

### 4.4 Reporting Module

- **Template Specifications:** Single or multi-page layout using Letter sizing, standardized margins (36pt), custom typographic hierarchy (`ParagraphStyle`), and automated page-break or spacer handling.
    
      
    
- **Output Asset:** A locally generated file named `executive_brief_{domain}_{date}.pdf`.
    
      
    

## 5. Deployment & Operational Requirements

- **Environment Variables:**
    
      
    - `FIRECRAWL_API_KEY`
        
          
        
    - `SUPABASE_URL`
        
          
        
    - `SUPABASE_KEY`
        
          
        
    - NVIDIA_API_KEY
    `
        
          
        
    - `SLACK_WEBHOOK_URL` (optional)
        
          
        
- **Execution Environment:** Dockerfile utilizing a lightweight Python slim base image with installed system dependencies for ReportLab rendering.
    
      
    
- **Schedule:** Configured via GitHub Actions workflow (`.github/workflows/competepulse.yml`) executing every Monday at 06:00 UTC.
2. [[appflow]]
3. [[rules]]
4. [[systemarchitecture]]
5. [[overview]]
6. [[prd]]
7. 