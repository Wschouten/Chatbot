# Feature Dependency Map

## All Features

| # | Feature | Track | Effort | Status | Dependencies |
|---|---------|-------|--------|--------|-------------|
| 25 | Contextual Query Reformulation | Enhancement | 15 min | Done | None |
| 26 | Python 3.14 ChromaDB Fix | Bug Fix | 5 min | Done | None |
| 27 | Production Environment & Secrets | Operations | 15-30 min | Todo | None |
| 28 | Local Docker Smoke Test | QA | 15 min | Todo | 25, 26 |
| 29 | End-to-End Acceptance Testing | QA | 30 min | Todo | 28 |
| 30 | ~~Real Shipping API Integration~~ | — | — | Superseded | Split into 31-35 |
| 31 | Shipping API Client | Feature | 1-2 hr | Done | None |
| 32 | Shipping Environment & Health Check | Operations | 15 min | Done | 31 |
| 33 | Order Confirmation Flow | Feature | 1-2 hr | Done | 31 |
| 34 | Confirmation State Timeout | Enhancement | 30 min | Done | 33 |
| 35 | Shipping Integration Testing | QA | 30-45 min | Done | 31, 32, 33, 34 |

Features 20 (Railway Hosting), 21 (Shopify Widget), and 22 (Post-Launch Monitoring) have been removed from scope.

## Dependency Graph

```
DONE (code changes complete)
├── Feature 25: Contextual Query Reformulation ── Done ✓
├── Feature 26: Python 3.14 ChromaDB Fix ──────── Done ✓
│
PRE-LAUNCH CHAIN
├── Feature 27: Production Env & Secrets (operations, in parallel)
│
├── Feature 28: Local Docker Smoke Test ◄── needs 25, 26 done
│       │
│       ▼
├── Feature 29: End-to-End Acceptance Testing
│
SHIPPING API INTEGRATION (Feature 30 → split into 31-35)
├── Feature 31: Shipping API Client ──────────────────── Done ✓
│       ├── Feature 32: Environment & Health Check ──── Done ✓
│       ├── Feature 33: Order Confirmation Flow ─────── Done ✓
│       │       └── Feature 34: State Timeout ───────── Done ✓
│       └── Feature 35: Shipping Integration Testing ── Done ✓
```

## What's Next

### Ready NOW

| Feature | Who | Notes |
|---------|-----|-------|
| 27 — Env & Secrets Prep | Store owner / ops | Generate keys, gather SMTP credentials, confirm domains |
| 28 — Docker Smoke Test | Developer | All code changes (25, 26) are done; can test locally |

### Must wait

| Feature | Blocked by | Why |
|---------|-----------|-----|
| 29 — Acceptance Testing | 28 | Need local validation to pass first |

## Estimated Remaining Timeline

| Phase | Features | Est. Time |
|-------|----------|-----------|
| Operations prep | 27 | ~15-30 min |
| Local validation | 28 | ~15 min |
| Acceptance testing | 29 | ~30 min |
| **Total remaining** | | **~1-1.5 hours** |

## Completed Features

✅ **Shipping API Integration (Features 31-35)** - 3 hours
- All shipping features implemented and tested
- See [SHIPPING-IMPLEMENTATION-SUMMARY.md](../SHIPPING-IMPLEMENTATION-SUMMARY.md) for details
