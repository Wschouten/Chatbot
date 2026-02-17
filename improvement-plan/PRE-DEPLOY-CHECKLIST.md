# Pre-Deploy Checklist

**Current State:** Chatbot + Admin Portal built in VS Code, tested locally via Docker, deployed to Railway
**End Goal:** Chatbot widget embedded on Shopify store, admin portal accessible for chat log management

---

## Phase 1: Data Persistence & Backup Strategy

### 1.1 Chat Logs (✅ Already Working)
- **Current:** Chat logs saved to `backend/logs/chat_logs/` directory
- **Docker:** Logs persist via volume mount in `docker-compose.yml`
- **Railway:** Need to verify persistent storage for logs directory
- **Action Required:**
  - [ ] Verify Railway has persistent volume mounted for `/app/logs`
  - [ ] Set up log rotation (logs can grow large over time)
  - [ ] Consider backing up logs to external storage (optional)

### 1.2 Portal Metadata (⚠️ **CRITICAL GAP**)
- **Current:** Labels, notes, ratings stored in **browser localStorage only**
- **Problem:** Data lost when browser cache clears or when switching devices
- **Solutions:**

#### Option A: Backend Storage (Recommended - 2-3 hours)
Add persistence endpoints to backend:
```
POST /admin/api/conversations/:id/metadata
{
  "labels": ["urgent", "product-info"],
  "notes": [{"text": "...", "author": "admin"}],
  "rating": 5,
  "status": "resolved"
}
```

Store in SQLite database or JSON files alongside chat logs.

#### Option B: Manual Export/Import (Quick Fix - 30 min)
- Add import feature to portal
- Export portal data weekly as JSON backup
- Store backups in Railway persistent volume or external storage

**Decision needed:** Which option do you prefer?

---

## Phase 2: Environment Configuration & Secrets

### 2.1 Production Environment Variables
**Status:** Feature 27 (Todo)

Required secrets for Railway:

```bash
# Core
OPENAI_API_KEY=sk-proj-...                    # Production OpenAI key
ADMIN_API_KEY=<generate via openssl rand -hex 32>

# SMTP Email Escalation
ESCALATION_METHOD=email
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_FROM_EMAIL=<your-outlook-email>
SMTP_PASSWORD=<app-password>                  # Office 365 App Password
SMTP_TO_EMAIL=<support-inbox-email>

# CORS for Shopify
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-store.com

# Optional: Shipping API (if using real API)
SHIPPING_API_KEY=<your-shipping-api-key>
SHIPPING_API_URL=https://api.delivery-company.com
```

**Actions:**
- [ ] Generate `ADMIN_API_KEY` with `openssl rand -hex 32`
- [ ] Create Office 365 App Password for SMTP (requires Azure AD)
- [ ] Verify SMTP AUTH is enabled on sending email account
- [ ] Confirm Shopify store domains for `ALLOWED_ORIGINS`
- [ ] Store all secrets in Railway dashboard (Environment Variables tab)
- [ ] Document secrets in password manager (NOT in git)

### 2.2 Verify `.env.example` is Up-to-Date
**Status:** ✅ Complete

- [ ] Review `backend/.env.example` has all required variables documented
- [ ] Confirm no secrets are committed to git

---

## Phase 3: Local Testing & Validation

### 3.1 Docker Smoke Test (Feature 28 - 15 min)
**Prerequisites:** Features 25 & 26 complete (✅ Done)

Run complete Docker validation:

```powershell
# 1. Build and start
docker-compose up --build

# 2. Wait for health check
curl http://localhost:5000/health
# Expected: 200 OK, document_count > 0

# 3. Test chatbot
# Open http://localhost:5000 in browser
# - GDPR consent appears
# - Ask "Wat is houtmulch?" → relevant answer
# - Follow up "en de prijs?" → contextual answer (Feature 25)
# - Ask in English → English response
# - Test email escalation flow

# 4. Verify Gunicorn
docker logs <container_name> | Select-String "gunicorn"
# Should show worker boot messages

# 5. Test admin portal
# Open http://localhost:5000/portal.html
# Login with ADMIN_API_KEY
# Verify chat logs appear
```

