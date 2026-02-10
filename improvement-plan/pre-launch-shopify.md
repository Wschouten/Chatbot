# Pre-Launch Plan: GroundCover Chatbot on Shopify

## Context

The chatbot is functionally complete (100% RAG evaluation pass rate, bilingual support, GDPR consent, security headers). The goal is to go from "works locally in Docker" to "live on the Shopify store". This plan covers the code changes, hosting setup, and Shopify integration needed.

**Supabase is NOT required.** The current stack (ChromaDB + file-based sessions) is production-ready for a low-to-medium traffic chatbot.

---

## Phase 1: Code Changes (~1 hour)

### 1.1 Add gunicorn for production serving
- **Why:** Flask's dev server is single-threaded and not production-safe
- Files to change:
  - `backend/requirements.txt` — add `gunicorn`
  - `Dockerfile` — change CMD from `python app.py` to `gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --access-logfile - app:app`
  - `Dockerfile` — increase HEALTHCHECK `--start-period` from 2m to 5m (initial ingestion of 32 files can take a few minutes)

### 1.2 Zendesk → Email replacement (handled separately)
- **Note:** Being implemented in a separate terminal session
- Zendesk client will be replaced with email-to-Outlook functionality
- Health check, env vars, and ticket creation flow will all change as part of that work
- This plan assumes that work is completed before moving to Phase 2

### 1.3 Update .env.example
- Ensure all current env vars are documented (including new email config vars from step 1.2)

### 1.4 Commit all pending changes
- Working tree has unstaged changes to `app.py`, `brand_config.py`, `rag_engine.py`, `widget.js`, `Dockerfile`
- Plus untracked knowledge base `.txt` files and evaluation files
- Stage and commit everything as the "production-ready" baseline

---

## Phase 2: Hosting Setup (~30-60 min)

### Recommended: Railway ($5-7/month)
- Easiest Docker deployment, auto-SSL, persistent volumes, custom domains
- Push repo to GitHub, connect to Railway, it auto-detects the Dockerfile

### Alternative: Hetzner VPS + Coolify (~4 EUR/month)
- More control, EU-hosted (good for GDPR), but requires basic server management

### Setup steps:
1. Create Railway account, connect GitHub repo
2. Set environment variables (all from `.env.example` with real production values)
3. Attach persistent volumes for `/app/backend/chroma_db`, `/app/backend/sessions`, `/app/backend/logs`
4. Configure custom domain (e.g., `chat.your-store.com`) + DNS
5. Deploy, wait for health check, verify at `/health`

### Key env vars for production:
| Variable | Action |
|----------|--------|
| `OPENAI_API_KEY` | Real key |
| `ADMIN_API_KEY` | Generate new secure key |
| `ALLOWED_ORIGINS` | `https://your-store.myshopify.com,https://www.your-store.com` |
| `FLASK_DEBUG` | `false` |

---

## Phase 3: Shopify Integration (~15-30 min)

### Embed the widget:
1. Shopify Admin > Online Store > Themes > Edit Code
2. Open `Layout/theme.liquid`
3. Add before `</body>`:
```html
<script src="https://chat.your-store.com/widget.js"
        data-api-url="https://chat.your-store.com"
        data-brand="GroundCoverGroup"
        data-position="bottom-right"
        data-primary-color="#2C5E2E"
        data-welcome="Hallo! Hoe kan ik je helpen?"
        data-privacy-url="/pages/privacy-policy">
</script>
```

### Shopify gotchas to watch for:
- Widget won't appear on checkout pages (Shopify restricts scripts there — this is fine)
- Test z-index conflicts with theme elements
- Test mobile view (sticky headers/footers may overlap)
- Two consent prompts (Shopify cookies + chatbot GDPR) — acceptable for now

---

## Phase 4: Post-Launch (~ongoing)

- Monitor Railway logs + OpenAI API usage for the first week
- Set up UptimeRobot (free) on the `/health` endpoint
- Run the RAG evaluation suite once more after deployment to confirm quality
- Review chat logs for quality issues

---

## Cost Estimate

| Item | Monthly |
|------|---------|
| Railway hosting | ~$5-7 |
| OpenAI API (varies by traffic) | ~$5-20 |
| **Total** | **~$10-27/month** |

---

## Verification Plan

1. After code changes: `docker-compose up --build` locally, test chat flow
2. After Railway deploy: hit `/health` endpoint, verify `document_count > 0`
3. After Shopify embed: test chat bubble on store, check browser console for CORS errors
4. Test on mobile, test in incognito, test Dutch + English queries
