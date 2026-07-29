# CLAUDE.md

Guidance for AI coding agents working in this repository. For setup, the full
environment-variable table and branding options, see [README.md](README.md) — this file
covers what the README does not: where the logic lives, how to test, and what breaks
silently.

## What this is

A RAG customer-support chatbot for GroundCoverGroup (garden ground-cover products):
Flask backend + ChromaDB + OpenAI, an embeddable chat widget for the Shopify storefront,
and an admin portal for reviewing conversations. Single-tenant. Production runs on
Railway and auto-deploys from `master`.

Primary bot language is Dutch; English is detected per message.

## Commands

```bash
# Tests — 110 tests, ~30s. Works from the repo root too: conftest.py pins the CWD.
cd backend && python -m pytest

# Run locally (Flask dev server) → http://127.0.0.1:5000
cd backend && python app.py

# Run in Docker (recommended: pinned to Python 3.11, which the RAG deps want)
docker-compose up --build

# RAG evaluation — BILLS THE OPENAI KEY. Only run when retrieval behaviour changes,
# and then run it before AND after so you have a comparison.
cd backend && python evaluate_rag.py

# Production health
curl https://chatbot-production-557f.up.railway.app/health
```

`.python-version` pins **3.11**. A newer local interpreter mostly works (the suite
passes on 3.14 with a ChromaDB/pydantic warning), but `app.py` logs a warning when it
detects it is not running in a container — prefer Docker for anything touching RAG.

## Architecture

| File | What lives there |
|---|---|
| [backend/app.py](backend/app.py) (~2,300 lines) | Flask app: security headers, CORS, rate limits, every route, and **all conversational state machines** inside `_handle_chat` ([app.py:956](backend/app.py)). The centre of gravity. |
| [backend/rag_engine.py](backend/rag_engine.py) (~1,200 lines) | `RagEngine`: ingestion, retrieval, query reformulation, context caching, plus the classifiers `detect_ticket_intent`, `detect_language`, `extract_name`. |
| [backend/admin_db.py](backend/admin_db.py) | SQLite (`portal.db`) for portal metadata: labels, notes, statuses, message ratings. |
| [backend/shipping_api.py](backend/shipping_api.py) | Van Den Heuvel StatusWeb track & trace (SOAP via `zeep`). |
| [backend/email_client.py](backend/email_client.py) / [backend/zendesk_client.py](backend/zendesk_client.py) | Human escalation — MailerSend by default, Zendesk as the alternative (`ESCALATION_METHOD`). |
| [backend/brand_config.py](backend/brand_config.py) | Persona, tone and copy, all from env vars. No branding belongs in code. |
| [backend/data_retention.py](backend/data_retention.py) | GDPR cleanup of expired sessions and logs, on startup. |
| [backend/knowledge_base/](backend/knowledge_base/) | 38 `.txt` source documents (products, FAQ, comparison guides). PDFs are supported too. |
| [frontend/static/widget.js](frontend/static/widget.js) | The **only** widget client, served at `/widget.js`. Injects its own `<style>` tag and markup; embedded with a single `data-api-url` attribute. |
| [portal/js/storage.js](portal/js/storage.js) / [portal/js/app.js](portal/js/app.js) | Admin portal SPA — `storage.js` is the data layer, `app.js` the UI. |

`backend/data/` holds sessions, chat logs, `portal.db` and `chroma_db`. It is gitignored;
in production it is a Railway volume (see Deploy).

Admin auth accepts either an `X-Admin-Key` header (scripts) or a signed HttpOnly
`admin_session` cookie valid for 4 hours (browser) — `require_admin_key`,
[app.py:282](backend/app.py). Rate limits: 200/day + 50/hour globally, 30/min on
`/api/chat`, 10/min on `/api/session` and `/admin/api/login`.

## Conversational state machines

Session state is one JSON dict per session on disk, via `get_session_state` /
`save_session_state` ([app.py:700](backend/app.py)), keyed with `awaiting_*` and
`pending_*` flags. There are four flows:

| Flow | Keys |
|---|---|
| Handoff to a human | `awaiting_name` → `awaiting_email` |
| Track & trace (StatusWeb) | `awaiting_order_number`, `pending_order_id` |
| Shopify order lookup | `awaiting_shopify_order_number` → `awaiting_shopify_postcode` |
| Stock lookup — **off in production** | `awaiting_product_name`, `pending_product_query` |

