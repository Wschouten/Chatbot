# Feature 20: Railway Hosting Deployment

**Track:** Infrastructure
**Effort:** 30-60 min
**Status:** Todo
**Dependencies:** Feature 27 (Production env vars prepared), Feature 28 (Local Docker smoke test passes)

## Context

The chatbot needs to be hosted on a publicly accessible server with HTTPS so the Shopify store can load the widget script and make API calls. Railway is the recommended platform: it auto-detects Dockerfiles, provides auto-SSL, persistent volumes, and custom domain support at ~$5-7/month.

### Alternative: Hetzner VPS + Coolify (~4 EUR/month)
More control and EU-hosted (good for GDPR), but requires basic server management. This feature documents the Railway path; Hetzner can be substituted if preferred.

## Steps

### 1. Create Railway account and connect GitHub

- Sign up at [railway.app](https://railway.app)
- Connect the GitHub repo containing the chatbot
- Railway auto-detects the `Dockerfile` and sets up the build

### 2. Set environment variables

Configure all production env vars in Railway's dashboard:

| Variable | Value |
|----------|-------|
| `OPENAI_API_KEY` | Real production key |
| `ADMIN_API_KEY` | Generate a new secure key (e.g., `openssl rand -hex 32`) |
| `ALLOWED_ORIGINS` | `https://your-store.myshopify.com,https://www.your-store.com` |
| `FLASK_DEBUG` | `false` |
| `ESCALATION_METHOD` | `email` |
| `SMTP_SERVER` | `smtp.office365.com` |
| `SMTP_PORT` | `587` |
| `SMTP_FROM_EMAIL` | Production sending address |
| `SMTP_PASSWORD` | App password (see notes) |
| `SMTP_TO_EMAIL` | Support inbox address |

### 3. Attach persistent volumes

Mount volumes for data that must survive redeployments:

| Container Path | Purpose |
|----------------|---------|
| `/app/backend/chroma_db` | Vector database (rebuilt on startup but caching saves time) |
| `/app/backend/sessions` | Active chat sessions |
| `/app/backend/logs` | Application logs |

### 4. Configure custom domain + DNS

- Add a custom domain in Railway (e.g., `chat.your-store.com`)
- Create a CNAME DNS record pointing to Railway's provided hostname
- Railway auto-provisions SSL certificate

### 5. Deploy and verify

- Trigger deploy (automatic on push, or manual)
- Wait for health check to pass
- Verify at `https://chat.your-store.com/health`

## Verification

1. `GET /health` returns 200 with `"status": "healthy"` and `document_count > 0`
2. `ALLOWED_ORIGINS` correctly includes the Shopify store domain
3. HTTPS is working (no mixed-content warnings)
4. Chat flow works end-to-end from a browser hitting the Railway URL directly
5. Email escalation sends a real email (test the full flow once)

## Notes

- Office 365 accounts with MFA need an App Password generated in Azure AD, not the regular account password
- The SMTP AUTH feature must be enabled in the Exchange admin center for the sending account
- Railway free tier has limits; the Hobby plan ($5/month) is recommended for always-on services
- If using Hetzner + Coolify instead, the same env vars and volumes apply; only the deployment mechanism differs

## Cost

| Item | Monthly |
|------|---------|
| Railway Hobby plan | ~$5-7 |
| OpenAI API (varies by traffic) | ~$5-20 |
| **Total** | **~$10-27** |
