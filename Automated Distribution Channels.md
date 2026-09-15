## Feature Documentation: Automated Distribution Channels (Competepulse)

The Automated Distribution Channels component serves as the final phase of the Competepulse pipeline. Once the agent compiles the weekly executive brief into a polished PDF report, this module securely routes the deliverable to designated stakeholders across asynchronous channels (Slack and Email) without manual intervention.

  

### 1. Overview & Objectives

- **Zero-Touch Delivery:** Eliminates the administrative friction of manually downloading and emailing weekly intelligence briefs.
    
      
    
- **Multi-Channel Redundancy:** Supports team-wide visibility via Slack workspace notifications alongside direct executive inbox delivery via SendGrid.
    
      
    
- **Secure File Handling:** Transmits compiled PDF assets securely using authenticated API tokens and signed payload transfers.
    
      
    

### 2. Architecture & Delivery Workflow

The distribution phase triggers immediately upon the successful generation of the PDF report by the ReportLab engine.

  

```
[PDF Report Generated] 
          │
          ├──────► [Slack Webhook Service] ────► #competitor-intel Channel
          │
          └──────► [SendGrid Email API] ──────► Executive Inbox(es)
```

### 3. Slack Integration (Webhook-Based Delivery)

The Slack channel distribution publishes a rich-text update notification containing a summary snippet and attaches the physical PDF file to a designated channel (e.g., `#competitor-intel`).

  

#### Configuration Steps

1. Create an Incoming Webhook app inside your Slack workspace and target your preferred channel.
    
      
    
2. Store the webhook URL securely in your environment variables (`SLACK_WEBHOOK_URL`).
    
      
    

#### Implementation Script

Python

```
import os
import requests

def send_slack_notification(pdf_path: str, summary_excerpt: str):
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("SLACK_WEBHOOK_URL environment variable not set.")

    # Payload text for the message body
    payload = {
        "text": f"📊 *Competepulse Weekly Brief Generated*\n\n> {summary_excerpt}"
    }
    
    # Send text notification
    response = requests.post(webhook_url, json=payload)
    response.raise_for_status()

    # Upload PDF file via Slack Files API or Webhook attachment mechanism
    # (Alternatively, post a secure download link if hosted on cloud storage like AWS S3 / Supabase Storage)
    with open(pdf_path, "rb") as f:
        files = {"file": (os.path.basename(pdf_path), f, "application/pdf")}
        data = {"channels": os.environ.get("SLACK_CHANNEL_ID"), "initial_comment": "Here is this week's executive brief."}
        headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
        
        upload_response = requests.post("https://slack.com/api/files.upload", headers=headers, data=data, files=files)
        upload_response.raise_for_status()
```

### 4. Email Integration (SendGrid API)

For executive stakeholders who prefer inbox delivery, the SendGrid integration encodes the PDF as a Base64 attachment and sends a formatted HTML email containing high-level takeaways.

  

#### Configuration Steps

1. Register a SendGrid account, verify a sender domain or single sender identity, and generate an API key.
    
      
    
2. Store credentials in environment variables (`SENDGRID_API_KEY`, `SENDER_EMAIL`, `RECIPIENT_EMAILS`).
    
      
    

#### Implementation Script

Python

```
import os
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

def send_email_report(pdf_path: str, email_body_html: str):
    sg_client = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
    
    message = Mail(
        from_email=os.environ.get("SENDER_EMAIL"),
        to_emails=os.environ.get("RECIPIENT_EMAILS").split(","),
        subject="Weekly Competitor Intelligence Brief - Competepulse",
        html_content=email_body_html
    )

    # Read and encode PDF file
    with open(pdf_path, "rb") as f:
        data = f.read()
        encoded_file = base64.b64encode(data).decode()

    # Attach PDF to SendGrid payload
    attachment = Attachment(
        FileContent(encoded_file),
        FileName(os.path.basename(pdf_path)),
        FileType("application/pdf"),
        Disposition("attachment")
    )
    message.attachment = attachment

    response = sg_client.send(message)
    return response.status_code
```

### 5. Error Handling & Retry Logic

Because network timeouts or third-party API rate limits can occasionally interrupt delivery, the distribution module incorporates exponential backoff retries via Python decorators.

Python

```
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_retries:
                        raise e
                    time.sleep(delay * attempts)
        return wrapper
    return decorator
```

### 6. Environment Variables Reference

|**Variable Name**|**Description**|**Scope**|
|---|---|---|
|`SLACK_WEBHOOK_URL`|Webhook endpoint for channel text alerts|Slack Integration|
|`SLACK_BOT_TOKEN`|OAuth token required for file uploads|Slack Integration|
|`SENDGRID_API_KEY`|Authentication key for SendGrid mail service|Email Integration|
|`SENDER_EMAIL`|Verified sender email address|Email Integration|
|`RECIPIENT_EMAILS`|Comma-separated list of executive recipients|Email Integration|
. [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[systemarchitecture]]
10. [[autorules]]
11. 