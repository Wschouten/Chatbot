# Feature Dependency Map

## Current Status

✅ **Features 25-29 & 31-35** — Complete
✅ **Feature 30a-30g** — Complete (admin portal backend storage implemented)
🔄 **Features 36-40** — Polish & cleanup (minor gaps remaining)
📋 **Features 41-46** — Deployment pipeline (ready to execute)

---

## Completed Features

### Core Improvements (25-29)
- ✅ Feature 25: Contextual Query Reformulation
- ✅ Feature 26: Python 3.14 ChromaDB Fix
- ✅ Feature 27: Production Environment & Secrets
- ✅ Feature 28: Local Docker Smoke Test
- ✅ Feature 29: End-to-End Acceptance Testing

### Admin Portal Backend Storage (30a-30g)
- ✅ Feature 30a: Admin DB Schema & Core Module (`backend/admin_db.py`)
- ✅ Feature 30b: Backend Auth Refactor (`@require_admin_key` decorator)
- ✅ Feature 30c: Backend API Routes (12 CRUD endpoints in `app.py`)
- ✅ Feature 30d: Existing Endpoint Enhancement (metadata overlay on conversations)
- ✅ Feature 30e: Frontend Storage Layer (API-backed `storage.js`)
- ✅ Feature 30f: Frontend UI Async (async/await handlers in `app.js`)
- ✅ Feature 30g: Infrastructure Updates (Docker volumes, data directory)

See [30-OVERVIEW.md](30-OVERVIEW.md) for original plan.

### Shipping Integration (31-35)
- ✅ Features 31-35: Complete shipping API integration with order tracking
- See [SHIPPING-IMPLEMENTATION-SUMMARY.md](../SHIPPING-IMPLEMENTATION-SUMMARY.md) for details

---

## Remaining: Code Polish (Features 36-40)

Minor improvements to close gaps in Feature 30 implementation.

| Feature | Name | Status | Effort | Dependencies | Blocks |
|---------|------|--------|--------|--------------|--------|
| **36** | [Single-Conversation API](36-single-conversation-api.md) | 📋 Todo | 15 min | None | 37 |
| **37** | [Efficient Conversation Refresh](37-efficient-conversation-refresh.md) | 📋 Todo | 25 min | 36 | — |
| **38** | [Async Loading States](38-async-loading-states.md) | 📋 Todo | 20 min | None | — |
| **39** | [Storage Dead Code Cleanup](39-storage-dead-code-cleanup.md) | 📋 Todo | 10 min | None | — |
| **40** | [Portal Cosmetic Fixes](40-portal-cosmetic-fixes.md) | 📋 Todo | 5 min | None | — |

### Dependency Diagram (Code)

```
PARALLEL (no dependencies)
├─→ 36 (Single-conversation API) ─→ 37 (Efficient refresh)
├─→ 38 (Async loading states)
├─→ 39 (Dead code cleanup)
└─→ 40 (Cosmetic fixes)
```

**Total effort:** ~1.25 hours
**Parallelization:** 36, 38, 39, 40 can all start immediately. Only 37 depends on 36.

---

## Remaining: Deployment Pipeline (Features 41-46)

Sequential steps to go live on the GroundCoverGroup website.

| Feature | Name | Status | Effort | Dependencies | Blocks |
|---------|------|--------|--------|--------------|--------|
| **41** | [Commit and Push](41-commit-and-push.md) | 📋 Todo | 10 min | 36-40 | 43 |
| **42** | [Production Secrets](42-production-secrets.md) | 📋 Todo | 30 min | None | 43 |
| **43** | [Docker Smoke Test](43-docker-smoke-test.md) | 📋 Todo | 15 min | 41, 42 | 44 |
| **44** | [Railway Deployment](44-railway-deployment.md) | 📋 Todo | 15 min | 43 | 45 |
| **45** | [Shopify Widget Integration](45-shopify-widget-integration.md) | 📋 Todo | 15 min | 44 | 46 |
| **46** | [Post-Launch Verification](46-post-launch-verification.md) | 📋 Todo | 15 min | 45 | — |

### Dependency Diagram (Deployment)

```
36-40 (code) ─→ 41 (commit) ─┐
                               ├─→ 43 (smoke test) ─→ 44 (Railway) ─→ 45 (Shopify) ─→ 46 (verify)
42 (secrets) ─────────────────┘
```

**Total effort:** ~1.75 hours
**Parallelization:** Feature 42 (secrets) can be done in parallel with features 36-41 since it's manual configuration work.

---

## Full Dependency Overview

```
                    ┌─→ 36 ─→ 37 ─┐
PARALLEL CODE  ─────┼─→ 38 ────────┤
                    ├─→ 39 ────────┼─→ 41 (commit) ─┐
                    └─→ 40 ────────┘                  │
                                                      ├─→ 43 ─→ 44 ─→ 45 ─→ 46
PARALLEL CONFIG ──────── 42 (secrets) ────────────────┘
```

**Total remaining effort:** ~3 hours
**Critical path:** 36 → 37 → 41 → 43 → 44 → 45 → 46
