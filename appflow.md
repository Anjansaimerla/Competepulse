# App Flow Document: Competepulse

## 1. Project Overview

**Competepulse** is an autonomous market research and competitor scraping agent. It takes a target competitor's domain, asynchronously scrapes key pages (pricing, blog/changelog, terms of service) using **Firecrawl**, compares the new content against historical data stored in **Supabase (`pgvector`)** to detect meaningful shifts, and compiles the insights into a professional executive PDF brief using **ReportLab**. The entire pipeline runs on autopilot via scheduled automation.

  

## 2. System Architecture & Tech Stack

- **Language & Orchestration:** Python (`asyncio`, LangGraph or a structured state machine)
    
      
    
- **Scraping Layer:** Firecrawl API (with fallback handling)
    
      
    
- **Storage & Vector Database:** Supabase (`pgvector` extension for semantic change detection)
    
      
    
- **LLM & Analysis:** OpenAI / Anthropic model (for diff summarization and insight extraction)
    
      
    
- **Reporting Engine:** ReportLab (for programmatic PDF compilation)
    
      
    
- **Automation & Distribution:** GitHub Actions (cron schedule) + Slack Webhook / SendGrid API
    
      
    

## 3. High-Level End-to-End Flow

```
[Trigger: Manual or Scheduled GitHub Action]
                     │
                     ▼
             [Initialize State]
                     │
                     ▼
         [Step 1: Async Scraping] ──(Firecrawl API)──► Fetch Pricing, Blog, Terms
                     │
                     ▼
      [Step 2: Vector Chunking & Storage] ──(Supabase pgvector)──► Compare & Save Snapshot
                     │
                     ▼
         [Step 3: LLM Intelligence] ──(OpenAI/Anthropic)──► Synthesize Diffs & Summarize
                     │
                     ▼
     [Step 4: PDF Generation Engine] ──(ReportLab)──► Compile Executive Brief PDF
                     │
                     ▼
      [Step 5: Distribution & Alert] ──(Slack / Email)──► Deliver Brief to User
```

## 4. Step-by-Step Application Flow

### Step 0: Trigger & State Initialization

- **Trigger:** A weekly cron job (e.g., every Monday at 6:00 AM) or a manual script execution.
    
      
    
- **State Object:** An initialized workflow state container is created to track data as it moves through the pipeline:
    
      
    
    JSON
    
    ```
    {
      "domain": "competitor.com",
      "scraped_data": {},
      "vector_diffs": {},
      "llm_analysis": null,
      "pdf_path": null
    }
    ```
    

### Step 1: Ingestion & Asynchronous Scraping

- **Input:** Target domain name (e.g., `stripe.com`).
    
      
    
- **Process:**
    
      
    - The agent constructs target endpoints: `/pricing`, `/blog`, and `/terms`.
        
          
        
    - Using Python’s `asyncio`, it fires concurrent requests to the **Firecrawl API**.
        
          
        
    - Firecrawl bypasses anti-bot measures, renders JavaScript, and returns clean Markdown.
        
          
        
- **State Update:** `scraped_data` dictionary is populated with the Markdown text for each page.
    
      
    

### Step 2: Vector Storage & Semantic Diffs (Supabase)

- **Process:**
    
      
    - The raw Markdown text chunks are passed through an embedding model to generate numerical vectors.
        
          
        
    - The agent connects to **Supabase** and queries the `competitor_snapshots` table via `pgvector` (`match_snapshots`RPC function) to fetch the previous week's text snapshot.
        
          
        
    - It compares the vector embeddings to measure semantic distance. Minor layout or text adjustments are ignored, while meaningful shifts (pricing adjustments, feature gating changes, policy updates) are flagged.
        
          
        
    - The current week's text, timestamp, and vector embedding are saved into Supabase for future comparisons.
        
          
        
- **State Update:** `vector_diffs` object is updated with highlighted changes.
    
      
    

### Step 3: LLM Intelligence & Analysis

- **Process:**
    
      
    - The diff summaries and historical context are passed into an LLM (e.g., GPT-4o).
        
          
        
    - The prompt instructs the model to act as an elite market intelligence analyst, filtering out noise and summarizing key business impacts (e.g., _“Pro plan increased by $10; new enterprise tier introduced”_).
        
          
        
    - The LLM outputs a structured layout of insights.
        
          
        
- **State Update:** `llm_analysis` is populated with structured text and key takeaways.
    
      
    

### Step 4: Executive PDF Report Compilation

- **Process:**
    
      
    - The application initializes **ReportLab** (`SimpleDocTemplate`) with standard page settings and styling profiles (`ParagraphStyle`).
        
          
        
    - It loops through the LLM analysis data, dynamically structuring the title, executive summary, pricing change tables, and bulleted takeaways into the document story array.
        
          
        
    - `doc.build()` compiles and saves the file locally as an executive brief PDF (e.g., `executive_brief.pdf`).
        
          
        
- **State Update:** `pdf_path` is updated with the file destination path.
    
      
    

### Step 5: Automated Distribution & Alert

- **Process:**
    
      
    - The script reads the generated PDF file from the local environment.
        
          
        
    - It triggers a **Slack Webhook** to post a formatted alert message with the attached PDF directly to a team workspace channel, **or** uses **SendGrid** to email the report to stakeholders.
        
          
        
- **Completion:** The workflow terminates successfully on autopilot.
  
  3. [[rules]]
4. [[systemarchitecture]]
5. [[overview]]
6. [[prd]]
7. [[trd]]
8. 