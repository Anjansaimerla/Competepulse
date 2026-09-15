## Serverless & Scheduled Automation: Architecture & Implementation

Serverless and scheduled automation form the backbone of **Competepulse**. By combining Docker, GitHub Actions, and cloud execution, the agent runs entirely on autopilot every week without requiring a dedicated server or manual intervention.

  

### Core Architecture Flow

The automation pipeline executes through three main layers:

  

1. **The Container Image (Docker):** Bundles the Python script, Firecrawl SDK, Supabase client, ReportLab, and all system dependencies into a single, portable unit.
    
      
    
2. **The Trigger (GitHub Actions Cron):** Acts as a digital alarm clock, waking up at a designated time (e.g., every Monday at 6:00 AM UTC).
    
      
    
3. **The Execution & Delivery:** GitHub spins up a temporary virtual machine, pulls the Docker container, runs the script to scrape competitors, generates the PDF, and pushes the report to Slack or email.
    
      
    

### Step-by-Step Implementation Guide

#### 1. Containerizing the Agent (Dockerfile)

To ensure the Python script runs identically on your local machine and in the cloud, package it into a Docker image. Create a file named `Dockerfile` in your project root:

  

Dockerfile

```
# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency list and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project source code
COPY . .

# Define the command to run your agent script
CMD ["python", "main.py"]
```

#### 2. Configuring Secure Environment Variables

Because your script connects to external services (Firecrawl, Supabase, OpenAI, Slack/SendGrid), it needs API keys. **Never hardcode keys into your code.** Instead, store them securely in **GitHub Repository Secrets**.

  

Go to your GitHub repository: `Settings` $\rightarrow$ `Secrets and variables` $\rightarrow$ `Actions` $\rightarrow$ `New repository secret`, and add:

  

- `FIRECRAWL_API_KEY`
    
      
    
- `SUPABASE_URL`
    
      
    
- `SUPABASE_KEY`
    
      
    
   NVIDIA_API_KEY`
    
      
    
- `SLACK_WEBHOOK_URL` (or `SENDGRID_API_KEY`)
    
      
    

#### 3. Setting Up the Scheduler (GitHub Actions Workflow)

Create a directory structure in your project: `.github/workflows/`. Inside it, create a file named `weekly_brief.yml`:

  

YAML

```
name: Competepulse Weekly Run

# Trigger configuration
on:
  schedule:
    - cron: '0 6 * * 1'  # Runs every Monday at 6:00 AM UTC
  workflow_dispatch:      # Allows you to click a button to run it manually anytime

jobs:
  run-agent:
    runs-on: ubuntu-latest
    
    steps:
      # Step 1: Pull your repository code into the runner
      - name: Checkout code
        uses: actions/checkout@v4

      # Step 2: Set up Python environment as a fallback/alternative to raw Docker execution
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      # Step 3: Install dependencies
      - name: Install dependencies
        run: pip install -r requirements.txt

      # Step 4: Run the agent script, injecting GitHub Secrets as environment variables
      - name: Execute Competepulse Agent
        env:
          FIRECRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
        run: python main.py
```

### Production Best Practices & Failure Handling

- **Idempotency:** Ensure your agent can safely re-run if a job fails halfway through. Supabase database inserts should use unique constraints or timestamps so duplicate runs don't corrupt historical diff data.
    
      
    
- **Error Notifications:** Wrap your main execution block in a `try/except` statement. If an exception occurs (e.g., Firecrawl times out or Supabase rejects a connection), catch the error and route an alert to a fallback webhook or personal email so you know the weekly brief failed to compile.
    
      
    
- **GitHub Actions Timeout Limits:** GitHub restricts free public/private repository workflow runs to a maximum of 6 hours (though a scraping script should comfortably finish in under 2–3 minutes). Set an explicit timeout in your workflow if necessary using `timeout-minutes: 10`.
  
  
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[Serverless & Scheduled Automation]]
10. 