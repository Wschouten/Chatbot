# Feature 39: Storage Dead Code Cleanup

**Effort:** ~10 min
**Status:** Todo
**Priority:** Low (code hygiene)
**Dependencies:** None
**Blocks:** None

---

## Problem

`portal/js/storage.js` contains ~440 lines of dead code left over from the localStorage-only era. This code is never called and increases file size by ~30%.

---

## What to Remove

### 1. `generateSeedData()` function (~lines 83-525)

A standalone function that generates fake conversation data for development. It is never called anywhere in the codebase — the portal now loads real data from the backend API via `syncFromApi()`.

**Lines:** ~83-525 (~440 lines)

### 2. `_updateConversation()` method (~lines 967-973)

A private method that directly updates a conversation in localStorage. It is never called by any public method — all mutation methods use the API + re-sync pattern instead.

**Lines:** ~967-973 (~6 lines)

### 3. `getDefaultLabels()` function (~lines 532-559)

Returns a hardcoded array of 24 label definitions. Labels are now served by the backend API via `GET /admin/api/labels` and synced by `syncLabelDefinitions()`. The frontend fallback is no longer needed.

**Lines:** ~532-559 (~27 lines)

**Note:** Check if `_seedAll()` references `getDefaultLabels()`. If so, replace with an empty array or remove the `_seedAll()` label seeding logic too.

---

## What NOT to Remove

- `_apiCall()` — actively used for all API communication
- `syncFromApi()` — actively used for initial data load
- `syncLabelDefinitions()` — actively used for label sync
- All public mutation methods (addLabel, removeLabel, etc.) — actively used
- `_transformApiConversation()` — actively used for data transformation

---

## Verification

1. Remove the dead code
2. `docker-compose up --build`
3. Open portal, login
4. Verify conversations load correctly
5. Verify labels, notes, ratings all work
6. Check browser console for no errors
7. Verify file size reduced from ~1517 lines to ~1044 lines
