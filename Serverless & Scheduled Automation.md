## Serverless & Scheduled Automation Architecture

The Serverless & Scheduled Automation layer for **Competepulse** eliminates manual execution by orchestrating containerized execution in the cloud on a recurring cron schedule, followed by multi-channel distribution.

  

### 1. The Automation Pipeline Flow

```
[GitHub Actions Cron (Weekly)] 
               │
               ▼
[Docker Container Triggered] ──► [Run Competepulse Agent] ──► [Generate PDF Report]
                                                                      │
                                          ┌───────────────────────────┘
                                          ▼
                         [Distribute: Slack Webhook / SendGrid Email]
```

### 2. Component Breakdown

#### A. Containerization (Docker)

Docker packages the Python runtime, system dependencies (such as fonts for PDF generation via ReportLab), and codebase into a single isolated image.

  

- **Dockerfile Structure:**
    
      
    
    Dockerfile
    
    ```
    FROM python:3.11-slim
    WORKDIR /app
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    COPY . .
    CMD ["python", "main.py"]
    ```
    
- **Why it matters:** Eliminates environment discrepancies between a local developer machine and cloud runner environments.
    
      
    

#### B. Scheduling & Execution (GitHub Actions)

GitHub Actions provides free compute runners with built-in cron scheduling capabilities, avoiding the need for dedicated server infrastructure.

  

- **Workflow Configuration (`.github/workflows/competepulse.yml`):**
    
      
    
    YAML
    
    ```
    name: Competepulse Weekly Run
    
    on:
      schedule:
        - cron: '0 6 * * 1' # Runs every Monday at 6:00 AM UTC
      workflow_dispatch: allow manual triggers for testing
    
    jobs:
      run-agent:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout Code
            uses: actions/checkout@v4
    
          - name: Set up Python
            uses: actions/setup-python@v5
            with:
              python-version: '3.11'
    
          - name: Install Dependencies
            run: |
              python -m pip install --upgrade pip
              pip install -r requirements.txt
    
          - name: Run Competepulse Agent
            env:
              FIRECRRAWL_API_KEY: ${{ secrets.FIRECRAWL_API_KEY }}
              SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
              SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
              OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
              SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
            run: python main.py
    ```
    

#### C. Distribution Engine (Slack & Email)

Once the PDF is generated programmatically, the final step of the script pushes the artifact outward to stakeholders.

  

- **Slack Webhook Integration:** Uses an HTTP POST request to transmit a notification message with the attached or linked PDF summary.
    
      
    
    Python
    
    ```
    import os
    import requests
    
    def send_slack_alert(summary_text):
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        payload = {
            "text": f"*Competepulse Weekly Brief*\n\n{summary_text}"
        }
        response = requests.post(webhook_url, json=payload)
        return response.status_code
    ```
    
- **Email Delivery (SendGrid / SMTP):** Attaches the generated `executive_brief.pdf` directly to an automated email dispatch for executive review before standard office hours.
    
      
    

### 3. Production Considerations

- **Secret Management:** Never hardcode API keys or database URLs. Utilize GitHub Secrets or environment injection via cloud parameters.
    
      
    
- **Error Handling & Logging:** Ensure exceptions during scraping timeouts or database latency are caught gracefully within the cron job so alerts can bubble up via webhook if a run fails.

. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
   [[serverrules]]
10. [[Automated Distribution Channels]]
11. 