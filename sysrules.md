## Competepulse: System Architecture & Engineering Rules

This document establishes the architectural standards, design patterns, and engineering constraints for the Competepulse autonomous market intelligence platform. All modules must adhere to these specifications to ensure horizontal scalability, fault tolerance, and clean state tracking.

  

### 1. High-Level Architecture & Layering

Competepulse operates as a decoupled, event-driven agentic pipeline divided into four isolated layers:

  

- **Ingestion Layer:** Handles asynchronous web crawling via Firecrawl and fallback headless scrapers. Employs rate-limiting and rotating user-agents to prevent IP bans.
    
      
    
- **Storage & Persistence Layer:** Utilizes Supabase (PostgreSQL + `pgvector`) for storing raw markdown snapshots, structured telemetry, and vector embeddings.
    
      
    
- **Intelligence & Orchestration Layer:** Utilizes a state machine pattern (via LangGraph or custom async state loops) to route scraped data through text chunking, embedding generation, and LLM-driven semantic diff analysis.
    
      
    
- **Presentation & Distribution Layer:** Programmatically compiles analysis payloads into professional executive briefs using ReportLab and dispatches them via webhook (Slack) or email (SendGrid).
    
      
    

### 2. Technology Stack Enforcement

- **Language:** Python 3.11+ (Strict type hinting required across all modules).
    
      
    
- **Asynchronous Engine:** `asyncio` for non-blocking network I/O across multi-page crawls.
    
      
    
- **Database & Vector Store:** Supabase PostgreSQL instance with the `pgvector` extension enabled. No secondary vector databases (e.g., Pinecone) are permitted.
    
      
    
- **Scraping Engine:** Firecrawl API primary; Playwright/BeautifulSoup secondary fallback for restricted endpoints.
    
      
    
- **Document Engine:** ReportLab for vector-based PDF compilation. No HTML-to-PDF conversion engines that rely on external binary renderers unless explicitly approved.
    
      
    
- **Containerization:** Docker multi-stage builds to minimize image footprint and secure runtime dependencies.
    
      
    

### 3. Data Pipeline & State Management Specifications

- **Immutable State Pattern:** Every workflow execution instantiates a strict state dictionary or Pydantic model. Steps must read from and write back to this shared state without side effects on external global variables.
    
      
    
- **Idempotency:** Crawl and analysis tasks must be safe to retry. If a weekly cron job fails midway, restarting the container must resume or safely re-evaluate without creating duplicate database records or malformed reports.
    
      
    
- **Chunking Standards:** Text extracted via Firecrawl must be split into semantic chunks (maximum 512 tokens with a 64-token overlap) prior to vector embedding generation to optimize LLM context retrieval.
    
      
    

### 4. Database & Vector Schema Rules

- **Table Normalization:**
    
      
    - `competitors`: Stores domain metadata, target URLs, and monitoring frequencies.
        
          
        
    - `competitor_snapshots`: Stores raw markdown content, vector embeddings (`vector(1536)` for OpenAI text-embedding-3-small), and timestamps.
        
          
        
- **Similarity Thresholds:** Vector similarity searches (`match_snapshots`) must enforce a default distance/similarity cutoff of $\ge 0.85$ to filter out layout-only changes and surface semantic business shifts.
    
      
    
- **Indexing:** HNSW or IVFFlat indexes must be configured on vector columns to ensure sub-second similarity lookups as historical data grows.
    
      
    

### 5. Deployment, Scheduling & Error Resilience

- **Execution Environment:** Runs inside an isolated Docker container orchestrated via GitHub Actions cron triggers (default: weekly, Mondays at 06:00 UTC).
    
      
    
- **Graceful Degradation:** If a specific competitor subpage (e.g., `/terms`) fails to load or times out, the scraping agent must log the exception, proceed with available pages (`/pricing`, `/blog`), and flag the partial data state to the LLM analyzer.
    
      
    
- **Secret Management:** All API keys (Firecrawl, Supabase, OpenAI/Anthropic, SendGrid/Slack Webhooks) must be injected exclusively via environment variables (`.env` locally, GitHub Secrets in production). Hardcoded credentials will fail code review pipelines.
  
  . [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
10. 