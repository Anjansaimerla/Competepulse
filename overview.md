Building this autonomous market research agent comes down to breaking it into four distinct layers: ingestion, storage, intelligence, and reporting.

  

### Step 1: Set Up the Ingestion Pipeline (Scraping)

The goal here is to automatically pull raw data from a competitor's website without getting blocked by anti-bot protections.

  

1. **Target Identification:** Define the core pages you want to track for any given company:
    
      
    - `/pricing` (to catch tier changes, feature gating, or price hikes)
        
          
        
    - `/blog` or `/changelog` (to catch new product launches and feature updates)
        
          
        
    - `/terms` or `/privacy` (to catch legal, data usage, or policy shifts)
        
          
        
2. **Integration with Firecrawl:** Instead of writing brittle custom Selenium or BeautifulSoup scrapers that break whenever a CSS class changes, use the **Firecrawl API**. It handles rendering JavaScript and converts messy HTML straight into clean **Markdown**.
    
      
    
3. **Asynchronous Execution:** Use Python's `asyncio` module so the agent doesn't crawl pages one by one sequentially. It fires requests to the pricing page, blog, and terms page simultaneously, cutting execution time down to seconds.
    
      
    

### Step 2: Implement Vector Storage & Change Detection (Supabase + pgvector)

A standard database would just overwrite old text with new text. To know what _changed_, you need a historical record with vector embeddings.

  

1. **Chunking Content:** Take the Markdown text returned by Firecrawl and split it into manageable semantic chunks (e.g., paragraph by paragraph or section by section).
    
      
    
2. **Generating Embeddings:** Pass these text chunks through an embedding model (like OpenAI's text-embedding-3-small) to convert the text into numerical vectors.
    
      
    
3. **Storing in Supabase (`pgvector`):** Save the domain name, raw text, timestamp, and the vector embedding into a Supabase table configured with the `pgvector` extension.
    
      
    
4. **Semantic Diffs:** When a new crawl happens this week, the agent queries Supabase using vector similarity (`match_snapshots`) to compare the new text against last week's text. If the similarity score drops below a certain threshold (e.g., 0.85), the agent flags it as a _meaningful change_ rather than just a minor typo fix.
    
      
    

### Step 3: Orchestrate the LLM Analysis

Now that you have isolated what changed, you need an LLM to read the diffs and write human-like executive insights.

  

1. **Workflow Framework:** Use **LangGraph** or **CrewAI** to orchestrate the agent's state.
    
      
    - _State 1:_ Scraped data retrieved.
        
          
        
    - _State 2:_ Vector database queried for historical context.
        
          
        
    - _State 3:_ LLM prompt assembled containing both old data and new data.
        
          
        
2. **Prompt Engineering:** Feed the differences to an LLM (like GPT-4o or Claude 3.5 Sonnet) with a strict prompt: _"You are an elite market intelligence analyst. Compare the following old pricing page data with the new crawl. Highlight any price increases, new feature restrictions, or hidden enterprise tiers."_
    
      
    
3. **Structured Output:** Force the LLM to return a structured JSON object containing sections like `Pricing Shifts`, `Product Launches`, and `Terms & Conditions Updates`.
    
      
    

### Step 4: Programmatic PDF Report Generation

Instead of dumping raw text into a chat window, the agent compiles the final analysis into a polished, shareable document.

  

1. **ReportLab Setup:** Initialize a `SimpleDocTemplate` in Python using standard letter page sizes and clean margins.
    
      
    
2. **Styling & Typography:** Define professional typographic styles (`ParagraphStyle`) for headers, body text, and callout boxes so the output looks like it was designed by a human analyst.
    
      
    
3. **Document Assembly:** Loop through the LLM's structured JSON output, dynamically adding title blocks, spacing, section headers, and bulleted takeaways into the document story array, then call `doc.build(story)` to output the final PDF file.
    
      
    

### Step 5: Automating & Deploying

Once the local script works, you need to make it run on autopilot.

  

1. **Containerization:** Wrap the entire Python script and its dependencies into a Docker container.
    
      
    
2. **Scheduling:** Set up a **GitHub Actions workflow** with a cron schedule (e.g., every Monday at 6:00 AM) or deploy it as a Supabase Edge Function / AWS Lambda.
    
      
    
3. **Distribution:** Add a final step to the script that takes the generated PDF and pushes it directly to a Slack channel via webhook or emails it to your executive team using an API like SendGrid.
   
   
   [[prd]]
1. [[trd]]
2. [[appflow]]
3. [[rules]]
4. [[systemarchitecture]]
