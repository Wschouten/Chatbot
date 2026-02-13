# Feature 28: Local Docker Smoke Test

**Track:** Quality Assurance
**Effort:** 15 min
**Status:** Todo
**Dependencies:** Features 25 and 26 (all code changes must be merged before validating)

## Context

Before deploying to Railway, the complete application must be validated locally via Docker to catch any issues early. This is a gate between code changes and cloud deployment — all code features (25, 26) should be complete before running this test.

## Steps

### 1. Build and start

```powershell
docker-compose up --build
```

Wait for the health check to pass and the log line showing document ingestion is complete.

### 2. Verify health endpoint

```powershell
curl http://localhost:5000/health
```

Expected: `200 OK` with `"status": "healthy"` and `document_count > 0`.

### 3. Test core chat flow

Open `http://localhost:5000` in a browser and verify:

| Test | Expected |
|------|----------|
| GDPR consent prompt | Appears before first message |
| Ask "Wat is houtmulch?" | Relevant answer about houtmulch |
| Follow up "en de prijs?" | Answer about houtmulch pricing (Feature 25 validation) |
| Ask in English | Response in English |
| Ask unanswerable question | Graceful "I don't know" response |

### 4. Test email escalation flow

1. Trigger escalation (unanswerable question > request human > provide name + email)
2. Verify confirmation message appears in chat
3. Check that email was sent to the configured `SMTP_TO_EMAIL`

### 5. Test gunicorn workers

Verify the container is running gunicorn (not Flask dev server):

```powershell
docker logs <container_name> | Select-String "gunicorn"
```

Should show gunicorn worker boot messages.

## Verification

1. Docker build completes without errors
2. Health endpoint returns healthy with documents loaded
3. Chat flow works end-to-end in both Dutch and English
4. Follow-up questions resolve correctly (Feature 25)
5. Application doesn't crash on Python 3.14 import issues (Feature 26)
6. Email escalation sends a real email
7. Gunicorn is serving (not Flask dev server)

## Notes

- If any test fails, fix the issue and re-test before proceeding to Feature 20 (Railway deployment)
- This is a manual smoke test, not automated — it supplements the RAG evaluation suite
- Keep Docker running during testing; stop with `docker-compose down` when done