**Debugging a bad conversation:** grep for the literal bot response string in `app.py`
or `rag_engine.py`, then trace which state key produced it. That is how the handoff bug
in `d7a575f` was found — `detect_ticket_intent` matched decline keywords as substrings,
so the name "Jarno" contained "no" and the bot cheerfully gave up. Intent keywords are
now matched on word boundaries; keep it that way.

## Gotchas

Every item below has broken production at least once.

- **Mock gating.** Shipping, stock, email and Zendesk only fall back to fabricated
  responses when `USE_MOCKS` or `FLASK_DEBUG` is truthy — `_mocks_allowed()`,
  [app.py:34](backend/app.py). Production returns an honest error instead of a fake
  tracking status or a fake escalation ticket. Never add a "convenient" fallback mock
  outside that gate.
- **`TESTING=1` in the suite.** `tests/conftest.py` sets it so that importing `app`
  skips `ingest_documents()` (bills the OpenAI embeddings API, 12+ min cold) and
  `run_data_retention_cleanup()` (deletes files). It also sets `USE_MOCKS` and pins the
  CWD to `backend/`. Do not remove any of the three.
- **The knowledge base does not re-index on edit.** Ingestion skips a file when
  `<filename>_chunk_0` already exists in Chroma
  ([rag_engine.py:445](backend/rag_engine.py) for `.txt`,
  [:474](backend/rag_engine.py) for `.pdf`). New files are picked up; a **modified
  existing** file is not — and because `chroma_db` lives on the Railway volume, the
  stale index survives deploys. To push an edit through, rename the file or purge the
  index. Deleted files are cleaned up correctly (`_cleanup_stale_entries`).
- **Widget CSS versus the Shopify theme.** Styling belongs in the injected stylesheet
  string in `widget.js`, not in JS `setProperty` calls — a stylesheet rule with
  `!important` beats the theme. When pinning a fixed size, pin `min-width`/`max-width`
  as well, not just `width`: the theme's `min-width` stretched the round toggle button
  into an oval in production (`59ed947`, see [widget.js:74-79](frontend/static/widget.js)).
- **Timestamps.** Chat logs and data retention are UTC-aware; session and tracking state
  stay naive (they are only ever compared against each other). Do not mix the two
  halfway through a flow.
- **`.dockerignore` is gitignored** ([.gitignore:52](.gitignore)) and therefore never
  reaches Railway. Do not rely on it to keep anything out of the image.
- **Never commit `portal.db`.** A baked-in snapshot resets every admin label, note and
  status on each deploy.
- **Changing `OPENAI_EMBEDDING_MODEL`** requires wiping `chroma_db/` so everything is
  re-embedded. The chat model can be swapped freely.

## Deploy

Push to `master` → Railway builds from the [Dockerfile](Dockerfile) and deploys →
verify `/health`.

- Gunicorn: 1 worker, 4 threads, 120s timeout. The container starts as root only to
  `chown` the Railway-mounted volume, then drops to `appuser` via `gosu`.
- Volume `chatbot-volume` is mounted at `/app/backend/data`, so logs, sessions,
  `portal.db` and `chroma_db` persist across deploys.
- `/health` reporting `"environment": "local"` on Railway is cosmetic — `/.dockerenv`
  is absent there. The app is genuinely on Railway.

## Features deliberately off

Stock lookup and WISMO ("where is my order") are gated off until
`SHOPIFY_STOREFRONT_TOKEN` and `SHOPIFY_STORE_DOMAIN` are set on Railway —
`_stock_lookup_enabled()`, [app.py:47](backend/app.py). Without a token a stock question
falls through to RAG instead of dead-ending. Both features reactivate themselves once
the token lands. Background:
[improvement-plan/features/60-wismo-shopify-direct-api.md](improvement-plan/features/60-wismo-shopify-direct-api.md).

## Conventions

- Code, comments and docstrings in English. Customer-facing strings in Dutch, with an
  English variant where the flow supports both.
- Conventional commit messages (`fix(rag):`, `refactor(portal):`, `docs:`).
- Every bug fix gets a regression test. `backend/tests/test_fase*_regressions.py` is the
  established pattern — one file per batch of fixes, each test named after the bug.
- Session and log filenames are sanitised (`sanitize_session_id`) and logs are
  PII-redacted (`_redact_pii_for_log`) before hitting disk. Keep both in any new path
  that writes user data.
- `AUDIT-2026-07-11.md` documents a full-repo audit and the five-phase cleanup that
  followed; it is history, not a to-do list.
