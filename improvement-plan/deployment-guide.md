# Deployment Guide: Features 20, 21, 22

## Context

All code work is complete (Features 16-19). The chatbot is committed locally on `master` but not yet pushed. These three features are **manual infrastructure steps** to get from "works in Docker" to "live on Shopify".

> **Security note:** Your `.env` file contains an OpenAI key flagged as exposed (see the rotation warning at the top of the file). Use **rotated/new keys** for production — do NOT copy the current `.env` values.

---

## Feature 20: Railway Hosting Deployment

### Step 1 — Push code to GitHub

```bash
git push origin master
```

### Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) and sign up (GitHub login recommended)
2. Click **"New Project"** > **"Deploy from GitHub Repo"**
3. Select your `GroundCoverChatbot` repository
4. Railway auto-detects the `Dockerfile` — no build config needed

### Step 3 — Set environment variables

In Railway dashboard > your service > **Variables** tab, add each of these:

| Variable | Value | Notes |
|----------|-------|-------|
| `OPENAI_API_KEY` | `sk-proj-...` | **Generate a new key** at [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `ADMIN_API_KEY` | *(generate new)* | Run: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ALLOWED_ORIGINS` | `https://YOUR-STORE.myshopify.com,https://www.YOUR-STORE.com` | Replace with real Shopify domain(s) |
| `FLASK_DEBUG` | `false` | |
| `ESCALATION_METHOD` | `email` | |
| `SMTP_SERVER` | `smtp.office365.com` | |
| `SMTP_PORT` | `587` | |
| `SMTP_FROM_EMAIL` | Your sending email address | |
| `SMTP_PASSWORD` | App Password from Azure AD | If account has MFA, you need an App Password, not the regular password |
| `SMTP_TO_EMAIL` | Your support inbox address | |
| `BRAND_NAME` | `GroundCoverGroup` | |
| `BRAND_USE_EMOJIS` | `false` | |

> You can copy the other `BRAND_*` and `DATA_RETENTION_*` values from your local `.env` — those don't contain secrets.

### Step 4 — Attach persistent volumes

In Railway dashboard > your service > **Volumes** tab, create three mounts:

| Mount Path | Purpose |
|------------|---------|
| `/app/backend/chroma_db` | Vector database cache (rebuilt on startup but saves time) |
| `/app/backend/sessions` | Active chat sessions |
| `/app/backend/logs` | Conversation logs |

### Step 5 — Configure custom domain

1. In Railway > your service > **Settings** > **Networking** > **Custom Domain**
2. Add your domain (e.g., `chat.groundcovergroup.nl`)
3. Railway gives you a CNAME target — add it to your DNS:
   - **Type:** CNAME
   - **Name:** `chat` (or whatever subdomain you chose)
   - **Value:** the Railway-provided hostname
4. Railway auto-provisions an SSL certificate (may take a few minutes)

> If you don't have a custom domain yet, Railway provides a free `*.up.railway.app` URL you can use temporarily.

### Step 6 — Deploy and verify

1. Railway auto-deploys on push. Watch the build logs in the dashboard.
2. First deploy takes ~3-5 minutes (building Docker image + ingesting 32 knowledge base files)
3. Once healthy, verify:
   - Open `https://YOUR-RAILWAY-DOMAIN/health` in your browser
   - Confirm you see: `"status": "ok"` and `"document_count"` > 0
   - Confirm the escalation method shows as `"configured"` or `"mock_mode"`

### Troubleshooting

- **Build fails:** Check Railway build logs for missing env vars or Dockerfile issues
- **Health check fails:** The `--start-period=5m` in the Dockerfile gives it time for initial ingestion — wait 5 minutes
- **CORS errors later:** Make sure `ALLOWED_ORIGINS` exactly matches your Shopify URL (including `https://`)

---

## Feature 21: Shopify Widget Integration

### Prerequisites
- Feature 20 is complete — you have a live URL (e.g., `https://chat.groundcovergroup.nl` or `https://xxx.up.railway.app`)
- You verified `/health` returns OK

### Step 1 — Add script to Shopify theme

1. Go to **Shopify Admin** > **Online Store** > **Themes**
2. Click **"..."** on your active theme > **"Edit code"**
3. Open **`Layout/theme.liquid`**
4. Find the closing `</body>` tag (usually at the very bottom)
5. Paste this **directly before** `</body>`:

```html
<script src="https://YOUR-RAILWAY-DOMAIN/widget.js"
        data-api-url="https://YOUR-RAILWAY-DOMAIN"
        data-brand="GroundCoverGroup"
        data-position="bottom-right"
        data-primary-color="#2C5E2E"
        data-welcome="Hallo! Hoe kan ik je helpen?"
        data-privacy-url="/pages/privacy-policy">
</script>
```

6. Replace `YOUR-RAILWAY-DOMAIN` with your actual Railway domain (both places)
7. Click **Save**

### Step 2 — Update ALLOWED_ORIGINS on Railway

Make sure the `ALLOWED_ORIGINS` variable in Railway includes your Shopify domain. Example:

```
https://your-store.myshopify.com,https://www.your-store.nl
```

After changing, Railway auto-redeploys.

### Step 3 — Test checklist

Open your Shopify store and run through each of these:

| # | Test | Expected result |
|---|------|----------------|
| 1 | Desktop: see chat bubble | Green circle button in bottom-right corner |
| 2 | Click bubble | Chat window opens with GDPR consent prompt |
| 3 | Accept consent | Consent disappears, welcome message shown |
| 4 | Ask a Dutch question (e.g., "Wat is houtmulch?") | Dutch answer from knowledge base |
| 5 | Ask an English question (e.g., "What is bark mulch?") | English answer |
| 6 | Ask something unanswerable, then request human help | Name > email > confirmation flow works |
| 7 | Browser console (F12) | No CORS errors, no JavaScript errors |
| 8 | Mobile phone | Widget doesn't overlap sticky headers/footers |
| 9 | Incognito window | GDPR consent prompt appears again |
| 10 | Checkout page | Widget does NOT appear (this is expected — Shopify restriction) |

### Troubleshooting

- **Widget doesn't appear:** Check browser console for errors. Most likely `data-api-url` is wrong or the Railway URL isn't accessible
- **CORS errors in console:** `ALLOWED_ORIGINS` on Railway doesn't match your Shopify domain exactly
- **Z-index conflicts:** If theme elements cover the widget, the widget uses z-index `2147483647` (maximum) — this should win over most themes
- **Two consent banners:** Shopify may show its own cookie banner alongside the chatbot GDPR consent — this is fine

---

## Feature 22: Post-Launch Monitoring (first week)

### Step 1 — Set up UptimeRobot (5 minutes)

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Click **"Add New Monitor"**
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** `GroundCover Chatbot`
   - **URL:** `https://YOUR-RAILWAY-DOMAIN/health`
   - **Monitoring Interval:** 5 minutes
3. Configure **email alerts** for downtime
4. Save — you'll get an email if the chatbot goes down

### Step 2 — Daily checks for the first week

**Railway logs** (check daily in Railway dashboard > service > **Logs**):
- Look for Python tracebacks (errors)
- Look for gunicorn worker timeout warnings (queries taking >120s)
- Check memory usage trend in Railway metrics (should stay under 512MB)

**OpenAI usage** (check daily at [platform.openai.com/usage](https://platform.openai.com/usage)):
- Verify costs are in the expected ~$5-20/month range
- Set up a billing alert/hard limit if you want

### Step 3 — Run RAG evaluation (after 1-2 days stable)

Once the chatbot has been running for a day or two without issues:

```bash
docker-compose up -d
python backend/evaluate_rag.py
```

Compare results against the previous 100% pass rate baseline in `backend/evaluation/evaluation_results.json`.

### Step 4 — Review chat logs (weekly habit)

Check Railway volume for `logs/` directory, or pull logs via Railway CLI:
- Look for frequently asked questions NOT in the knowledge base
- Look for incorrect or unhelpful answers
- Track how often users request human escalation
- Add new `.txt` files to `backend/knowledge_base/` for recurring questions the bot can't answer

---

## Cost Summary

| Item | Monthly |
|------|---------|
| Railway Hobby plan | ~$5-7 |
| OpenAI API (varies with traffic) | ~$5-20 |
| UptimeRobot | Free |
| **Total** | **~$10-27** |

---

## Quick Reference: Order of Operations

1. `git push origin master`
2. Create Railway project + set env vars + volumes + domain
3. Verify `/health` returns OK
4. Add `<script>` tag to Shopify `theme.liquid`
5. Update `ALLOWED_ORIGINS` to include Shopify domain
6. Run through test checklist on the live store
7. Set up UptimeRobot
8. Monitor daily for the first week
