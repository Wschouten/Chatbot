# Change history — GroundCoverChatbot

Moved out of `CLAUDE.md` (2026-10-09) to keep that file short. Each section lists the
commits of one round of work and what production verification found.

## Chatlog-analyse 2026-07-29 — five phases

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

## Follow-up: sess_jLgTn7 (2026-08-25, verified in production)

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

## Rebrand to Boomschors.nl (2026-10-01, verified in production)

Ground Cover Group no longer exists (see the brand gotcha above). Replaying production
after the rebrand turned up two older routing faults as well:

| Commit | What |
|---|---|
| `67ee09e` | Name, email and phone everywhere customer-facing; `over_boomschors.txt`; guard test `test_old_brand_name_is_gone` |
| `0dfa43c` | Old name split into its own KB file so "wie zijn jullie?" stops volunteering it; `PHONE_CONTACT_RE` now catches "jullie/uw … telefoonnummer" — not bare "telefoonnummer", which customers use to give their *own* number |
| `afa817b` | `PICKUP_RE` above tracking: "kan ik mijn bestelling zelf afhalen?" hit "mijn bestelling" and got the shipment-number prompt |

Railway carries five `BRAND_*`/`SMTP_*` vars; the persona itself comes from the
defaults in `brand_config.py` — do not set `BRAND_PERSONALITY_*`, it would drop the
upsell/no-repeat rules.

**`SMTP_TO_EMAIL` stays on klantenservice@groundcovergroup.nl — that is correct, not a
leftover.** klantenservice@boomschors.nl (the address customers are given) is an alias
that forwards into that mailbox. Do not "fix" it: the MailerSend account is registered
on the groundcovergroup.nl address and the sender is a trial `mlsender.net` domain,
which only delivers to the account's own address. Any other recipient is accepted by
MailerSend, logged as "sent successfully", and never delivered — that is how the first
test escalation to boomschors.nl vanished.

## Code audit 2026-10-09 — all three phases done

A read-only, adversarially verified audit of the whole repo:
[AUDIT-2026-10-09.md](AUDIT-2026-10-09.md) (41 findings, phased plan). Fase 1 is
implemented; each fix has a test in `tests/test_audit_2026_10_regressions.py`.

| Commit | What |
|---|---|
| `2675095` | C2 — the suite blanks every integration key (see the `TESTING=1` gotcha) |
| `fd8eef0` | C1/C4 — escalation email carries name + question; sent synchronously, `handoff_done` only on success |
| `8468ecf` | C5 — a missing `session_id` gets its own id, never a shared `unknown_session` |
| `6335d0c` | C6 — frustration gate and `_flow_dead_end` go through `_start_handoff`; `flow_attempts` resets per flow |
| `305e303` | 1.8 — Shopify order/postcode flow removed; a tracking question with an 8+ digit number is looked up at once (`_statusweb_reply`) |
| `901e34b` | 1.6 — a phone number given during the handoff goes with the escalation; asking ours only pauses it |
| `23076eb` | 1.7 — loop detector needs the *last two* answers to be dead ends; declines are recorded |

Fase 2:

| Commit | What |
|---|---|
| `d871f04` | Router — `wanneer kunnen/wordt` needs an order noun, manco anchored to a delivery verb, dates/quantities are never order numbers, flows escape via the router. Verified over all 1,016 export messages |
| `229081c` | Every early return goes through `_reply()` (records the turn, logs, answers) |
| `2863dac` | "Oké" after a bot question is a yes; `volume_calc` refuses unit-less counts; StatusWeb negations → neutral reply (`classify_status`) |
| `ad35a70` | `check_output` on the `__UNKNOWN__` path; email taken out of a sentence |
| `666d84b` | Partial embed failure drops the file so the next boot retries; no duplicate tail chunk; per-write temp file |
| `880bb2c` | No names in stdout logs; portal.db orphans purged at startup; only `/portal/js/` served; CSV formula escaping |
| `c294f8d` | Portal language wired up (`lang` in each log entry, `_conversation_from_log`); persona vars out of `.env.example` |

C3 / 1.4 and Fase 3:

| Commit | What |
|---|---|
| `3b9dd75`, `115da8e` | `ProxyFix(x_for=2)` — measured in production: `remote_addr` was Railway's `100.64.0.7` for everyone, and `X-Forwarded-For` arrives as `<visitor>, <edge node>`. A spoofed header is ignored (verified). `/widget.js` and `/health` are exempt from rate limits |
| `3f74666` | Unused label POST/DELETE, `_count_tokens`, unused chunk metadata, `Actiepunten.md` |
| `8f5fbfc` | One `mocks.py`; `use_mock` means the same everywhere and `/health` says `not_configured`; one `format_transcript` for email + Zendesk; dead `BrandConfig` fields |
| `e9fc7f8` | `SUPPORT_PHONE` / `SUPPORT_EMAIL` instead of ten literal copies; one `_expired` |

Deliberately left: cut 3 (merge the three language detectors) changes retrieval and
needs `evaluate_rag.py` before and after, which bills OpenAI; cut 9 (one phone block
instead of three) is small and each block now sits at a deliberate priority. Logout
does not revoke the 4-hour admin cookie, and Zendesk mode would make the chat email the
ticket requester — both accepted risks while the cookie is HttpOnly + SameSite=Strict
and production runs in email mode. **PII in chat logs** — only email addresses are
redacted (see Conventions); names and phone numbers stay because colleagues read the
logs in the portal. Decided 2026-10-09 (Wilco): keep it that way.

## Chatlog-analyse 2026-10-09 (38 real conversations after the rebrand)

Plan and findings: [improvement-plan/CHATLOG-ANALYSE-2026-10-09.md](improvement-plan/CHATLOG-ANALYSE-2026-10-09.md).

| Commit | What |
|---|---|
| `5009483` | KB: bigbags fall under free shipping from € 50 (one session said they did not); tuinaarde settles 15–20 % |
| `da912a4` | `RESTOCK_RE` above tracking; re-ordering is `pre_purchase`; "nog niet besteld" leaves the tracking flow; no email → ask for a phone number (customer service calls back, Wilco 2026-10-09); a reference sent after the handoff is forwarded once (`_forward_addendum`); honest answer to "praat ik met een AI?" |
| `de1bbd7`, `218dcfd` | Shipping costs: `prijzen_topproducten.txt` no longer says "bij het afrekenen berekend"; `_shipping_block` injects the FAQ's `### Verzendkosten` section for any shipping-cost question (retrieval returned the product page instead). Keep that FAQ heading — a test fails without it |

Fase 3 (`d5fb260`): mid-conversation the session language holds unless `guess_language` is clear; the LLM detector only decides an undecided first message. `evaluate_rag.py` was not run: it calls `get_answer` directly with `language='nl'`, so it never touches this path.

"PGBE-…" is not a reference from the webshop or the carrier (Wilco); unknown origin.

