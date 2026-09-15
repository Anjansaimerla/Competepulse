# Architectural & Implementation Guide: Automated Distribution Channels for Competepulse

This document defines the architecture, data flow, error handling, and implementation rules for the **Automated Distribution Channels** module in Competepulse. This layer is responsible for taking the generated executive PDF brief and securely delivering it to stakeholders via Slack and Email without manual intervention.

  

## 1. System Architecture & Routing Logic

The distribution engine acts as the final node in the Competepulse workflow graph. Once the ReportLab engine compiles the PDF and returns its absolute file path, the distribution dispatcher evaluates the configuration environment variables to route the document to the appropriate channels.

  

```
[PDF Compilation Engine]
           │
           ▼
[Distribution Dispatcher]
           ├──► [Slack Webhook Handler] ──► (POST multipart/form-data) ──► Slack Workspace
           │
           └──► [Email SMTP / SendGrid API] ──► (MIME Multipart Payload) ──► Executive Inboxes
```

### Core Routing Rules

- **Asynchronous Execution:** Distribution tasks must execute asynchronously to prevent network latency or API rate limits from blocking the primary workflow runtime.
    
      
    
- **Idempotency & Retry Safety:** If a delivery channel fails, the system must log the error and retry up to 3 times with exponential backoff before triggering an alert fallback.
    
      
    
- **Environment-Based Toggle:** Channels are enabled dynamically based on the presence of specific environment variables (`SLACK_WEBHOOK_URL`, `SENDGRID_API_KEY`, or `SMTP_HOST`).
    
      
    

## 2. Slack Channel Integration

Slack delivery utilizes Incoming Webhooks combined with the Slack Files API to upload the binary PDF directly into a designated channel rather than sending a loose external link.

  

### Implementation Requirements

- **Payload Type:** Multipart/form-data containing the file buffer and comment metadata.
    
      
    
- **Authentication:** Bot User OAuth Token (`xoxb-...`) or dedicated Webhook URL with `files:write` permissions.
    
      
    

Python

```
import os
import aiohttp

async def send_slack_notification(pdf_path: str, channel_id: str):
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    url = "https://slack.com/api/files.upload"
    
    headers = {"Authorization": f"Bearer {slack_token}"}
    
    async with aiohttp.ClientSession() as session:
        with open(pdf_path, "rb") as pdf_file:
            form = aiohttp.FormData()
            form.add_field('channels', channel_id)
            form.add_field('initial_comment', "📊 *Competepulse Weekly Brief:* New competitor updates detected.")
            form.add_field('file', pdf_file, filename=os.path.basename(pdf_path), content_type='application/pdf')
            
            async with session.post(url, headers=headers, data=form) as response:
                result = await response.json()
                if not result.get("ok"):
                    raise RuntimeError(f"Slack upload failed: {result.get('error')}")
                return True
```

## 3. Email Channel Integration (SendGrid / SMTP)

Email delivery compiles a clean MIME message attaching the compiled PDF alongside a lightweight HTML summary body extracted from the LLM state.

  

### Implementation Requirements

- **Transport Layer:** SendGrid Python SDK for production delivery tracking (opens/bounces), with standard `smtplib`as a fallback.
    
      
    
- **Payload Structure:** Multipart MIME message containing a `text/html` alternative body and a `application/pdf`attachment node.
    
      
    

Python

```
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

def send_email_brief(pdf_path: str, recipient_emails: list[str], summary_snippet: str):
    message = Mail(
        from_email=os.environ.get("SENDER_EMAIL"),
        to_emails=recipient_emails,
        subject="Competepulse Weekly Executive Intelligence Brief",
        html_content=f"<p><strong>Automated Weekly Briefing</strong></p><p>{summary_snippet}</p>"
    )
    
    with open(pdf_path, 'rb') as f:
        file_data = f.read()
        
    encoded_file = base64.b64encode(file_data).decode()
    
    attachment = Attachment(
        FileContent(encoded_file),
        FileName(os.path.basename(pdf_path)),
        FileType('application/pdf'),
        Disposition('attachment')
    )
    message.attachment = attachment
    
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        return response.status_code == 202
    except Exception as e:
        raise RuntimeError(f"Email dispatch failed: {str(e)}")
```

## 4. Error Handling, Logging, and Fallbacks

Robust failure management ensures that delivery hiccups do not corrupt the agent's tracking state or leave stakeholders in the dark.

  

- **Dead Letter Logging:** If all delivery retries fail, the system writes the absolute path of the generated PDF to a local fallback directory (`./failed_deliveries/`) and emits an error event to the monitoring hook.
    
      
    
- **Secret Masking:** API keys, webhook URLs, and sender credentials must never appear in execution logs. Logger instances must sanitize environment strings before printing output.
    
      
    
- **Dry Run Mode:** When running tests or local development without live API credentials, setting `DISTRIBUTION_DRY_RUN=true` bypasses external API calls and saves payloads locally for validation.
  
  . [[overview]]
5. [[prd]]
6. [[trd]]
7. [[appflow]]
8. [[rules]]
9. [[Automated Distribution Channels]]
10. 