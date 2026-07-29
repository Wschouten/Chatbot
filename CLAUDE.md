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
# Tests — 133 tests, ~30s. Works from the repo root too: conftest.py pins the CWD.
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
| [backend/knowledge_base/](backend/knowledge_base/) | 40 `.txt` source documents (products, FAQ, comparison guides, policy). PDFs are supported too. |
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
- **The knowledge base re-indexes on edit via a content hash** (since 2026-07-29).
  Every chunk stores `content_hash`; `ingest_documents` skips a file only when the
  stored digest still matches, and otherwise deletes the file's chunks
  (`collection.delete(where={"source": ...})`) before re-embedding. Renaming files to
  force an update is no longer needed. Deleted files are still cleaned up by
  `_cleanup_stale_entries`. Two things to keep in mind: chunks indexed *before* this
  change carry no digest, so the first run after deploying it re-embeds the whole KB
  once (bills the embeddings API); and editing a KB file now costs an embedding call
  per chunk on the next boot, so batch your edits.
  Never reintroduce a skip that looks only at whether `<filename>_chunk_0` exists —
  because `chroma_db` lives on the Railway volume, that made a stale answer survive
  every deploy (the "kooiaap" FAQ was answered wrong in production for weeks while the
  corrected text sat in the file).
- **Guided flows need an escape hatch.** `_handle_chat` checks
  `PHONE_CONTACT_RE` / `HUMAN_ESCALATION_RE` / `FRUSTRATION_RE` **before** the
  tracking/Shopify/stock state machines, and `_flow_dead_end()` hands over to a human
  after two failed attempts in the same flow. Without it a customer could not get out:
  "Echte persoon" was answered with the shipment-number prompt eight times in a row.
  Any new `awaiting_*` flow must be added to `GUIDED_FLOW_KEYS`.
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

## Current work: chatlog-driven improvements

An analysis of 257 production conversations (2026-04-22 → 2026-07-29) produced a
five-phase plan: [improvement-plan/CHATLOG-ANALYSE-2026-07-29.md](improvement-plan/CHATLOG-ANALYSE-2026-07-29.md).
It records the findings with real transcripts, the session ids, and the cause of each as
`file:line` — read it before touching routing, the system prompt or the KB.

- **Fase 1 (escape hatch, input validation) — done, deployed, verified 2026-07-29.**
- **Fase 2 (knowledge base) — done, deployed, verified 2026-07-29.** Business-policy
  answers that fed into it: [improvement-plan/OPENSTAANDE-VRAGEN-KB.md](improvement-plan/OPENSTAANDE-VRAGEN-KB.md).
- **Fase 3 (prompt hardening) — open.** Fabricated actions ("26 mei heb ik genoteerd"),
  the `'Zoals ik eerder noemde'` phrase the prompt itself prescribes, internal system
  language reaching customers ("staat niet in de context"), yes/no misalignment.
- **Fase 4 (intent router + escalation catalogue) — open.** The largest change; own PR.
- **Fase 5 (output sanitizer + arithmetic helper) — open.** Language flips, foreign-script
  characters mid-sentence, one confirmed volume miscalculation.

Two constraints learned the hard way while doing Fase 2, both still true:

- **Escalation cannot be forced from the KB.** The prompt explicitly forbids the bot from
  sending `__HUMAN_REQUESTED__` on its own judgement, so a KB file saying "refer to a
  colleague" has no effect when another KB file answers the same question substantively —
  the bot picks the substantive answer. The working pattern is: allow one factual answer,
  put the boundary at the follow-up, and say so in *every* file touching the topic.
  Deterministic escalation is Fase 4 work.
- **A KB contradiction is fixed in the source file, never in the prompt.**

## Conventions

- Code, comments and docstrings in English. Customer-facing strings in Dutch, with an
  English variant where the flow supports both.
- Conventional commit messages (`fix(rag):`, `refactor(portal):`, `docs:`).
- Every bug fix gets a regression test. `backend/tests/test_fase*_regressions.py` is the
  established pattern — one file per batch of fixes, each test named after the bug. Fixes
  that come out of a chatlog analysis go in `test_chatlog_regressions.py`, named after the
  production session that exposed them (`test_sess_7xo9rz_...`).
- `tests/test_knowledge_base.py` guards the KB source files: the build fails on unfilled
  template text (`[INVULLEN]`, `TODO`) or a wrong customer-service phone number. Unfilled
  placeholders used to be read out to customers verbatim.
- A test module that posts many chat messages must set `flask_app.limiter.enabled = False`,
  not just `RATELIMIT_ENABLED` — otherwise the 30/min cap on `/api/chat` leaks into later
  modules as 429s.
- Session and log filenames are sanitised (`sanitize_session_id`) and logs are
  PII-redacted (`_redact_pii_for_log`) before hitting disk. Keep both in any new path
  that writes user data.
- `AUDIT-2026-07-11.md` documents a full-repo audit and the five-phase cleanup that
  followed; it is history, not a to-do list.
