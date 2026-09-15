# Technical Documentation: Intelligent LLM Orchestration in Competepulse

## 1. Overview

The **Intelligent LLM Orchestration** layer serves as the cognitive core of **Competepulse**. While the scraping layer gathers raw text and the vector database tracks historical context, the orchestration layer is responsible for reasoning. It takes disparate pieces of information—such as newly scraped markdown, historical site snapshots, and semantic vector diffs—and transforms them into structured, actionable business intelligence.

  

This document details how the orchestration layer is architected, how state is managed, and how deterministic outputs are enforced using modern agentic frameworks.

  

## 2. Core Architecture & Framework Selection

To manage multi-step reasoning without getting trapped in infinite agent loops, Competepulse uses **LangGraph** (or **CrewAI**) to enforce a structured **Directed Acyclic Graph (DAG)** workflow.

  

Unlike free-form autonomous agents that can wander off-task, a structured graph ensures that the LLM operates inside a strict pipeline:

  

1. **Injest & Retrieve:** Gather current markdown and fetch historical vectors from Supabase.
    
      
    
2. **Diff & Filter:** Isolate semantic changes using vector similarity thresholds.
    
      
    
3. **Analyze & Synthesize:** Pass the filtered context to the LLM for deep business analysis.
    
      
    
4. **Format & Validate:** Ensure the LLM output conforms to a strict schema required by the PDF generation engine.
    
      
    

## 3. Step-by-Step Orchestration Workflow

```
[State Initialization] 
          │
          ▼
[Node 1: Scrape & Embed] ──► Query Supabase pgvector ──► [Node 2: Semantic Diff Evaluation]
                                                                      │
                                                                      ▼
[Node 4: Report Payload Ready] ◄── [Node 3: LLM Synthesis & Structuring]
```

### Step 1: State Initialization & Schema

The workflow relies on a shared `AgentState` object (typed using Pydantic or TypedDict) that travels through every node in the graph.

  

Python

```
from typing import TypedDict, List, Dict, Optional

class CompetepulseState(TypedDict):
    domain: str
    raw_scraped_pages: Dict[str, str]      # e.g., {"/pricing": "# Pricing..."}
    vector_matches: List[Dict]             # Historical context fetched from Supabase
    identified_shifts: List[str]           # Filtered meaningful changes
    llm_structured_insights: Optional[Dict]# Final categorized JSON output
    error_log: List[str]
```

### Step 2: The Diff & Filter Node

Before blindly sending all text to an expensive LLM, the orchestration layer uses vector distance metrics to filter out noise.

  

- If a pricing page has a cosine similarity score of `0.99` compared to last week, the node flags it as "No Change" and skips deep analysis for that specific page.
    
      
    
- If the score drops below a set threshold (e.g., `< 0.88`), it flags the chunk as a **significant delta** and packages it alongside the historical baseline chunk for the LLM.
    
      
    

### Step 3: LLM Synthesis & Prompt Engineering

Once meaningful deltas are isolated, the orchestrator invokes a frontier model (such as `GPT-4o` or `Claude 3.5 Sonnet`) with a specialized persona and strict constraints.

  

#### System Prompt Blueprint:

> _"You are an elite enterprise market intelligence analyst. Your job is to review competitor website changes and write an objective, high-impact executive brief. You will be provided with historical text snippets and new text snippets. Ignore superficial layout changes, minor typos, or CSS updates. Focus exclusively on strategic shifts: pricing tier modifications, feature gating changes, new product launches, and legal/terms alterations."_
> 
>   

### Step 4: Structured Output Enforcing (Pydantic Integration)

To prevent the LLM from returning messy, unstructured paragraphs that would break the PDF generation script, the orchestration layer forces **Structured Outputs** using Pydantic models.

  

Python

```
from pydantic import BaseModel, Field

class PricingShift(BaseModel):
    tier_name: str = Field(description="Name of the pricing tier, e.g., Pro, Enterprise")
    change_type: str = Field(description="Price Increase, Price Decrease, Feature Added, or Feature Removed")
    details: str = Field(description="Detailed explanation of what changed")

class ExecutiveBriefSchema(BaseModel):
    executive_summary: str = Field(description="High-level 3-sentence summary of all competitor movements.")
    pricing_shifts: List[PricingShift]
    product_launches: List[str] = Field(description="List of new products or features discovered.")
    terms_updates: List[str] = Field(description="Critical legal or data policy updates.")
```

---## 4. Error Handling and Fallbacks

  

Autonomous workflows running on weekly schedules must be resilient to external failures:

  

- **LLM Rate Limits / Timeouts:** The graph incorporates exponential backoff decorators using `tenacity` around LLM invocation nodes.
    
      
    
- **Malformed JSON Responses:** If an LLM fails to output valid JSON matching the Pydantic schema, a validation catch-node automatically feeds the error message back to the LLM with the instruction: _"Your previous output failed schema validation. Correct the formatting and try again."_
    
      
    

## 5. Summary of Benefits

- **Cost Efficiency:** By filtering content via `pgvector` _before_ hitting the LLM, token consumption is reduced by only analyzing pages that actually changed.
    
      
    
- **Deterministic Reliability:** Pydantic schemas guarantee that downstream tools (like ReportLab) always receive clean, predictable data structures.
    
      
    
- **Auditability:** Every state transition is logged, allowing developers to trace why a specific executive insight was generated from a raw markdown string.
  
  
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
   [[intellirules]]
10. 
11. [[Programmatic PDF Brief Generation]]
12. 
13. 