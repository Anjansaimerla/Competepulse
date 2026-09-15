## 1. System Overview

Competepulse is an autonomous market research and competitor tracking agent designed to eliminate manual web surveillance. The system operates on a scheduled cadence to ingest target web pages, perform vector-backed change detection, synthesize strategic diffs via a Large Language Model (LLM), compile a formatted executive PDF brief, and distribute it directly to stakeholders.

  

## 2. High-Level Architecture Diagram

```
[ GitHub Actions Cron ] 
         │
         ▼ (Triggers Container)
┌────────────────────────────────────────────────────────┐
│                      Docker Runtime                    │
│                                                        │
│  [1. Ingestion Agent] ──► (Firecrawl API)              │
│         │                                              │
│         ▼                                              │
│  [2. Vector Engine]   ──► (Supabase pgvector)          │
│         │                                              │
│         ▼                                              │
│  [3. Intelligence]    ──► (OpenAI / Anthropic LLM)     │
│         │                                              │
│         ▼                                              │
│  [4. Report Engine]   ──► (ReportLab PDF Generator)    │
└────────────────────────────────────────────────────────┘
         │
         ▼ (Delivers Artifact)
[ Slack Webhook / SendGrid Email ]
```

## 3. Core Component Specifications

### Ingestion Layer

- **Technology:** Firecrawl API, Python `asyncio`
    
      
    
- **Responsibility:** Bypasses anti-bot mechanisms and dynamic JavaScript barriers to extract clean Markdown representations of targeted competitor pages (`/pricing`, `/blog`, `/terms`). Concurrency handles multiple URLs simultaneously to minimize total execution time.
    
      
    

### Storage & Vector Layer

- **Technology:** Supabase (PostgreSQL with `pgvector` extension)
    
      
    
- **Responsibility:** Persists raw text chunks alongside high-dimensional vector embeddings generated from text payloads. Executes semantic similarity queries (`match_snapshots`) to isolate meaningful business adjustments from superficial layout or formatting modifications.
    
      
    

### Orchestration & Intelligence Layer

- **Technology:** Python, OpenAI / Anthropic models
    
      
    
- **Responsibility:** Manages the pipeline state machine. Packages historical diff context and current scraped data into structured prompts, forcing the LLM to output categorized intelligence insights (pricing shifts, feature updates, regulatory changes).
    
      
    

### Reporting Engine

- **Technology:** ReportLab (Python PDF library)
    
      
    
- **Responsibility:** Transforms structured intelligence payloads into a clean, typography-driven executive PDF brief featuring consistent layouts, section dividers, and structured data layout.
    
      
    

### Infrastructure & Distribution Layer

- **Technology:** Docker, GitHub Actions, Slack Webhooks / SendGrid API
    
      
    
- **Responsibility:** Encapsulates dependencies into a portable image, provisions weekly execution cycles without local infrastructure overhead, and pushes the final PDF artifact to messaging channels or inboxes.
    
      
    

## 4. End-to-End Data Flow

1. **Trigger:** GitHub Actions initiates the scheduled workflow every Monday at 06:00 UTC using the containerized environment.
    
      
    
2. **Scrape:** The async ingestion script concurrently requests targeted competitor endpoints via Firecrawl, returning markdown text blocks.
    
      
    
3. **Embed & Compare:** Text payloads are converted into vectors and checked against historical snapshots residing in Supabase. Cosine distance metrics determine significant content drift.
    
      
    
4. **Synthesize:** The change set is routed to the LLM client, which formats a concise, executive-level change summary.
    
      
    
5. **Render:** ReportLab processes the summary strings into a publication-ready PDF asset.
    
      
    
6. **Publish:** The execution runtime dispatches the PDF payload through the configured webhook or email relay service.
    

## 5. Technology Stack Summary

|**Layer**|**Component**|**Purpose**|
|---|---|---|
|**Scraping**|Firecrawl API|Clean Markdown extraction from complex web structures|
|**Concurrency**|Python `asyncio`|Concurrent network requests and execution speedup|
|**Database & Vector**|Supabase (`pgvector`)|Unified relational storage and vector similarity search|
|**LLM Inference**|OpenAI / Anthropic API|Diff analysis and qualitative market insight generation|
|**Document Generation**|ReportLab|Programmatic layout and executive PDF compilation|
|**Execution**|Docker & GitHub Actions|Containerized environment isolation and cron scheduling|
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[sysrules]]
10. 