**Actions:**
- [ ] Complete Docker smoke test
- [ ] Document any issues found
- [ ] Fix issues before proceeding

### 3.2 End-to-End Acceptance Testing (Feature 29 - 30 min)
**Prerequisites:** Feature 28 passes

Full test matrix (see [29-end-to-end-acceptance-testing.md](features/29-end-to-end-acceptance-testing.md)):

**Functional:**
- [ ] GDPR consent
- [ ] Dutch + English conversations
- [ ] Follow-up query resolution (Feature 25)
- [ ] Escalation flow + email sent
- [ ] Session persistence
- [ ] Unknown question handling
- [ ] Shipping order confirmation flow (Features 31-35)

**Technical:**
- [ ] Health endpoint healthy
- [ ] No browser console errors
- [ ] Gunicorn serving (not Flask dev)
- [ ] ChromaDB graceful on Python 3.14 (Feature 26)

**Actions:**
- [ ] Run full acceptance test
- [ ] Fix any failing tests
- [ ] Get sign-off before Railway deployment

---

## Phase 4: Railway Deployment

### 4.1 Pre-Deploy Checks
- [ ] All local tests pass (Features 28 & 29)
- [ ] All code committed and pushed to `master`
- [ ] Production secrets prepared and documented
- [ ] Railway project created and connected to GitHub repo

### 4.2 Railway Configuration

**Environment Variables:**
```bash
# Copy all production secrets from Phase 2.1 into Railway dashboard
# Settings → Variables → Add each one
```

**Build Configuration:**
- [ ] Railway auto-detects `Dockerfile` (should work automatically)
- [ ] Verify build command: `docker build -t chatbot .`
- [ ] Verify start command: uses `gunicorn` from Dockerfile

**Persistent Storage:**
- [ ] Add persistent volume for `/app/logs` (chat logs)
- [ ] If using backend portal storage (Option A), add volume for database

**Networking:**
- [ ] Note Railway-provided domain (e.g., `chatbot-production.up.railway.app`)
- [ ] Configure custom domain if needed (optional)
- [ ] Update `ALLOWED_ORIGINS` to include Railway domain

### 4.3 Deploy & Verify

**Deploy:**
```bash
# Railway auto-deploys on git push to master
git push origin master

# Or trigger manual deploy in Railway dashboard
```

**Verify Deployment:**
```bash
# 1. Check Railway logs for successful startup
# Look for: "OpenAI Client Initialized Successfully"
# Look for: "Ingestion Complete. X documents processed"

# 2. Test health endpoint
curl https://chatbot-production.up.railway.app/health
# Expected: 200 OK, document_count > 0

# 3. Test chatbot
# Open https://chatbot-production.up.railway.app
# Run basic chat flow test

# 4. Test admin portal
# Open https://chatbot-production.up.railway.app/portal.html
# Login with ADMIN_API_KEY
# Verify conversations sync from backend

# 5. Test email escalation
# Trigger escalation flow
# Verify email arrives at SMTP_TO_EMAIL
```

**Actions:**
- [ ] Deploy to Railway
- [ ] Verify all tests pass on Railway URL
- [ ] Fix any Railway-specific issues
- [ ] Document Railway URL

---

## Phase 5: Shopify Integration

### 5.1 Widget Embedding

**Get Widget Code:**
The chatbot widget is served from Railway. To embed on Shopify:

```html
<!-- Add to Shopify theme's theme.liquid before </body> -->
<script src="https://chatbot-production.up.railway.app/static/widget.js"></script>
```

**Shopify Setup:**
1. Log in to Shopify admin
2. Go to **Online Store → Themes**
3. Click **Actions → Edit code** on active theme
4. Open `Layout/theme.liquid`
5. Add widget script before `</body>` tag
6. **Save**

**Test on Shopify:**
- [ ] Visit your Shopify storefront
- [ ] Verify chat bubble appears (bottom right)
- [ ] Click bubble → chat widget opens
- [ ] Test full conversation flow
- [ ] Verify email escalation works from Shopify

### 5.2 CORS Configuration

