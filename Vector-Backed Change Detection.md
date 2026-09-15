# Technical Documentation: Vector-Backed Change Detection in Competepulse

## 1. Executive Summary

In traditional web monitoring, detecting changes on a competitor's website relies on string matching or HTML diffing (e.g., comparing raw HTML tags or literal strings line by line). This approach fails in modern web development because minor updates—such as CSS restyling, updated timestamps, invisible script changes, or rephrased sentences—trigger false positives.

  

**Competepulse** solves this using **Vector-Backed Change Detection**. By converting text content into numerical embeddings and storing them in **Supabase** via the `pgvector` extension, the agent measures _semantic similarity_ rather than literal text matching. This ensures that the system only flags meaningful business shifts—such as price increases, feature gating, or policy alterations—while ignoring superficial layout edits.

  

## 2. Core Architecture & Workflow

The change detection pipeline follows a 5-step lifecycle every time a competitor domain is scraped:

  

```
[Firecrawl Markdown] 
        │
        ▼
[Text Chunking Engine] 
        │
        ▼
[Embedding Model (OpenAI)] ──► [Generate Vectors]
                                      │
       ┌──────────────────────────────┴──────────────────────────────┐
       ▼                                                             ▼
[Supabase (pgvector)]                                     [Vector Similarity Search]
(Store new snapshot)                                  (Compare against previous snapshot)
       │                                                             │
       └──────────────────────────────┬──────────────────────────────┘
                                      ▼
                       [Diff Threshold Evaluation]
                       ├── Score >= 0.85: No significant change
                       └── Score <  0.85: Significant change (Flagged for LLM)
```

1. **Extraction:** Firecrawl returns the target page (e.g., `/pricing`) as clean Markdown text.
    
      
    
2. **Chunking:** The Markdown text is split into semantic chunks (paragraphs or sections) so micro-changes can be isolated without drowning in whole-page noise.
    
      
    
3. **Embedding:** Each chunk is passed through an embedding model (e.g., OpenAI `text-embedding-3-small`) to convert text into a high-dimensional vector array (e.g., 1536 dimensions).
    
      
    
4. **Vector Similarity Query:** The system queries Supabase using cosine distance to find the most historically relevant matching chunk from the previous week's crawl.
    
      
    
5. **Threshold Evaluation:** If the similarity score drops below a predefined threshold (e.g., `0.85`), the system flags the text as modified and forwards it to the LLM orchestration layer for executive summarization.
    
      
    

## 3. Database Schema Design (Supabase / PostgreSQL)

To support vector-backed change detection, Supabase requires the `pgvector` extension and a structured table to hold text chunks, metadata, and embeddings.

  

### SQL Setup Script

Execute this schema in your Supabase SQL Editor:

  

SQL

```
-- Step 1: Enable the pgvector extension
create extension if not exists vector;

-- Step 2: Create the competitor snapshots table
create table competitor_snapshots (
    id bigserial primary key,
    domain text not null,
    page_type text not null, -- e.g., 'pricing', 'terms', 'blog'
    content text not null,   -- The raw Markdown text chunk
    embedding vector(1536),  -- Vector embedding dimension matching OpenAI's text-embedding-3-small
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Step 3: Create an index for fast vector similarity search (Cosine Distance)
create index on competitor_snapshots using ivfflat (embedding vector_cosine_ops)
with (lists = 100);
```

## 4. Implementation Code

Below is the Python implementation handling chunking, embedding generation, database storage, and similarity matching.

  

### Prerequisites

Install required dependencies:

  

Bash

```
pip install supabase openai tiktoken
```

### Python Module (`vector_detector.py`)

Python

```
import os
from openai import OpenAI
from supabase import create_client

# Initialize clients
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
supabase = create_client(
    os.environ.get("SUPABASE_URL"), 
    os.environ.get("SUPABASE_KEY")
)

def generate_embedding(text: str) -> list[float]:
    """Converts a text chunk into a vector embedding using OpenAI."""
    response = openai_client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def chunk_text(text: str, max_chars: int = 1000) -> list[str]:
    """Splits large Markdown text into manageable semantic blocks."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chars:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            chunks.append(current_chunk)
            current_chunk = para
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def process_and_detect_changes(domain: str, page_type: str, raw_markdown: str):
    """
    Processes new page data, checks against historical vectors in Supabase,
    identifies changes, and stores the new snapshot.
    """
    chunks = chunk_text(raw_markdown)
    flagged_changes = []

    for chunk in chunks:
        # 1. Generate vector embedding for the current chunk
        embedding = generate_embedding(chunk)
        
        # 2. Query Supabase for the closest historical match using pgvector RPC
        # (Assuming a custom Postgres function 'match_snapshots' is registered)
        match_response = supabase.rpc(
            'match_snapshots',
            {
                'query_embedding': embedding,
                'match_threshold': 0.85, 
                'match_count': 1,
                'target_domain': domain,
                'target_page': page_type
            }
        ).execute()
        
        matches = match_response.data
        
        if not matches:
            # Brand new content or content changed past threshold
            flagged_changes.append({
                "type": "new_or_modified",
                "content": chunk
            })
        else:
            # Evaluate similarity score returned by pgvector
            best_match = matches[0]
            if best_match['similarity'] < 0.85:
                flagged_changes.append({
                    "type": "content_shift",
                    "previous_content": best_match['content'],
                    "current_content": chunk,
                    "similarity_score": best_match['similarity']
                })

        # 3. Save the new snapshot into Supabase for future tracking
        supabase.table("competitor_snapshots").insert({
            "domain": domain,
            "page_type": page_type,
            "content": chunk,
            "embedding": embedding
        }).execute()

    return flagged_changes
```

## 5. Postgres RPC Function for Similarity Matching

To allow Supabase to execute vector distance calculations efficiently, execute the following function definition in your Supabase database:

SQL

```
create or replace function match_snapshots (
  query_embedding vector,
  match_threshold float,
  match_count int,
  target_domain text,
  target_page text
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
  where competitor_snapshots.domain = target_domain
    and competitor_snapshots.page_type = target_page
    and 1 - (competitor_snapshots.embedding <=> query_embedding) > match_threshold
  order by competitor_snapshots.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

## 6. Advantages Over Traditional Approaches

|**Feature**|**Traditional String/HTML Diffing**|**Vector-Backed Change Detection (Competepulse)**|
|---|---|---|
|**Handling Layout Resets**|Fails (flags CSS/class updates as changes).|Ignores layout updates; focuses strictly on text semantics.|
|**Rephrasing Detection**|Flags minor sentence restructuring as heavy modifications.|Recognizes that the _underlying meaning_ is identical.|
|**Noise Filtering**|Easily distracted by dynamic scripts, ads, or timestamps.|Bypasses noise through semantic chunking and thresholds.|
|**Historical Intelligence**|Limited to direct "Before vs. After" file comparisons.|Enables multi-week trend analysis via deep vector space mapping.|
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
10. [[vecrules]]
11. [[Intelligent LLM Orchestration]]
12. 