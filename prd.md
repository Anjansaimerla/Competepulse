A solid PRD (Product Requirements Document) for **Competepulse** provides a clear blueprint for what you're building, why you're building it, and how it works.

  

# Product Requirements Document (PRD): Competepulse

## 1. Executive Summary

Competepulse is an autonomous market intelligence agent designed to automate competitor tracking. By combining headless web scraping, vector-backed semantic change detection, and automated LLM analysis, the tool crawls competitor domains weekly, isolates meaningful shifts (such as pricing tier adjustments or new product launches), and compiles the findings into a polished executive PDF report.

  

## 2. Problem Statement

Product managers, founders, and market researchers waste hours manually browsing competitor websites week after week to check for updates. Standard web scrapers or change-alert tools are too noisy, triggering false alarms on minor layout shifts, typos, or CSS updates instead of focusing on actual business and product changes.

  

## 3. Target Users

- **Founders & Indie Hackers:** Need to monitor competitors without dedicating hours to manual research.
    
      
    
- **Product Managers:** Want automated visibility into feature rollouts and pricing strategy pivots.
    
      
    
- **Sales & Marketing Teams:** Need real-time insights into competitor positioning changes for go-to-market strategies.
    
      
    

## 4. Core Features & User Stories

- **Automated URL Ingestion:** As a user, I want the agent to automatically target a competitor’s `/pricing`, `/blog`, and `/terms` pages so I don't have to navigate them manually.
    
      
    
- **Clean Markdown Extraction:** As a system, I need raw HTML converted into clean, LLM-ready Markdown via Firecrawl to bypass anti-scraping blocks.
    
      
    
- **Semantic Change Detection:** As a system, I need to compare current web snapshots against historical database records using vector embeddings (`pgvector`) so I only flag true business changes, ignoring superficial text edits.
    
      
    
- **Executive PDF Brief Generation:** As a user, I want a cleanly formatted weekly PDF report delivered automatically so I can quickly digest insights over morning coffee.
    
      
    

## 5. Technical Architecture & Tech Stack

- **Language & Orchestration:** Python (`asyncio`, LangGraph or custom execution loops).
    
      
    
- **Scraping Engine:** Firecrawl API (with optional Playwright fallback).
    
      
    
- **Database & Vector Store:** Supabase (PostgreSQL with the `pgvector` extension).
    
      
    
- **LLM Layer:** OpenAI (GPT-4o) or Anthropic (Claude 3.5 Sonnet) for diff synthesis and insight generation.
    
      
    
- **Document Engine:** ReportLab for programmatic PDF compilation.
    
      
    
- **Infrastructure & Automation:** Docker containerization, GitHub Actions (Cron schedule), and Slack Webhooks/SendGrid for distribution.
    
      
    

## 6. Success Metrics

- **Time Saved:** Reduces 5+ hours of manual weekly competitor checking to zero manual effort.
    
      
    
- **Noise Reduction:** Zero false-positive alerts triggered by minor CSS or layout modifications, driven by vector similarity thresholds ($>0.85$).
    
      
    
- **Reliability:** Successful weekly end-to-end execution resulting in a generated PDF delivered via webhook/email.
    
      
    

Let me know if you want to expand any of these sections or dive straight into writing the folder structure and code files for the repository!
1. [[trd]]
2. [[appflow]]
3. [[rules]]
4. [[systemarchitecture]]
5. [[overview]]
6. 