# Feature 29: End-to-End Acceptance Testing

**Track:** Quality Assurance
**Effort:** 30 min
**Status:** Todo
**Dependencies:** Feature 28 (Local Docker Smoke Test must pass)

## Context

With Features 20 (Railway), 21 (Shopify), and 22 (Monitoring) removed from scope, acceptance testing focuses on the local Docker deployment. This is the final QA gate to confirm all features work end-to-end.

## Test Matrix

### Functional Testing (via `http://localhost:5000`)

| Test | Steps | Expected |
|------|-------|----------|
| GDPR consent | Open incognito, load chatbot | Consent prompt appears before first message |
| Dutch conversation | Ask "Wat is houtmulch?" | Relevant Dutch answer |
| English conversation | Ask "What is bark mulch?" | Relevant English answer |
| Follow-up query (Feature 25) | Ask about a product, then follow up with "en de prijs?" | Correctly resolves context using reformulated query |
| Escalation flow | Ask unanswerable > request human > name > email | Confirmation message + email sent |
| Session persistence | Chat, close widget, reopen | Previous messages preserved |
| Unknown question handling | Ask "Verkopen jullie meststoffen?" | Helpful "I don't know" response (not a crash) |

### Technical Verification

| Check | How | Expected |
|-------|-----|----------|
| Health endpoint | `curl http://localhost:5000/health` | `200 OK`, `document_count > 0` |
| No console errors | Browser DevTools > Console | No JavaScript errors |
| Gunicorn serving | `docker logs <container>` | Gunicorn worker boot messages |
| Graceful degradation (Feature 26) | App starts on Python 3.14 host | No crash from ChromaDB import |

### RAG Evaluation (optional, requires Python 3.12/3.13 venv)

```powershell
cd backend
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python evaluate_rag.py
```

- All test cases (including follow-up cases from Feature 25) should pass
- Review the generated `evaluation/evaluation_report.md`

## Verification

1. All functional tests pass in browser
2. Health endpoint returns healthy with documents loaded
3. Follow-up questions resolve correctly (Feature 25)
4. App doesn't crash on import issues (Feature 26)
5. Email escalation sends a real email (if SMTP configured)
6. Gunicorn is serving (not Flask dev server)

## Notes

- If SMTP is not configured, escalation will use mock mode (check logs for mock output)
- The RAG evaluation requires Python 3.12 or 3.13 (ChromaDB doesn't work on 3.14)
