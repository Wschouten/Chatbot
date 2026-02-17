# Feature 44: Railway Deployment

**Effort:** ~15 min
**Status:** Todo
**Priority:** High (production deployment)
**Dependencies:** Feature 43 (smoke test passes)
**Blocks:** Feature 45

---

## Problem

The application needs to be deployed to Railway so it's accessible on the internet for the Shopify widget to connect to.

---

## Steps

### 1. Push Code to GitHub

```bash
git push origin master
```

Ensure the latest commit (from Feature 41) is on GitHub.

### 2. Create Railway Project

1. Log in to https://railway.app
2. Click **New Project** > **Deploy from GitHub Repo**
3. Select the GroundCoverChatbot repository
4. Railway will auto-detect the `Dockerfile`

### 3. Set Environment Variables

In Railway dashboard: **Settings > Variables**

Add all production secrets from Feature 42:

```
OPENAI_API_KEY=sk-proj-...
ADMIN_API_KEY=<generated-key>
FLASK_ENV=production
FLASK_DEBUG=false
ESCALATION_METHOD=email
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_FROM_EMAIL=<your-email>
SMTP_PASSWORD=<app-password>
SMTP_TO_EMAIL=<support-email>
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-store.com
BRAND_NAME=GroundCoverGroup
BRAND_PRODUCT_LINE=GroundCoverGroup
BRAND_ASSISTANT_NAME=GroundCoverGroup
BRAND_USE_EMOJIS=true
RAG_RELEVANCE_THRESHOLD=1.2
DATA_RETENTION_SESSIONS_DAYS=30
DATA_RETENTION_LOGS_DAYS=90
```

Add shipping API credentials when StatusWeb whitelists IP:
```
SHIPPING_API_KEY=<when-available>
SHIPPING_API_PASSWORD=<when-available>
```

### 4. Create Persistent Volumes

In Railway dashboard: **Settings > Volumes**

| Mount Path | Purpose |
|-----------|---------|
| `/app/logs` | Chat logs (JSON files) |
| `/app/backend/data` | Portal SQLite database |
| `/app/backend/chroma_db` | ChromaDB vector store |
| `/app/backend/sessions` | Session state files |

### 5. Configure Networking

- Railway auto-assigns a `*.up.railway.app` domain
- Note this URL — it's needed for Shopify widget and CORS
- Optional: Add custom domain (e.g., `chat.groundcovergroup.com`)
- Update `ALLOWED_ORIGINS` to include the Railway domain itself

### 6. Deploy

Railway auto-deploys on push to master. Monitor in dashboard:
- Build logs: Verify Dockerfile builds successfully
- Deploy logs: Look for `"OpenAI Client Initialized Successfully"` and `"Ingestion Complete"`

---

## Verification

```bash
# Replace with your Railway URL
RAILWAY_URL=https://chatbot-production.up.railway.app

# 1. Health check
curl $RAILWAY_URL/health

# 2. Test chat (should return a response)
curl -X POST $RAILWAY_URL/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Wat is houtmulch?", "session_id": "test123"}'

# 3. Test admin API
curl -H "X-Admin-Key: $ADMIN_API_KEY" $RAILWAY_URL/admin/api/conversations

# 4. Open in browser
# Visit $RAILWAY_URL — chatbot should load
# Visit $RAILWAY_URL/portal — admin portal should load
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails | Check Dockerfile, verify Python 3.11 base image |
| Health returns unhealthy | Check OPENAI_API_KEY is set correctly |
| document_count = 0 | Knowledge base files missing — check Dockerfile COPY step |
| CORS errors | Update ALLOWED_ORIGINS with correct domains |
| 502 Bad Gateway | Check Railway logs for startup errors, verify PORT binding |
