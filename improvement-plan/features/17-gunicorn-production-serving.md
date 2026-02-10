# Feature 17: Gunicorn Production Serving

**Track:** Infrastructure
**Effort:** 15 min
**Status:** Done
**Dependencies:** None (independent, can be done in parallel with Feature 16)

## Context

Flask's built-in development server is single-threaded and not safe for production use. Adding gunicorn as the WSGI server provides proper multi-worker request handling, graceful timeouts, and production-grade stability. The Dockerfile's healthcheck start period also needs increasing because initial ingestion of 32 knowledge base files can take several minutes.

## Files to Modify

| File | Action |
|------|--------|
| `backend/requirements.txt` | **Modify** — Add `gunicorn` |
| `Dockerfile` | **Modify** — Change CMD and increase HEALTHCHECK start-period |

## Implementation

### 1. Add gunicorn to requirements

Add `gunicorn` to `backend/requirements.txt`.

### 2. Update Dockerfile CMD (line 56)

Replace:
```dockerfile
CMD ["python", "app.py"]
```
With:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "app:app"]
```

### 3. Update Dockerfile HEALTHCHECK start-period (line 52)

Replace:
```dockerfile
HEALTHCHECK --interval=2m --timeout=10s --start-period=2m --retries=3 \
```
With:
```dockerfile
HEALTHCHECK --interval=2m --timeout=10s --start-period=5m --retries=3 \
```

## Verification

1. `docker-compose up --build` — container starts with gunicorn (logs show `[INFO] Booting worker with pid:`)
2. `GET /health` returns 200 after startup completes
3. Chat flow works as before (gunicorn should be transparent to application logic)

## Notes

- 2 workers is appropriate for a low-to-medium traffic chatbot; can be increased later via env var if needed
- `--timeout 120` gives RAG queries plenty of time (OpenAI calls can be slow)
- `--access-logfile -` sends access logs to stdout for Docker log collection
- gunicorn is Linux-only; local development on Windows continues to use `python app.py`
