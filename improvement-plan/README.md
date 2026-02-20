# GroundCover Chatbot Improvement Plan

## Overview

The GroundCover Chatbot is a RAG-based customer support bot for GroundCoverGroup (Dutch garden/landscaping products). It has a solid foundation: modular Flask + ChromaDB + OpenAI architecture, good prompt engineering with safety guardrails, GDPR-compliant data retention, Docker setup with non-root user, rate limiting, and an embeddable widget with privacy consent.

The original plan focused on two areas:
1. **Security Hardening** — credential management, CSP, logging safety
2. **RAG Quality** — evaluation framework, retrieval improvements, knowledge base content

Both are now complete. The project has also grown significantly beyond the original plan with an admin portal, email escalation system, and shipping API integration.

## Current State Assessment (Updated 2026-02-18)

| Area | Score | Notes |
|---|---|---|
| Architecture | 9/10 | Extended with admin portal, email client, shipping API, gunicorn |
| Prompt Engineering | 9/10 | English translation clarified, safety guardrails solid |
| Security | 9/10 | All 10 checklist items complete |
| RAG Retrieval | 9/10 | Metadata, distance filtering, source diversity, 100% eval pass rate |
| Knowledge Base | 9/10 | 36 files (was 32): 3 comparison guides + Cacaodoppen added |
| Testing | 7/10 | RAG evaluation framework (100% pass rate), multiple integration test scripts |
| Deployment | 9/10 | Dockerignore, chmod 700, enhanced health check, gunicorn, 2m start-period |

## Implementation Steps

| Step | Task | Status | Details |
|---|---|---|---|
| 0 | Create improvement plan folder | :white_check_mark: Done | This folder |
| 1 | Rotate all exposed API keys | :white_check_mark: Done | Manual — OpenAI, ADMIN_API_KEY (Zendesk replaced by email) |
| 2 | Security quick wins | :white_check_mark: Done | [Security checklist](security/checklist.md) items 2-5 |
| 3 | Security remaining items | :white_check_mark: Done | [Security checklist](security/checklist.md) items 6-10 |
| 4 | Make LLM model configurable | :white_check_mark: Done | `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, `RAG_RELEVANCE_THRESHOLD` env vars |
| 5 | Build RAG evaluation framework | :white_check_mark: Done | `backend/evaluate_rag.py` + `backend/evaluation/test_set.json` (28 questions) |
| 6 | Run baseline evaluation | :white_check_mark: Done | Used as starting point before retrieval improvements |
| 7 | Metadata + retrieval improvements | :white_check_mark: Done | `_extract_metadata_from_content()`, distance filtering, source diversity (n=10, max 2/source) |
| 8 | Run evaluation | :white_check_mark: Done | 100% pass rate, avg 3.02s latency |
| 9 | Knowledge base content improvements | :white_check_mark: Done | 3 comparison guides, cross-references, Cacaodoppen; thin files expanded |
| 10 | English language prompt fix | :white_check_mark: Done | System prompt: "translate all information to English" when user speaks English |
| 11 | Run final evaluation | :white_check_mark: Done | 28/28 pass (100%), all categories ≥ LLM score 4.2/5 |

## RAG Evaluation Results (2026-02-06)

| Category | Questions | Pass Rate | Avg Latency | Avg LLM Score |
|---|---|---|---|---|
| Product Info | 10 | 100% | 3.37s | 4.4/5 |
| FAQ / Policy | 6 | 100% | 2.08s | 4.8/5 |
| Cross-product | 5 | 100% | 4.12s | 4.2/5 |
| English Queries | 3 | 100% | 4.00s | 4.7/5 |
| Hallucination Check | 4 | 100% | 1.42s | 5.0/5 |
| **Total** | **28** | **100%** | **3.02s** | **4.6/5** |

All original success metrics exceeded: product info > 80% ✓, FAQ > 90% ✓, hallucination = 100% ✓, avg latency < 4s ✓.

## Features Added Beyond the Original Plan

These were not in the improvement plan but were built as the project reached production:

| Feature | Files | Notes |
|---|---|---|
| Email escalation (MailerSend) | `backend/email_client.py` | Replaced Zendesk; went through SMTP → MS Graph → Resend → MailerSend |
| Admin portal | `backend/admin_db.py` | Conversation management, analytics, JSON export |
| Shipping API integration | `backend/shipping_api.py` | Real-time order tracking via external API |
| Gunicorn production server | `Dockerfile`, `requirements.txt` | Replaced Flask dev server for production |
| Context retention | `backend/rag_engine.py` | Conversation history passed to LLM for multi-turn coherence |
| Cacaodoppen knowledge base | `backend/knowledge_base/Cacaodoppen.txt` | New product added |

## Key Files

| File | Role |
|---|---|
| `backend/app.py` | Flask app, security headers, session management, chat routing, admin routes |
| `backend/rag_engine.py` | RAG engine: ChromaDB, ingestion, retrieval, metadata, LLM calls |
| `backend/brand_config.py` | Multi-brand configuration via env vars |
| `backend/email_client.py` | MailerSend email escalation (replaced Zendesk) |
| `backend/zendesk_client.py` | Zendesk integration (retained but superseded by email escalation) |
| `backend/admin_db.py` | Admin portal: SQLite DB for conversations and analytics |
| `backend/shipping_api.py` | Shipping order tracking integration |
| `backend/evaluate_rag.py` | RAG evaluation script (keyword match + LLM-as-judge + latency) |
| `backend/evaluation/test_set.json` | 28-question evaluation test set |
| `backend/evaluation/evaluation_report.md` | Latest evaluation results |
| `backend/knowledge_base/` | 36 .txt files (~120 KB) of product & FAQ content |
| `frontend/static/widget.js` | Embeddable chat widget |
| `.dockerignore` | Prevents .env, venv, logs from entering Docker image |

## Detailed Plans

- [Security Hardening Checklist](security/checklist.md) — 10 items, all complete
- [RAG Quality Improvement Plan](rag/evaluation-plan.md) — 6 sections, all complete
