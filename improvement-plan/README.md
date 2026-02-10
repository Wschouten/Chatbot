# GroundCover Chatbot Improvement Plan

## Overview

The GroundCover Chatbot is a RAG-based customer support bot for GroundCoverGroup (Dutch garden/landscaping products). It has a solid foundation: modular Flask + ChromaDB + OpenAI architecture, good prompt engineering with safety guardrails, GDPR-compliant data retention, Docker setup with non-root user, rate limiting, and an embeddable widget with privacy consent.

To make this chatbot production-ready, we're focusing on two areas:
1. **Security Hardening** — credential management, CSP, logging safety
2. **RAG Quality** — evaluation framework, retrieval improvements, knowledge base content

## Current State Assessment

| Area | Score | Notes |
|---|---|---|
| Architecture | 8/10 | Well-designed, modular, clean separation of concerns |
| Prompt Engineering | 8/10 | Comprehensive safety guardrails, closed-world assumption |
| Security | 6/10 | Good fundamentals (CORS, rate limiting), but exposed keys and CSP issues |
| RAG Retrieval | 6/10 | Basic top-5 similarity, no filtering/reranking/evaluation |
| Knowledge Base | 7/10 | Well-structured content, but no comparisons or cross-references |
| Testing | 4/10 | Only validation tests (~30% coverage), no RAG evaluation |
| Deployment | 7/10 | Docker with non-root user, but no `.dockerignore` or health dependency checks |

## Implementation Steps

| Step | Task | Status | Details |
|---|---|---|---|
| 0 | Create improvement plan folder | :white_check_mark: Done | This folder |
| 1 | Rotate all exposed API keys | :black_square_button: Todo | Manual — OpenAI, Zendesk, ADMIN_API_KEY |
| 2 | Security quick wins | :black_square_button: Todo | [Security checklist](security/checklist.md) items 2-5 |
| 3 | Security remaining items | :black_square_button: Todo | [Security checklist](security/checklist.md) items 6-10 |
| 4 | Make LLM model configurable | :black_square_button: Todo | [RAG plan](rag/evaluation-plan.md) section 1 |
| 5 | Build RAG evaluation framework | :black_square_button: Todo | [RAG plan](rag/evaluation-plan.md) section 2 |
| 6 | Run baseline evaluation | :black_square_button: Todo | Measure current quality |
| 7 | Metadata + retrieval improvements | :black_square_button: Todo | [RAG plan](rag/evaluation-plan.md) sections 3-4 |
| 8 | Run evaluation | :black_square_button: Todo | Measure improvement from steps 4-7 |
| 9 | Knowledge base content improvements | :black_square_button: Todo | [RAG plan](rag/evaluation-plan.md) section 5 |
| 10 | English language prompt fix | :black_square_button: Todo | [RAG plan](rag/evaluation-plan.md) section 6 |
| 11 | Run final evaluation | :black_square_button: Todo | Compare to baseline |

## Key Files

| File | Role |
|---|---|
| `backend/app.py` | Flask app, security headers, session management, chat routing |
| `backend/rag_engine.py` | RAG engine: ChromaDB, ingestion, retrieval, LLM calls |
| `backend/brand_config.py` | Multi-brand configuration via env vars |
| `backend/zendesk_client.py` | Zendesk ticket creation integration |
| `backend/knowledge_base/` | 32 .txt files (~98 KB) of product & FAQ content |
| `frontend/static/widget.js` | Embeddable chat widget |

## Detailed Plans

- [Security Hardening Checklist](security/checklist.md) — 10 items covering credentials, CSP, logging, Docker
- [RAG Quality Improvement Plan](rag/evaluation-plan.md) — 6 sections covering evaluation, retrieval, content
