# Vector-Backed Change Detection: Detailed Architecture & Implementation Guide

Vector-backed change detection is the core intelligence engine of **Competepulse**. Instead of relying on brittle line-by-line text comparisons (like standard `git diff` tools, which break when website layouts, HTML tags, or whitespace change), this approach uses **semantic similarity** to understand the _meaning_ of content over time.

  

## 1. Why Traditional Diffing Fails on Websites

If a competitor changes their pricing page from:

  

> _"Pro Plan: $49/month with 5 included users."_
> 
>   

to:

  

> _"Pro Plan is now $49 a month, and you get 5 team members included."_
> 
>   

- **A traditional text diff** sees completely different strings because the words, order, and punctuation changed. It flags the entire block as modified, creating noise.
    
      
    
- **Vector-backed change detection** looks at the underlying semantics and recognizes that the core meaning, price, and user limits are identical, filtering out superficial wording shifts.
    
      
    

## 2. The Core Workflow

The change detection pipeline operates in four logical steps every time a competitor's domain is scraped:

  

1. **Ingestion & Text Extraction:** Firecrawl strips away all website clutter (CSS, JavaScript, navigation bars) and returns clean, structured Markdown.
    
      
    
2. **Chunking & Vectorization:** The Markdown is split into logical blocks (paragraphs or sections) and passed to an embedding model to generate numerical vectors.
    
      
    
3. **Similarity Query (`pgvector`):** The new vectors are queried against historical snapshots stored in Supabase to find the closest semantic matches from previous weeks.
    
      
    
4. **Distance & Threshold Analysis:** The system measures the distance (similarity score) between old and new chunks. If a score falls below a specific threshold, it is isolated as a _meaningful business shift_.
    
      
    

## 3. Database Schema Design (Supabase + `pgvector`)

To support vector search and history tracking, the database requires a dedicated table structure.

  

### SQL Setup

Run this migration in your Supabase SQL Editor to enable the vector extension and create the snapshots table:

  

SQL

```
-- 1. Enable the pgvector extension (if not already enabled)
create extension if not exists vector;

-- 2. Create the table to store competitor page snapshots
create table competitor_snapshots (
    id bigserial primary key,
    domain text not null,
    url text not null,
    content text not null,          -- The raw markdown chunk
    embedding vector(1536),         -- 1536 dimensions for OpenAI text-embedding-3-small
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- 3. Create an index for fast vector similarity search (Cosine Distance)
create index on competitor_snapshots using ivfflat (embedding vector_cosine_ops)
with (lists = 100);
```

## 4. Supabase RPC Function for Similarity Matching

To compare new text against historical snapshots, you need a PostgreSQL function (RPC) that the Python script can call directly. This function searches for past chunks belonging to the same URL.

  

SQL

```
create or replace function match_snapshots (
  query_embedding vector(1536),
  match_threshold float,
  match_count int,
  target_url text
)
returns table (
  id bigint,
  content text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    competitor_snapshots.id,
    competitor_snapshots.content,
    1 - (competitor_snapshots.embedding <=> query_embedding) as similarity
  from competitor_snapshots
  where competitor_snapshots.url = target_url
    and 1 - (competitor_snapshots.embedding <=> query_embedding) > match_threshold
  order by competitor_snapshots.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

## 5. Python Implementation

This script demonstrates how the agent processes scraped text, generates embeddings, checks for historical changes via Supabase, and flags differences for the LLM.

  

Python

```
import os
import openai
from supabase import create_client

# Initialize clients
supabase = create_client(os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY"))
openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_embedding(text: str) -> list[float]:
    """Generates a vector embedding using OpenAI's embedding model."""
    response = openai.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def analyze_page_changes(domain: str, url: str, new_markdown_content: str):
    """
    Chunks new content, compares it against historical vectors in Supabase,
    stores the new snapshot, and returns meaningful changes.
    """
    # 1. Chunk content by paragraphs or logical sections
    chunks = [chunk.strip() for chunk in new_markdown_content.split("\n\n") if chunk.strip()]
    
    changes_detected = []

    for chunk in chunks:
        # 2. Generate vector embedding for the current chunk
        embedding = get_embedding(chunk)
        
        # 3. Query Supabase for the closest historical match (Threshold: 0.85)
        # If similarity is high, the text hasn't meaningfully changed.
        # If similarity is low or no match is found, something is new/changed.
        response = supabase.rpc(
            'match_snapshots',
            {
                'query_embedding': embedding,
                'match_threshold': 0.82,
                'match_count': 1,
                'target_url': url
            }
        ).execute()
        
        matches = response.data
        
        if not matches:
            # No matching semantic chunk found -> Major change or brand new content
            changes_detected.append({
                "type": "NEW_OR_MODIFIED",
                "content": chunk
            })
        else:
            # Match found, check similarity score explicitly if needed
            best_match = matches[0]
            if best_match['similarity'] < 0.85:
                changes_detected.append({
                    "type": "SHIFTED_MEANING",
                    "old_content": best_match['content'],
                    "new_content": chunk,
                    "similarity": best_match['similarity']
                })

        # 4. Save the current chunk snapshot into Supabase for future tracking
        supabase.table("competitor_snapshots").insert({
            "domain": domain,
            "url": url,
            "content": chunk,
            "embedding": embedding
        }).execute()

    return changes_detected
```

## 6. How the LLM Uses These Results

Once the Python script isolates the items where `type` is `NEW_OR_MODIFIED` or `SHIFTED_MEANING`, it compiles them into a structured payload and sends them to the LLM (e.g., GPT-4o).

  

### Example LLM Prompt Structure:

> _"You are an elite corporate intelligence analyst. Below are the semantic shifts detected on Competitor X's pricing and terms pages over the last 7 days. Ignore minor edits. Summarize only strategic business shifts (e.g., price modifications, removed features, updated liabilities) into bullet points for an executive brief."_
> 
>   

This ensures the final PDF report contains high-value strategic takeaways rather than raw, unorganized website text dumps.


. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[Vector-Backed Change Detection]]
10. 