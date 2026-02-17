# Feature 43: Local Docker Smoke Test

**Effort:** ~15 min
**Status:** Todo
**Priority:** High (validates before deployment)
**Dependencies:** Feature 41 (committed code), Feature 42 (secrets ready)
**Blocks:** Feature 44

---

## Problem

Need to validate the complete application works in Docker before deploying to Railway. Catches issues that only appear in the containerized environment (Gunicorn, file paths, volumes, etc.).

---

## Test Procedure

### Setup

```bash
# Create .env from template (fill in real values)
cp backend/.env.example backend/.env
# Edit backend/.env with production secrets

# Build and start
docker-compose up --build
```

### Test 1: Health Check

```bash
curl http://localhost:5000/health
```

**Expected:** HTTP 200 with:
- `"status": "healthy"`
- `"document_count"` > 0
- `"openai"` status ok
- `"shipping_api"` status (mock_mode or configured)

### Test 2: Dutch Chat

1. Open http://localhost:5000
2. Accept GDPR consent
3. Ask: "Wat is houtmulch?"
4. Verify: Relevant Dutch answer about wood mulch

### Test 3: English Chat

1. Ask: "What ground cover products do you have?"
2. Verify: Relevant English answer

### Test 4: Follow-up Context (Feature 25)

1. Ask: "Wat is boomschors?"
2. Follow up: "En de prijs?"
3. Verify: Answer about boomschors pricing (not a generic response)

### Test 5: Shipping Flow (Features 31-35)

1. Ask: "Waar is mijn bestelling 12345?"
2. Verify: Confirmation prompt appears
3. Confirm with "ja"
4. Verify: Mock shipping status returned (or real if API key configured)

### Test 6: Admin Portal

1. Open http://localhost:5000/portal
2. Login with ADMIN_API_KEY
3. Verify: Conversations list appears
4. Select a conversation
5. Add a label, add a note, set a rating
6. **Refresh the page (F5)**
7. Verify: All metadata persists after refresh

### Test 7: Backend Persistence

1. Add metadata in portal (labels, notes, ratings)
2. **Clear browser localStorage** (DevTools > Application > Clear)
3. Refresh and re-login
4. Verify: Metadata still shows (confirms backend SQLite storage, not localStorage)

### Test 8: Email Escalation (if SMTP configured)

1. Trigger escalation flow in chat
2. Verify: Email arrives at SMTP_TO_EMAIL

### Test 9: Container Restart

```bash
docker-compose down
docker-compose up
```

1. Verify: Previous conversations still visible in portal
2. Verify: Chat logs persist
3. Verify: Admin metadata persists

---

## Pass Criteria

- [ ] Health endpoint returns 200 with document_count > 0
- [ ] Dutch and English conversations work
- [ ] Follow-up context resolution works
- [ ] Shipping order flow works (mock or real)
- [ ] Portal shows conversations with metadata
- [ ] Metadata persists across page refresh
- [ ] Metadata persists after clearing localStorage (backend storage works)
- [ ] Metadata persists across container restart
- [ ] No errors in browser console
- [ ] No errors in Docker logs (check with `docker-compose logs`)