**Update Railway Environment:**
```bash
ALLOWED_ORIGINS=https://your-store.myshopify.com,https://www.your-store.com
```

Replace with your actual Shopify domains. Include:
- Your `.myshopify.com` domain
- Any custom domains pointing to your Shopify store

**After updating:**
- [ ] Redeploy Railway (auto-deploys on env var change)
- [ ] Test widget on Shopify again
- [ ] Verify no CORS errors in browser console

### 5.3 Customize Widget Appearance (Optional)

Edit `frontend/static/widget.js` to customize:
- Bubble position
- Colors (brand matching)
- Welcome message
- Widget size

**After customization:**
```bash
git add frontend/static/widget.js
git commit -m "customize widget appearance for Shopify"
git push origin master
# Railway auto-deploys
```

---

## Phase 6: Monitoring & Maintenance

### 6.1 Railway Monitoring
- [ ] Set up Railway health check alerts (Settings → Health Checks)
- [ ] Configure uptime monitoring (Uptime Robot, Pingdom, or Railway built-in)
- [ ] Set up log retention policy in Railway

### 6.2 Portal Access
- [ ] Share Railway URL + `ADMIN_API_KEY` with authorized users
- [ ] Document login instructions:
  - URL: `https://chatbot-production.up.railway.app/portal.html`
  - Username: (any name for display)
  - Password: `ADMIN_API_KEY` value

### 6.3 Backup Strategy
- [ ] **Chat Logs:** Backed up via Railway persistent volume
- [ ] **Portal Metadata:**
  - If using backend storage (Option A): Included in Railway backups
  - If using localStorage (Option B): Weekly manual export via portal

### 6.4 SMTP Maintenance
- [ ] Test email escalation weekly
- [ ] Rotate Office 365 App Password every 6 months (Azure AD security)
- [ ] Monitor SMTP quota (Office 365 has sending limits)

---

## Phase 7: Optional Enhancements (Post-Launch)

### 7.1 Portal Backend Storage (if not done in Phase 1)
**Effort:** 2-3 hours
- Add SQLite database for portal metadata
- Migrate localStorage data to backend
- Enables multi-device access and permanent storage

### 7.2 Custom Domain for Railway
**Effort:** 15 min
- Register domain or use subdomain (e.g., `chat.your-store.com`)
- Point DNS to Railway
- Configure in Railway dashboard

### 7.3 Analytics Integration
**Effort:** 1 hour
- Add Google Analytics to widget
- Track conversation metrics (volume, escalation rate, etc.)
- Integrate with Shopify analytics

### 7.4 Real Shipping API Integration
**Effort:** 1 hour
- Replace mock shipping API with real integration
- Add `SHIPPING_API_KEY` and `SHIPPING_API_URL` to Railway
- Test order tracking flow

---

## Summary: What's Left To Do

| Phase | Task | Effort | Status | Blocker |
|-------|------|--------|--------|---------|
| **1** | Portal Metadata Storage Decision | 5 min | 🟡 Todo | Need your decision: Option A or B |
| **2** | Generate Production Secrets | 15-30 min | 🟡 Todo | Need Office 365 App Password |
| **3** | Local Docker Smoke Test (Feature 28) | 15 min | 🟡 Ready | — |
| **3** | End-to-End Acceptance Testing (Feature 29) | 30 min | 🟡 Ready | Blocked by Feature 28 |
| **4** | Railway Deployment | 15 min | 🟡 Ready | Blocked by Phase 2 & 3 |
| **5** | Shopify Widget Integration | 15 min | 🟡 Ready | Blocked by Phase 4 |
| **6** | Monitoring Setup | 15 min | 🟡 Ready | Blocked by Phase 4 |

**Total Remaining:** ~1.5-2 hours (excluding portal backend storage if chosen)

---

## Critical Decision Needed

**Portal Metadata Storage:** Do you want to implement backend storage (Option A - 2-3 hours) or use manual export/import (Option B - 30 min)?

**My recommendation:** Start with Option B (quick fix) to get deployed quickly, then add Option A (backend storage) as a post-launch enhancement if needed.

Let me know your decision and I'll help you proceed!
