## Automated Multi-Page Ingestion: Architecture & Operational Rules

The ingestion engine serves as the sensory layer for **Competepulse**. Its primary job is to bypass anti-scraping blocks, extract clean semantic content from dynamic websites, and feed that data downstream into the vector storage and analysis pipelines.

  

### 1. Target Endpoint Routing & Categorization

The ingestion pipeline does not crawl a website blindly. It targets specific sub-routes designed to capture different pillars of a competitor's business strategy:

  

- **The Pricing Route (`/pricing`):** Captures changes to tier structures, feature gating, numeric price points, and enterprise-tier thresholds.
    
      
    
- **The Product Route (`/blog` or `/changelog`):** Captures recent product launches, feature releases, and technical documentation updates.
    
      
    
- **The Legal Route (`/terms` or `/privacy`):** Captures policy shifts, data usage alterations, or changes to service level agreements (SLAs).
    
      
    

### 2. Execution & Scraping Rules (The Firecrawl Layer)

To prevent scraping failures caused by heavy JavaScript rendering or aggressive bot-detection blocks, ingestion follows strict protocol:

  

- **Markdown Conversion Rule:** Raw HTML is never sent to the LLM or vector store. The scraping engine must convert all retrieved pages directly into clean, structured **Markdown** to strip out layout noise, CSS wrappers, and advertisement scripts.
    
      
    
- **Asynchronous Concurrency Rule:** Pages belonging to a single competitor domain must never be crawled sequentially. The agent utilizes Python’s `asyncio` loop to fire requests to the pricing, blog, and terms pages simultaneously, reducing per-target ingestion time to under five seconds.
    
      
    
- **Fallback Protocol:** If the primary headless rendering API encounters a rate limit or a 403 Forbidden error, the script drops back to a secondary headless browser instance (such as Playwright with rotated user agents) before failing the run.
    
      
    

### 3. Data Cleansing & Normalization Rules

Before raw Markdown is pushed to Supabase for embedding, it must undergo sanitization:

  

- **Boilerplate Stripping:** Standard navigation bars, footers, cookie banners, and dynamic copyright dates must be filtered out. Only the core content payload of the page is retained to prevent false positives in vector similarity comparisons.
    
      
    
- **Chunking Strategy:** Large Markdown files are split into logical semantic blocks (typically 500-token chunks with 50-token overlaps) to ensure the vector database can pinpoint exact paragraphs where pricing or feature changes occurred.
    
      
    

### 4. Error Handling & State Reporting

- **Timeouts & Retries:** Individual page requests enforce a strict 15-second timeout with an automatic single-retry policy.
    
      
    
- **Graceful Degradation:** If a specific page (e.g., the blog) is down or missing, the ingestion pipeline must log a non-fatal warning, proceed with the remaining successfully scraped pages (pricing and terms), and pass an incomplete status flag into the workflow state.
  
  
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[multi page ingestion]]
10. 