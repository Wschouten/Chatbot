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
# Tests — 241 tests, ~15s. Works from the repo root too: conftest.py pins the CWD.
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
| [backend/volume_calc.py](backend/volume_calc.py) | `compute_volume` — deterministic m²/m³/litre arithmetic, injected into the prompt as a fact so the model never multiplies. Returns `None` unless the dimensions parse with confidence. |
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

**Routing happens in one place.** `classify_intent(message)` ([app.py](backend/app.py))
returns exactly one label per fresh message, in a fixed priority order:
`human_request > order_admin > escalate_topic > pre_purchase > return_payment >
tracking > stock > rag`. Everything that needs a human returns before the flows below
are reached. Do not add a competing regex check next to a flow — extend the router,
or the old failure comes back: routing used to be independent regexes in reading
order, so "ik wil iemand spreken over mijn bestelling" matched `TRACKING_INTENT_RE`
on "mijn bestelling" and got the shipment-number prompt.

Every path into the handoff goes through `_start_handoff`, which is where the
already-handed-off guard and the skip-the-name-if-known shortcut live. Adding a new
entry point means calling that, not setting `state = 'awaiting_name'` yourself.

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
- **The output gate only sees model output.** `check_output` ([rag_engine.py](backend/rag_engine.py))
  rejects foreign scripts, leaked system vocabulary and the wrong language, retries once
  and otherwise returns a safe answer. It cannot see the canned flow strings in
  `app.py` — those follow `state_data['language']`, which used to stick for a whole
  conversation (seven English messages to a Dutch customer). `guess_language` corrects
  the stored value per message; keep any new canned copy behind that, not behind a
  hard-coded language.
- **A shortcut that returns before the RAG must answer completely — and record its
  turn.** `PHONE_CONTACT_RE` returns a canned reply, so no question *about* the phone
  ever reaches the knowledge base: "vanaf hoe laat kan ik telefonisch contact opnemen?"
  got the bare number twice in a row (`sess_jLgTn7`, 2026-08-24). The hours now live in
  `SUPPORT_HOURS_NL`/`_EN` next to the regex, and `tests/test_knowledge_base.py` asserts
  they still match `knowledge_base/openingstijden.txt`. The same block also returned
  without appending to `state_data['chat_history']`, so the *next* message was
  reformulated against a history that ended two turns earlier — "tussen welke tijden kan
  dat?" was rewritten against the delivery question and answered with a delivery time.
  Every canned early return goes through `_remember_turn`; a new one must too.
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

## Chatlog-driven improvements — all five phases done

An analysis of 257 production conversations (2026-04-22 → 2026-07-29) produced a
five-phase plan: [improvement-plan/CHATLOG-ANALYSE-2026-07-29.md](improvement-plan/CHATLOG-ANALYSE-2026-07-29.md).
It records the findings with real transcripts, the session ids, and the cause of each as
`file:line` — read it before touching routing, the system prompt or the KB. Each phase
section now also records what its production verification found.

All five are deployed and verified against production (fase 1–2 on 2026-07-29, fase 3–5
on 2026-07-30). Test suite went from 133 to 232.

| Fase | What | Where |
|---|---|---|
| 1 | Escape hatch out of every guided flow, shipment-number validation | `app.py` |
| 2 | KB cleanup, re-indexing on `content_hash` | `knowledge_base/`, `rag_engine.py` |
| 3 | Prompt hardening (7 rules) | `rag_engine.py`, before/after in [improvement-plan/rag/fase3-before-after.md](improvement-plan/rag/fase3-before-after.md) |
| 4 | `classify_intent` + escalation catalogue | `app.py` |
| 5 | Output gate, `volume_calc.py`, pasted product URLs | `rag_engine.py`, `volume_calc.py` |

Known leftovers, all deliberate and small: a policy question about the delivery date
escalates unnecessarily, one session escapes the catalogue through a typo ("niet gied op
de website"), and the KB has no dimensions for the solid plastic posts, so the "7 mm"
question still cannot be answered.

### Follow-up: sess_jLgTn7 (2026-08-25, verified in production)

One conversation from 2026-08-24 — a customer asking from what time we answer the phone,
answered three times without ever naming the hours — produced three fixes, each a
different layer:

| Commit | Layer | What |
|---|---|---|
| `7424d47` | `app.py` | The canned phone reply names the hours (`SUPPORT_HOURS_NL`/`_EN`), and every canned early return records its turn via `_remember_turn` |
| `90c9beb` | `knowledge_base/` | "Douglas Premium" was nowhere in the KB, so retrieval matched it against the discontinued "Douglas Excellent" and told a buying customer we no longer sell it |
| `4f2a839` | `rag_engine.py` | The bot now tutoyeert consistently, even when the customer writes "u" |

Still open from this session: the Douglas Premium big bag has no fraction, price or
volume in the KB, so "hoeveel zit er in?" for that article cannot be answered yet.

### What this taught, and is still true

- **Verify against the real export, not against reconstructed sentences.** The first
  version of the fase-4 catalogue was written from this repo's own summaries and missed
  most of the actual customer phrasings. Running the classifier over all 803 user
  messages in `chat-export-2026-07-29.json` found that in minutes; the tests never
  would have. Same for the fase-5 output gate: 7 of its 10 language flags turned out to
  be canned `app.py` strings, which the gate cannot see at all.
- **Prompt work has a ceiling, and it is `app.py`.** Two fase-3 findings could not be
  fixed by any prompt rule because the message never reached the model — the state
  machine answered first. If a bad answer never seems to change, check whether the LLM
  is even involved.
- **Escalation cannot be forced from the KB.** The prompt forbids the bot from sending
  `__HUMAN_REQUESTED__` on its own judgement, so a KB file saying "refer to a colleague"
  has no effect when another KB file answers the same question substantively. Since
  fase 4 that judgement is deterministic instead: `ORDER_ADMIN_RE` / `ESCALATE_TOPIC_RE`.
- **A KB contradiction is fixed in the source file, never in the prompt.**
- **A prompt's examples outweigh its adjectives.** The persona said "vriendelijk,
  informeel", but the one sample sentence in the whole Dutch prompt read "Bedoelt *u*
  misschien de rozenkever?" — and the bot drifted to the formal form mid-conversation
  while every canned `app.py` string tutoyeerde. Adding a rule was half the fix; the
  other half was correcting the example. `test_fase3_prompt_hardening.py` now fails on
  any `u`/`uw` anywhere in the Dutch prompt, not just on a missing rule.
- **A near-miss product name is worse than an unknown one.** A KB that names only the
  discontinued variant makes retrieval confidently deny a product that is on sale
  ("Douglas Premium" matched "Douglas Excellent — uit het assortiment"). When a
  discontinued product has a still-available sibling, name both, in both files.
- **Every prompt rule can overshoot in the other direction.** "Never infer a country from
  a place name" made the bot withhold Dutch shipping costs entirely; "do not dispute the
  customer" plus "give the answer again" made it reply "Dat klopt niet; ik heb dat net
  wel genoemd." Both only showed up when replayed against production, not in the tests.

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
