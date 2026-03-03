# Feature Dependency Map

## Current Status

✅ **Features 25-29 & 31-35** — Complete
✅ **Feature 30a-30g** — Complete (admin portal backend storage implemented)
✅ **Features 36-43** — Complete (polish, cleanup, commit, secrets, smoke test)
✅ **Feature 44** — Complete (Railway already deployed)
📋 **Features 45-46** — Deployment pipeline (remaining)
✅ **Feature 47** — Complete (dependency versions pinned)
✅ **Feature 48** — Complete (Docker Desktop fixed, build verified, ChromaDB healthy)
✅ **Feature 49** — Complete (local development override)
✅ **Feature 50** — Complete (health endpoint diagnostics)
✅ **Feature 51** — Complete (build & deploy cleanup)

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

## Completed: Code Polish (Features 36-40)

Minor improvements to close gaps in Feature 30 implementation. **All complete.**

| Feature | Name | Status | Effort | Dependencies | Blocks |
|---------|------|--------|--------|--------------|--------|
| **36** | Single-Conversation API | ✅ Done | 15 min | None | 37 |
| **37** | Efficient Conversation Refresh | ✅ Done | 25 min | 36 | — |
| **38** | Async Loading States | ✅ Done | 20 min | None | — |
| **39** | Storage Dead Code Cleanup | ✅ Done | 10 min | None | — |
| **40** | Portal Cosmetic Fixes | ✅ Done | 5 min | None | — |

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
| **41** | Commit and Push | ✅ Done | 10 min | 36-40 | 43 |
| **42** | Production Secrets | ✅ Done | 30 min | None | 43 |
| **43** | Docker Smoke Test | ✅ Done | 15 min | 41, 42 | 44 |
| **44** | [Railway Deployment](44-railway-deployment.md) | ✅ Done | 15 min | 43 | 45 |
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

## Production Readiness (Features 47-51)

ChromaDB/Python/Docker fixes required for going live.

| Feature | Name | Status | Effort | Dependencies | Blocks |
|---------|------|--------|--------|--------------|--------|
| **47** | [Pin Dependency Versions](47-pin-dependency-versions.md) | ✅ Done | 5 min | None | 48 |
| **48** | [Docker Desktop & Verify Build](48-docker-desktop-verify-build.md) | ✅ Done | 15 min | 47 | 49 |
| **49** | [Local Development Override](49-local-development-override.md) | ✅ Done | 5 min | 48 | — |
| **50** | [Health Endpoint Diagnostics](50-health-endpoint-diagnostics.md) | ✅ Done | 5 min | None | — |
| **51** | [Build & Deploy Cleanup](51-build-deploy-cleanup.md) | ✅ Done | 10 min | None | — |

### Dependency Diagram (Production Readiness)

```
47 (pin deps) ──→ 48 (Docker build) ──→ 49 (dev override)

PARALLEL (no dependencies):
├─→ 50 (health diagnostics)
└─→ 51 (cleanup)
```

**Total effort:** ~40 minutes
**Parallelization:** 50 and 51 can run in parallel with 47→48→49.

---

## Full Dependency Overview

```
                    ┌─→ 36 ─→ 37 ─┐
PARALLEL CODE  ─────┼─→ 38 ────────┤
                    ├─→ 39 ────────┼─→ 41 (commit) ─┐
                    └─→ 40 ────────┘                  │
                                                      ├─→ 43 ─→ 44 ─→ 45 ─→ 46
PARALLEL CONFIG ──────── 42 (secrets) ────────────────┘

PRODUCTION READINESS (independent track):
47 (pin deps) ──→ 48 (Docker) ──→ 49 (dev override)
                  50 (health) ───┘  (parallel)
                  51 (cleanup) ──┘  (parallel)
```

**Total remaining effort:** ~3.5 hours (deployment) + ~7-8 hours (post-launch)
**Critical path (deployment):** 36 → 37 → 41 → 43 → 44 → 45 → 46
**Critical path (production readiness):** 47 → 48 → 49

---

## Post-Launch Improvements (Features 52-59)

Improvements to implement after the chatbot is live. Features 52, 55, 57, 58, 59 can start immediately (no dependency on go-live). Features 53 and 54 require the production deployment to be running.

| Feature | Name | Status | Effort | Dependencies | Blocks |
|---------|------|--------|--------|--------------|--------|
| **52** | [Delete Conversations](52-delete-conversations.md) | 📋 Todo | ~1h | None | 56 |
| **53** | [Uptime Monitoring Setup](53-uptime-monitoring.md) | 📋 Todo | ~15 min | Feature 46 (go-live) | — |
| **54** | [Shipping API Live Integration](54-shipping-api-live.md) | 🚫 Blocked | ~30 min | Feature 46 + StatusWeb IP whitelist | — |
| **55** | [Automated Backend Tests](55-automated-tests.md) | 📋 Todo | ~2-3h | None | — |
| **56** | [Bulk Conversation Operations](56-bulk-conversation-operations.md) | 📋 Todo | ~2h | Feature 52 | — |
| **57** | [Knowledge Base Update Workflow](57-knowledge-base-workflow.md) | 📋 Todo | ~1h | None | — |
| **58** | [Analytics Dashboard Enhancements](58-analytics-enhancements.md) | 📋 Todo | ~2-3h | None | — |
| **59** | [Database Backup & Restore](59-database-backup.md) | 📋 Todo | ~30 min | None | — |

### Dependency Diagram (Post-Launch)

```
PARALLEL (can start any time):
├─→ 52 (Delete Conversations) ──→ 56 (Bulk Operations)
├─→ 55 (Automated Tests)
├─→ 57 (Knowledge Base Workflow)
├─→ 58 (Analytics Enhancements)
└─→ 59 (DB Backup & Restore)

AFTER go-live (Feature 46):
├─→ 53 (Uptime Monitoring)
└─→ 54 (Shipping API Live) ← also needs StatusWeb IP whitelist
```

**Total effort:** ~7-8 hours
**Recommended first:** 52 (high-value, low-effort admin portal improvement) + 53 (5 min setup, production safety) + 59 (data protection)
**Can be parallel:** 52, 55, 57, 58, 59 have no dependencies and can all be worked on simultaneously
