# Feature 30: Backend SQLite Storage - Implementation Overview

**Total Effort:** 4-5 hours
**Status:** Split into 7 sub-features
**Priority:** Critical (blocks reliable portal usage)

---

## Sub-Features Breakdown

| Feature | Name | Effort | Can Start | Dependencies |
|---------|------|--------|-----------|--------------|
| **30a** | Admin DB Schema & Core Module | 45-60 min | ✅ **Now** | None |
| **30b** | Backend Auth Refactor | 15-20 min | ✅ **Now** | None |
| **30c** | Backend API Routes | 60-75 min | ⏳ After 30a, 30b | 30a, 30b |
| **30d** | Existing Endpoint Enhancement | 20-30 min | ⏳ After 30a, 30b | 30a, 30b |
| **30e** | Frontend Storage Layer | 60-75 min | ⏳ After 30c, 30d | 30c, 30d |
| **30f** | Frontend UI Async | 30-40 min | ⏳ After 30e | 30e |
| **30g** | Infrastructure Updates | 15-20 min | ✅ **Now** | None |

---

## Dependency Graph

```
START
  ├─→ 30a (DB Module) ─────────┬─→ 30c (API Routes) ──┐
  ├─→ 30b (Auth Refactor) ─────┤                       │
  │                             └─→ 30d (Endpoint) ────┼─→ 30e (Storage) ─→ 30f (UI) ─→ END
  └─→ 30g (Infrastructure) ─────────────────────────────┘
```

**Legend:**
- Features on the same vertical level can be done in **parallel**
- Features connected by arrows must be done **sequentially**
- **30g** can be done anytime but must be complete before deployment

---

## Implementation Strategies

### Strategy 1: Maximum Parallelization (2 developers)

**Developer A - Backend Track:**
1. **30a** (DB Module) → 60 min
2. **30b** (Auth Refactor) → 20 min
3. **30c** (API Routes) → 75 min
4. **30d** (Endpoint Enhancement) → 30 min

**Developer B - Frontend + Infra Track:**
1. **30g** (Infrastructure) → 20 min
2. *Wait for 30c + 30d to complete*
3. **30e** (Storage Layer) → 75 min
4. **30f** (UI Async) → 40 min

**Total Time:** ~3.5 hours (parallel work)

---

### Strategy 2: Sequential (1 developer)

1. **30a** + **30b** in parallel → 60 min (start both, 30b finishes first)
2. **30c** → 75 min
3. **30d** → 30 min
4. **30e** → 75 min
5. **30f** → 40 min
6. **30g** → 20 min (can be done anytime)

**Total Time:** ~5 hours (sequential work)

---

### Strategy 3: Backend-First (most common)

**Phase 1 - Backend Complete (Test APIs):**
1. **30a** (DB Module) → 60 min
2. **30b** (Auth Refactor) → 20 min
3. **30c** (API Routes) → 75 min
4. **30d** (Endpoint) → 30 min
5. *Integration test with curl/Postman*

**Phase 2 - Frontend Integration:**
6. **30e** (Storage Layer) → 75 min
7. **30f** (UI Async) → 40 min
8. *End-to-end testing in browser*

**Phase 3 - Deployment:**
9. **30g** (Infrastructure) → 20 min
10. *Deploy and smoke test*

**Total Time:** ~5 hours with clear milestones

---

## Quick Start Guide

### Start Immediately (Parallel):
```bash
# Terminal 1: Backend DB Module
cd backend
# Work on 30a-admin-db-schema-module.md

# Terminal 2: Auth Refactor
cd backend
# Work on 30b-backend-auth-refactor.md

# Terminal 3: Infrastructure
# Work on 30g-infrastructure-updates.md (Dockerfile, docker-compose)
```

### After 30a + 30b Complete:
```bash
# Can now start both:
# - 30c (API Routes) - needs admin_db.py and @require_admin_key
# - 30d (Endpoint Enhancement) - needs admin_db.py and @require_admin_key
```

### After 30c + 30d Complete:
```bash
# Must be sequential:
# 30e (Frontend Storage) → 30f (Frontend UI)
```

---

## Testing Milestones

### Milestone 1: DB Module Ready (30a)
```bash
python3
>>> from backend.admin_db import init_db, get_all_metadata
>>> init_db()
>>> # Verify portal.db created
```

### Milestone 2: Backend APIs Ready (30a+30b+30c+30d)
```bash
# Start server
docker-compose up --build

# Test with curl
curl -H "X-Admin-Key: $ADMIN_API_KEY" http://localhost:5000/admin/api/conversations
curl -X POST -H "X-Admin-Key: $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label_name": "test"}' \
  http://localhost:5000/admin/api/conversations/session123/labels
```

### Milestone 3: Frontend Integration Ready (30e+30f)
```bash
# Open browser console
await window.app.storage.addLabel('session123', 'test-label')
# Verify network request sent to API
# Refresh page → verify data persists
```

### Milestone 4: Production Ready (30g)
```bash
# Full smoke test
docker-compose down -v && docker-compose up --build
# Login → Add metadata → Restart → Verify persistence
```

---

## File Summary

### Created (1 file)
- `backend/admin_db.py` - New SQLite module

### Modified (5 files)
- `backend/app.py` - Auth decorator, DB init, 1 modified + 11 new routes
- `portal/js/storage.js` - API-based storage layer
- `portal/js/app.js` - Async/await event handlers
- `Dockerfile` - Data directory creation
- `docker-compose.yml` - Volume mount

### Configuration (1 file)
- `backend/.env.example` - Add PORTAL_DB_PATH

---

## Risk Mitigation

### Risk: Frontend breaks before backend ready
**Mitigation:** Keep feature flag to toggle between localStorage and API mode

### Risk: Data loss during migration
**Mitigation:** No migration needed! Old localStorage data was ephemeral

### Risk: SQLite performance with 1000+ conversations
**Mitigation:** Use indexes on session_id, add pagination in future

### Risk: Database corruption
**Mitigation:** WAL mode + regular backups via volume snapshots

---

## Success Criteria

✅ All metadata persists across browser cache clears
✅ All metadata persists across device switches
✅ All metadata persists across Docker container restarts
✅ No localStorage used for conversation metadata
✅ API response times < 500ms for typical loads
✅ All CRUD operations working (create, read, update, delete)
✅ Full integration test passes

---

## Next Steps After Completion

1. **Add automated tests** - Create `tests/test_admin_api.py`
2. **Add database migrations** - Schema versioning for future changes
3. **Add analytics** - Track portal usage metrics
4. **Add export feature** - Export metadata as CSV/JSON
5. **Add bulk operations** - Label/status multiple conversations at once
6. **Add search** - Full-text search across notes and labels
