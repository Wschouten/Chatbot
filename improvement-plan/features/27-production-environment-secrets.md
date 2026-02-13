# Feature 27: Production Environment & Secrets Preparation

**Track:** Operations
**Effort:** 15-30 min
**Status:** Todo
**Dependencies:** None (can start immediately, in parallel with Features 25 and 26)

## Context

Before deploying to Railway (Feature 20), all production environment variables, API keys, and SMTP credentials must be prepared. This is a prerequisite for deployment and can be done while code changes (Features 25, 26) are being implemented.

## Steps

### 1. Generate production secrets

| Secret | How to generate |
|--------|----------------|
| `ADMIN_API_KEY` | `openssl rand -hex 32` (or PowerShell: `[System.Guid]::NewGuid().ToString("N") + [System.Guid]::NewGuid().ToString("N")`) |
| `OPENAI_API_KEY` | Use existing production key from [OpenAI dashboard](https://platform.openai.com/api-keys) |

### 2. Prepare SMTP credentials for email escalation

| Variable | Value |
|----------|-------|
| `ESCALATION_METHOD` | `email` |
| `SMTP_SERVER` | `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_FROM_EMAIL` | Production sending address |
| `SMTP_PASSWORD` | App password (see notes below) |
| `SMTP_TO_EMAIL` | Support inbox address |

### 3. Determine CORS allowed origins

Set `ALLOWED_ORIGINS` to include all domains that will host the widget:

```
https://your-store.myshopify.com,https://www.your-store.com
```

Replace with actual Shopify store domains. If using a custom domain, include both the `.myshopify.com` and custom domain variants.

### 4. Verify .env.example is up to date

Ensure `backend/.env.example` documents all required variables with placeholder values and comments explaining each one.

### 5. Store secrets securely

Keep production secrets in a password manager or secure note — they will be entered into Railway's dashboard in Feature 20.

## Verification

1. All required secrets have been generated and stored securely
2. SMTP credentials have been tested (send a test email via the sending account)
3. `ALLOWED_ORIGINS` domains are confirmed with the store owner
4. `.env.example` lists every required variable

## Notes

- Office 365 accounts with MFA require an App Password generated in Azure AD, not the regular account password
- The SMTP AUTH feature must be enabled in the Exchange admin center for the sending account
- Do NOT commit real secrets to the repository — `.env` is in `.gitignore`
- This feature can be completed in parallel with Features 25 (Query Reformulation) and 26 (ChromaDB Fix)
