## Core Objective

Intelligent LLM Orchestration acts as the analytical brain of **Competepulse**. It bridges the gap between raw web data and executive decision-making by transforming unstructured text diffs into structured, high-value business insights without human intervention.

  

## 1. The Core Rules of LLM Orchestration in Competepulse

### Rule 1: Separation of Concerns (Stateless LLM vs. State-Aware Orchestration)

The LLM should never be responsible for remembering past crawls or fetching data.

  

- **The Orchestrator (LangGraph/Python):** Manages the state, fetches historical data from Supabase, performs the vector comparison, and constructs the prompt.
    
      
    
- **The LLM:** Acts purely as a reasoning and synthesis engine. It receives a tightly scoped payload (e.g., _"Here is what Competitor X's pricing page said last week vs. today"_), evaluates the business impact, and returns structured data.
    
      
    

### Rule 2: Strict Structured Output (No Free-Form Text)

An agent generating an executive PDF cannot afford messy or unpredictable LLM responses.

  

- The orchestration layer must enforce **JSON schema validation** (using tools like OpenAI's JSON mode or Pydantic integration).
    
      
    
- The LLM's output must map directly to predefined sections required by the reporting engine:
    
      
    - `pricing_shifts`: Array of detected price changes, tier restructurings, or feature gating.
        
          
        
    - `product_launches`: Array of new features, updates, or blog highlights.
        
          
        
    - `legal_updates`: Summary of terms of service or privacy policy shifts.
        
          
        
    - `executive_summary`: A 3-sentence high-level overview for leadership.
        
          
        

### Rule 3: Context Window Management & Chunking

Competitor pages (especially terms of service or extensive blogs) can easily exceed token limits or introduce "noise" that degrades LLM attention.

  

- **Semantic Filtering:** Before sending text to the LLM, the orchestration layer uses Supabase `pgvector` similarity scores to filter out sections that haven't changed or are irrelevant (e.g., website footers, copyright notices, cookie banners).
    
      
    
- **Token Budgeting:** The orchestrator trims or summarizes historical context if the text diff is exceptionally large, ensuring the LLM focuses strictly on high-impact delta.
    
      
    

### Rule 4: Deterministic Guardrails & Fallbacks

AI models can hallucinate or fail to return valid JSON. The orchestration layer must handle these edge cases gracefully:

  

- **Retry Logic:** If the LLM returns invalid JSON or times out, the orchestrator catches the exception, logs the error, and automatically retries with a lower temperature (e.g., `temperature=0.0`).
    
      
    
- **Fallback Summaries:** If multiple LLM calls fail, the system falls back to a deterministic text-diff summary rather than crashing the entire weekly pipeline.
    
      
    

## 2. Step-by-Step Execution Flow within the Orchestrator

```
[Vector DB Diffs Found] 
         │
         ▼
[Step 1: Prompt Assembly] ──► Inject Old vs. New Text + System Persona
         │
         ▼
[Step 2: LLM Call with Pydantic Schema] ──► Enforce Strict JSON Output
         │
         ▼
[Step 3: Validation & Error Handling] ──► Check for Schema Compliance
         │
         ▼
[State Update] ──► Pass Structured Insights to PDF Engine
```

1. **Prompt Assembly:** The orchestrator binds a strict system persona ("Elite Market Intelligence Analyst") with the specific text diffs pulled from Supabase.
    
      
    
2. **Execution:** The prompt is sent to a high-reasoning model (e.g., GPT-4o or Claude 3.5 Sonnet).
    
      
    
3. **Pydantic Validation:** The response is validated against a Python Pydantic model to guarantee fields like `price_change` or `new_feature` exist and match expected data types.
    
      
    
4. **State Transition:** Once validated, the orchestrator updates the global workflow state and hands the data over to ReportLab for PDF generation.
     
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[Intelligent LLM Orchestration]]
10. 