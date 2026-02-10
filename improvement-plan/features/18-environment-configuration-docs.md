# Feature 18: Environment Configuration Documentation

**Track:** Documentation
**Effort:** 10 min
**Status:** Done
**Dependencies:** Feature 16 (Email Escalation — adds SMTP and ESCALATION_METHOD env vars)

## Context

The `.env.example` file must document all environment variables needed for production deployment. Feature 16 introduces new SMTP-related variables and an `ESCALATION_METHOD` toggle. This feature ensures `.env.example` is complete and accurate before the production baseline commit.

## Files to Modify

| File | Action |
|------|--------|
| `backend/.env.example` | **Modify** — Ensure all production env vars are documented |

## Implementation

### 1. Verify all env vars are present

Ensure `.env.example` includes at minimum:

```env
# OpenAI
OPENAI_API_KEY=

# Admin
ADMIN_API_KEY=

# Security / CORS
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-store.com

# Flask
FLASK_DEBUG=false

# Escalation Method: "email" (default) or "zendesk"
ESCALATION_METHOD=email

# SMTP Email (when ESCALATION_METHOD=email)
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_FROM_EMAIL=
SMTP_PASSWORD=
SMTP_TO_EMAIL=

# Zendesk (when ESCALATION_METHOD=zendesk)
ZENDESK_SUBDOMAIN=
ZENDESK_EMAIL=
ZENDESK_API_TOKEN=
```

### 2. Add production notes as comments

Include inline comments for vars that need special attention in production (e.g., `ALLOWED_ORIGINS` must match actual store domain, `FLASK_DEBUG` must be `false`).

## Verification

1. Compare `.env.example` against all `os.environ.get()` calls in `app.py`, `email_client.py`, `zendesk_client.py`, and `rag_engine.py`
2. Confirm no env var is missing from the example file

## Notes

- This is a documentation-only change with no runtime impact
- Must be done after Feature 16 is complete so the SMTP vars are finalized
