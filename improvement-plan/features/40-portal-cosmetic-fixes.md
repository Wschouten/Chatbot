# Feature 40: Portal Cosmetic Fixes

**Effort:** ~5 min
**Status:** Todo
**Priority:** Low (cosmetic)
**Dependencies:** None
**Blocks:** None

---

## Problem

The admin portal sidebar footer still references "localStorage" as the data storage method. Since the portal now uses backend API-backed SQLite storage, this text is inaccurate.

---

## Solution

**File:** `frontend/templates/portal.html`

Update the sidebar footer text (around line 99) from the current localStorage reference to indicate API-backed storage.

Change to something like:
```html
<span id="sidebarVersion">Portal v1.0</span> &middot; API-backed
```

---

## Verification

1. Open portal in browser
2. Check sidebar footer text shows "API-backed" instead of "localStorage"
