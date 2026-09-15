## Overview

The **Automated Multi-Page Ingestion** module serves as the primary data collection engine for **Competepulse**. Its core objective is to autonomously navigate target competitor websites, bypass modern anti-scraping protections, and extract clean, structured text data from critical pages without manual human intervention.

  

Instead of relying on brittle, traditional HTML scrapers that break whenever a company updates its website layout or CSS classes, this module leverages modern headless API tools to convert dynamic web pages straight into LLM-ready Markdown.

  

## Core Pages Tracked

To capture a complete picture of a competitor's business strategy, the ingestion engine targets three distinct categories of web pages during every scheduled run:

  

- **Pricing & Packaging (`/pricing`):** Captures changes to tier structures, price points, feature gating, and hidden enterprise tiers.
    
      
    
- **Changelogs & Product Blogs (`/blog` or `/changelog`):** Monitors newly launched features, product updates, and engineering pivots.
    
      
    
- **Terms of Service & Privacy (`/terms` or `/privacy`):** Flags legal modifications, data usage policy adjustments, and shifts in enterprise liabilities.
    
      
    

## Technology Stack

- **Firecrawl API:** Handles JavaScript rendering, headless browser navigation, and automatic conversion of messy HTML into clean Markdown.
    
      
    
- **Python `asyncio`:** Manages concurrent network requests so the agent crawls all target pages simultaneously rather than one by one.
    
      
    
- **Requests / HTTPX:** Manages API communication with error handling and retry mechanisms.
    
      
    

## Step-by-Step Execution Workflow

1. **Target Initialization:** The script receives a target domain name (e.g., `competitor.com`) from the workflow orchestrator.
    
      
    
2. **Endpoint Construction:** The engine automatically builds the target URLs for pricing, blogs, and terms based on standard URL paths.
    
      
    
3. **Asynchronous Dispatch:** Python fires concurrent API requests to Firecrawl for all target pages at the exact same time.
    
      
    
4. **Markdown Conversion:** Firecrawl renders any heavy JavaScript elements, strips out useless code (like CSS, navigation bars, and footers), and returns only the core textual content formatted as clean Markdown.
    
      
    
5. **State Hand-off:** The collected Markdown strings are packaged into a structured dictionary and pushed directly into the workflow's shared **state** container for vector storage and analysis.
    
      
    

## Python Implementation Example

The following script demonstrates how the ingestion engine concurrently scrapes multiple pages using Firecrawl and `asyncio`:

  

Python

```
import asyncio
import os
from firecrawl import FirecrawlApp

async def scrape_competitor_pages(domain: str) -> dict:
    """
    Asynchronously crawls key competitor pages and returns clean Markdown.
    """
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    app = FirecrawlApp(api_key=api_key)
    
    # Define standard target paths
    target_endpoints = {
        "pricing": f"https://{domain}/pricing",
        "changelog": f"https://{domain}/blog",
        "terms": f"https://{domain}/terms"
    }
    
    async def fetch_page(url: str):
        try:
            # Run the synchronous Firecrawl SDK call in a separate thread to prevent blocking async loop
            response = await asyncio.to_thread(
                app.scrape_url, 
                url, 
                {'formats': ['markdown'], 'timeout': 30000}
            )
            return response.get('markdown', '')
        except Exception as e:
            print(f"Failed to scrape {url}: {str(e)}")
            return None

    # Fire requests concurrently
    tasks = [fetch_page(url) for url in target_endpoints.values()]
    results = await asyncio.gather(*tasks)
    
    # Map results back to their respective categories
    scraped_data = {
        key: content for key, content in zip(target_endpoints.keys(), results) if content is not None
    }
    
    return scraped_data
```

## Error Handling & Resiliency

- **Graceful Fallbacks:** If a competitor does not have a `/changelog` page or returns a 404 error on `/terms`, the script catches the exception individually without crashing the entire pipeline.
    
      
    
- **Timeouts & Rate Limiting:** Built-in request timeouts prevent the agent from hanging indefinitely if a competitor's web server is experiencing an outage.
    
      
    
- **Cloudflare / Anti-Bot Bypass:** Because Firecrawl routes requests through managed headless browser infrastructure with rotating proxies, the agent avoids getting blocked or hit with CAPTCHAs.
  
  
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
10. [[Vector-Backed Change Detection]]
11. [[multirules]]
12. 