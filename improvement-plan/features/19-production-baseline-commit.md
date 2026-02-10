# Feature 19: Production Baseline Commit

**Track:** Process
**Effort:** 10 min
**Status:** Todo
**Dependencies:** Feature 16 (Email Escalation), Feature 17 (Gunicorn), Feature 18 (Env Config Docs)

## Context

The working tree has significant unstaged changes and untracked files. Before deploying to production hosting, all code changes must be committed as a clean "production-ready" baseline. This commit is the gate between code work (Features 16-18) and infrastructure work (Features 20-22).

## Pending Changes to Commit

### Modified files (unstaged)
- `Dockerfile` — gunicorn CMD + healthcheck (Feature 17)
- `backend/app.py` — email escalation routing (Feature 16)
- `backend/brand_config.py` — branding updates
- `backend/rag_engine.py` — RAG improvements
- `backend/zendesk_client.py` — `use_mock` property fix (Feature 16)
- `frontend/static/widget.js` — widget updates

### New files (untracked)
- `backend/email_client.py` — new email escalation module (Feature 16)
- `backend/evaluate_rag.py` + `backend/evaluation/` — RAG evaluation suite
- `backend/knowledge_base/*.txt` — 32 product/FAQ text files
- `improvement-plan/features/*.md` — feature documentation

## Implementation

### 1. Review all changes

Run `git diff` and `git status` to verify everything is as expected. No secrets (API keys, passwords) should be in any committed file.

### 2. Stage and commit

```bash
git add -A
git commit -m "feat: production-ready baseline with email escalation, gunicorn, and knowledge base"
```

### 3. Push to GitHub

```bash
git push origin master
```

This is required for Railway to auto-deploy from the repo.

## Verification

1. `git status` shows clean working tree
2. `git log --oneline -1` shows the new commit
3. Repo is pushed to GitHub and visible at the remote

## Notes

- Ensure `.env` (with real secrets) is in `.gitignore` and NOT committed
- The `.env.example` file (no real values) IS committed
- This is a checkpoint — all subsequent features depend on this commit existing
