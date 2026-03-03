# Feature 56: Bulk Conversation Operations

**Effort:** ~2 hours
**Status:** Todo
**Priority:** Low (efficiency improvement for high-volume portals)
**Dependencies:** Feature 52 (Delete Conversations — single delete must exist first)
**Blocks:** None

---

## Problem

Admins must process conversations one at a time. With high message volume, bulk workflows like "mark all resolved" or "delete test conversations" require opening each conversation individually. The export feature already uses checkboxes — that infrastructure should be extended to support bulk actions.

---

## Solution

Add checkboxes to the conversation list rows. When one or more are selected, a "Bulk actions" toolbar appears above the list offering:
- **Change status** (open / resolved / escalated / unknown_flagged)
- **Add label**
- **Delete selected**

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/templates/portal.html` | Bulk action toolbar above conversation list |
| `portal/js/app.js` | Checkbox logic, toolbar show/hide, bulk action handlers |
| `portal/js/storage.js` | `bulkDeleteConversations()`, `bulkUpdateStatus()` methods |
| `backend/app.py` | `DELETE /admin/api/conversations/bulk` endpoint |

---

## UI Design

```
┌─────────────────────────────────────────────────────────────┐
│  [✓] 3 selected   [Change status ▼]  [Add label ▼]  [Delete]│ ← bulk toolbar (shown when ≥1 checked)
├─────────────────────────────────────────────────────────────┤
│ [✓] Session abc123   Open    2026-02-10   5 msgs            │
│ [✓] Session def456   Open    2026-02-09   3 msgs            │
│ [ ] Session ghi789   Resolved 2026-02-08  8 msgs            │
│ [✓] Session jkl012   Open    2026-02-07   2 msgs            │
└─────────────────────────────────────────────────────────────┘
```

- "Select all" checkbox in the header row selects/deselects all visible conversations
- Bulk toolbar appears/disappears based on selection count
- Delete confirmation shows count: "Permanently delete 3 conversations? This cannot be undone."

---

## Backend: New Bulk Delete Endpoint

`DELETE /admin/api/conversations/bulk`

Request body:
```json
{ "session_ids": ["abc123", "def456", "jkl012"] }
```

Response:
```json
{ "deleted": 3, "failed": 0 }
```

The endpoint iterates over each ID, calls the same logic as the single-delete route (Feature 52), and returns a summary. Partial failures are reported but do not stop the batch.

---

## Backend: Bulk Status Update

`PUT /admin/api/conversations/bulk/metadata`

Request body:
```json
{ "session_ids": ["abc123", "def456"], "status": "resolved" }
```

Uses existing `admin_db.upsert_metadata()` in a loop.

---

## Implementation Notes

- Bulk delete should reuse `admin_db.delete_conversation()` from Feature 52 in a loop (no new DB function needed)
- Rate limit: `"5 per minute"` on bulk endpoints (destructive, higher impact)
- Max batch size: 50 conversations per request (prevent accidental mass deletion)
- Checkboxes are independent of the export checkboxes (export lives in a separate view)

---

## Dependency on Feature 52

The bulk delete endpoint calls the same file deletion + DB cleanup logic as single delete. Feature 52 must be implemented and working before building the bulk endpoint on top of it.

---

## Verification

1. Select 2+ conversations using checkboxes
2. Bulk toolbar appears with action options
3. "Change status → Resolved" updates all selected conversations
4. "Delete" shows confirmation with count → confirm → all selected conversations removed from list
5. "Select all" checkbox toggles all visible rows
6. Deselecting all hides the bulk toolbar
