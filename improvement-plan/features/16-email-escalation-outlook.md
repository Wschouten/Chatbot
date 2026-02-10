# Feature 16: Email Escalation via Outlook SMTP

**Track:** Feature
**Effort:** 30-45 min
**Status:** Done
**Dependencies:** None (independent of all other features)

## Context

When the chatbot cannot answer a question and the user requests human help, a Zendesk ticket is currently created. We want to replace this with sending an email to a configured Outlook address via SMTP. The Zendesk code stays in the codebase but is inactive by default, switchable via an `ESCALATION_METHOD` env var.

The existing flow (collect name, collect email, escalate) remains the same — only the final escalation step changes from Zendesk API call to SMTP email.

## Files to Modify

| File | Action |
|------|--------|
| `backend/email_client.py` | **Create** — New SMTP email client module |
| `backend/app.py` | **Modify** — Switch from Zendesk to email client |
| `backend/zendesk_client.py` | **Modify** — Add `use_mock` property (fixes existing bug) |
| `backend/.env.example` | **Modify** — Add SMTP config variables and escalation toggle |

## Implementation

### 1. Create `backend/email_client.py`

New module mirroring `zendesk_client.py` patterns (class structure, logging, error handling, mock mode):

- **Class:** `EmailClient`
- **Dependencies:** Python built-in `smtplib` + `email.mime` only (no new pip packages)
- **SMTP defaults:** `smtp.office365.com`, port 587, STARTTLS
- **Env vars loaded in `__init__`:**
  - `SMTP_SERVER` (default: `smtp.office365.com`)
  - `SMTP_PORT` (default: `587`)
  - `SMTP_FROM_EMAIL` (required)
  - `SMTP_PASSWORD` (required)
  - `SMTP_TO_EMAIL` (required)
- **`is_configured()`** — returns `True` if `from_email`, `password`, and `to_email` are all set
- **`use_mock` property** — returns `not self.is_configured()`
- **`send_email(name, requester_email, question, session_history)`**:
  - Same parameter signature as `ZendeskClient.create_ticket()`
  - Returns `{"ticket": {"id": "EMAIL-SENT", "subject": "..."}}` on success (compatible with existing response handling in app.py)
  - Returns `None` on failure
  - Mock mode: logs the request, returns `{"ticket": {"id": "MOCK-EMAIL-123", ...}}`
  - Sets `Reply-To` header to customer email
  - Email body includes: customer name, email, original question, full chat history (same format as Zendesk description)
  - Error handling: `SMTPAuthenticationError`, `SMTPConnectError`, `socket.timeout`, `SMTPException`, `OSError`

### 2. Fix `backend/zendesk_client.py`

Add `use_mock` property after `is_configured()` method (~line 29). This fixes a latent bug where `app.py:250` references `zendesk.use_mock` which doesn't exist:

```python
@property
def use_mock(self) -> bool:
    """Check if running in mock mode (credentials missing)."""
    return not self.is_configured()
```

### 3. Modify `backend/app.py`

**3a. Add import** (after line 19):
```python
from email_client import EmailClient
```

**3b. Replace global client instantiation** (lines 277-278):
Replace `zendesk = ZendeskClient()` with:
```python
ESCALATION_METHOD = os.environ.get("ESCALATION_METHOD", "email").lower()
if ESCALATION_METHOD == "zendesk":
    escalation_client = ZendeskClient()
else:
    escalation_client = EmailClient()
```

**3c. Update health check** (lines 248-264):
Replace `zendesk.use_mock` references with `escalation_client.use_mock`. Update dependency key from `"zendesk"` to the active method name (`"email"` or `"zendesk"`).

**3d. Replace ticket creation and response messages** (lines 426-446):
- Line 427: Replace `zendesk.create_ticket(...)` with conditional call to either `escalation_client.create_ticket()` or `escalation_client.send_email()`
- Lines 436-446: Branch success/error messages:
  - **Email mode (NL):** "Top! Ik heb je bericht doorgestuurd naar een collega. We nemen zo snel mogelijk contact met je op via e-mail."
  - **Email mode (EN):** "Great! I've forwarded your message to a colleague. We'll get in touch via email as soon as possible."
  - **Zendesk mode:** Keep existing ticket number messages unchanged
  - **Error (NL):** "Sorry, er ging iets mis bij het versturen van je bericht. Neem alsjeblieft direct contact met ons op."
  - **Error (EN):** "I'm sorry, something went wrong sending your message. Please contact us directly."

### 4. Update `backend/.env.example`

Add after the Zendesk section:
```env
# Escalation Method: "email" (default) or "zendesk"
ESCALATION_METHOD=email

# SMTP Email (when ESCALATION_METHOD=email)
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_FROM_EMAIL=
SMTP_PASSWORD=
SMTP_TO_EMAIL=
```

## Verification

1. **Mock mode:** Set `ESCALATION_METHOD=email`, leave SMTP credentials empty. Trigger the full flow (unanswerable question -> request human -> give name -> give email). Confirm logs show mock email send and user sees success message.
2. **Real SMTP:** Set all 5 SMTP env vars. Run same flow. Confirm email arrives at `SMTP_TO_EMAIL` with correct subject ("Chatbot Query from {name}"), body (name, email, question, chat history), and Reply-To header.
3. **Toggle to Zendesk:** Set `ESCALATION_METHOD=zendesk`. Confirm Zendesk flow works as before.
4. **Health check:** `GET /health` reflects active escalation method and its config status.
5. **Error handling:** Set wrong SMTP password, verify graceful error message shown to user.

## Notes

- Office 365 accounts with MFA need an App Password (generated in Azure AD), not the regular account password
- The SMTP AUTH feature must be enabled in the Exchange admin center for the sending account
- No changes needed to `requirements.txt`, `Dockerfile`, or `docker-compose.yml`