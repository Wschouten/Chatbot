# Security Hardening Checklist

All items are ordered by security impact. Total estimated effort: ~80 minutes.

---

## 1. Rotate All Exposed API Keys

**Status:** :black_square_button: Todo
**Effort:** 15 min (manual)
**Impact:** Critical

The `backend/.env` file contains real credentials. Even though `.env` is in `.gitignore`, these keys should be rotated as a precaution.

**Actions:**
- [ ] **OpenAI API Key**: Revoke at https://platform.openai.com/api-keys, generate new key, update `.env`
- [ ] **Zendesk API Token**: Revoke at Zendesk admin panel, generate new token, update `.env`
- [ ] **ADMIN_API_KEY**: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`, update `.env`

---

## 2. Create `.env.example` Template

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** New `backend/.env.example`

Create a template with placeholder values for all environment variables so new developers can onboard safely without ever seeing real credentials.

**Variables to include:**
- `OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE`
- `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN` (placeholders)
- `ADMIN_API_KEY=CHANGE_ME_generate_a_secure_key_here`
- `ALLOWED_ORIGINS=http://localhost:5000`
- `DATA_RETENTION_SESSIONS_DAYS=30`, `DATA_RETENTION_LOGS_DAYS=90`
- All `BRAND_*` variables with generic defaults
- New: `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL` (from RAG plan)

---

## 3. Add ADMIN_API_KEY Startup Validation

**Status:** :black_square_button: Todo
**Effort:** 10 min
**File:** `backend/app.py` (after `load_dotenv()`, ~line 24)

**Changes:**
- Add check that refuses to start if ADMIN_API_KEY is still the placeholder value
  - In debug mode: log a critical warning but allow startup
  - In production: raise `SystemExit`
- At line 424, replace `provided_key != admin_key` with `secrets.compare_digest(provided_key, admin_key)` for constant-time comparison (prevents timing attacks)
  - `secrets` is already imported at line 7

---

## 4. Fix Content Security Policy

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** `backend/app.py` line 71

**Current:** `"script-src 'self' 'unsafe-inline'; "`
**Target:** `"script-src 'self'; "`

**Why safe to remove:** The app uses external script files only (`widget.js`, `script.js`). No inline `<script>` blocks exist in `index.html`. The widget uses DOM manipulation (`innerHTML`) for its own container, but that's not inline script execution — it doesn't require `'unsafe-inline'` in `script-src`.

Keep `'unsafe-inline'` in `style-src` — it's needed for Google Fonts injection and one inline style in `index.html` line 18.

---

## 5. Validate ALLOWED_ORIGINS at Startup

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** `backend/app.py` (after line 42)

**Changes:**
- Strip whitespace from each origin after splitting
- Log a warning if any origin contains placeholder-like strings (`your-`, `example`, `placeholder`)
- Remove the Shopify placeholder from `.env` if still present

---

## 6. Enhance Health Check Endpoint

**Status:** :black_square_button: Todo
**Effort:** 15 min
**Files:** `backend/app.py` (line 148), `Dockerfile`

Replace the trivial `/health` endpoint with dependency-aware checks:
- **ChromaDB**: Verify collection exists and return document count
- **OpenAI client**: Verify client is initialized (no live API call — too expensive)
- **Zendesk**: Report if configured or running in mock mode

Return `200` if all critical deps are ok, `503` if ChromaDB or OpenAI are down.

Also update `Dockerfile` HEALTHCHECK:
- Increase `--start-period` from 5s to 30s (RAG engine needs time to ingest documents at startup)

---

## 7. Add PII Redaction to Conversation Logs

**Status:** :black_square_button: Todo
**Effort:** 10 min
**File:** `backend/app.py` (before logging block ~line 376)

**Changes:**
- Add `_redact_pii_for_log(text)` function that replaces email addresses with `[EMAIL_REDACTED]`
- Apply to both `user_message` and `response_text` before writing to the conversation log JSON files
- Keeps logs useful for debugging while reducing PII exposure risk

---

## 8. Add Cache-Control Headers for API Routes

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** `backend/app.py` — in `add_security_headers()` function

**Changes:**
Add to the `@app.after_request` handler:
```python
if request.path.startswith('/api/'):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
```

Prevents browsers and intermediate proxies from caching chat responses that may contain personal data (names, emails from ticket creation flow).

---

## 9. Create `.dockerignore`

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** New `.dockerignore` (repo root)

The `COPY . /app` in the Dockerfile currently copies everything into the image, including `.git/`, test files, and potentially `.env` if it exists at build time.

**Contents:**
```
.git
.gitignore
.claude
.env
*.env
backend/.env
backend/tests
backend/__pycache__
backend/chroma_db
backend/sessions
backend/logs
agent
improvement-plan
*.md
*.pyc
__pycache__
.pytest_cache
.coverage
htmlcov
nul
```

---

## 10. Tighten Directory Permissions in Dockerfile

**Status:** :black_square_button: Todo
**Effort:** 5 min
**File:** `Dockerfile`

**Changes:**
Add `chmod 700` on sessions and logs directories after creating them:
```dockerfile
RUN chmod 700 /app/backend/sessions /app/backend/logs
```

Ensures only `appuser` can read/write these directories, even if the container is compromised through another vector.

---

## What This Checklist Does NOT Cover (Intentionally)

- **Full encryption at rest for logs** — PII redaction + directory permissions are sufficient for single-client deployment
- **Redis for rate limiting** — in-memory is fine for single-instance
- **CSRF protection** — JSON-only API with CORS is not vulnerable to form-based CSRF
- **WAF rules** — belongs at the reverse proxy layer
- **HTTPS** — assumed to be handled by reverse proxy in production
- **User authentication for chat** — public-facing widget; rate limiting is the appropriate control
