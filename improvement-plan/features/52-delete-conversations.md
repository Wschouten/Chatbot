# Feature 52: Delete Conversations

**Effort:** ~1 hour
**Status:** Todo
**Priority:** Medium (admin portal quality of life)
**Dependencies:** None
**Blocks:** Feature 56 (Bulk Conversation Operations)

---

## Problem

The admin portal has no way to delete individual logged conversations. Admins can delete sub-resources (notes, labels) but the conversation itself — including its log file, session file, and all SQLite metadata — persists indefinitely. This makes it impossible to clean up test conversations, spam, or data that should be removed for GDPR/privacy reasons.

---

## Solution

Add a "Delete" button to the conversation detail panel that permanently removes:
1. The chat log JSON file: `backend/data/logs/chat_<session_id>.json`
2. The session state JSON file: `backend/data/sessions/<session_id>.json`
3. All SQLite rows in `portal.db` for that session

---

## Files Changed

| File | Change |
|------|--------|
| `backend/admin_db.py` | New `delete_conversation(session_id)` function |
| `backend/app.py` | New `DELETE /admin/api/conversations/<session_id>` route |
| `portal/js/storage.js` | New `deleteConversation(conversationId)` method |
| `portal/js/app.js` | New `_handleDeleteConversation()` handler + event binding |
| `frontend/templates/portal.html` | Delete button in `div.detail-header-actions` |

> **Note:** `btn-danger` CSS class already exists in `frontend/static/portal.css` — no CSS changes needed.

---

## Backend: `backend/admin_db.py`

Insert after `delete_note()` (line 408):

```python
def delete_conversation(session_id: str) -> bool:
    """Delete all database rows for a conversation across all tables.

    Deletes from conversation_labels, conversation_notes, message_metadata,
    and conversation_metadata in FK dependency order. Returns True if a
    conversation_metadata row was deleted.
    """
    db = get_db()
    db.execute("DELETE FROM conversation_labels WHERE session_id = ?", (session_id,))
    db.execute("DELETE FROM conversation_notes WHERE session_id = ?", (session_id,))
    db.execute("DELETE FROM message_metadata WHERE session_id = ?", (session_id,))
    cur = db.execute(
        "DELETE FROM conversation_metadata WHERE session_id = ?", (session_id,)
    )
    db.commit()
    return cur.rowcount > 0
```

---

## Backend: `backend/app.py`

Insert before `if __name__ == '__main__':` (line 1435):

```python
@app.route("/admin/api/conversations/<session_id>", methods=["DELETE"])
@limiter.limit("10 per minute")
@require_admin_key
def delete_conversation_route(session_id):
    """Permanently delete a conversation: log file, session file, and all DB rows."""
    safe_id = sanitize_session_id(session_id)
    if not safe_id:
        return jsonify({"error": "Invalid session ID"}), 400

    log_path = os.path.join("data", "logs", f"chat_{safe_id}.json")
    session_path = os.path.join(SESSION_DIR, f"{safe_id}.json")

    if not os.path.exists(log_path):
        return jsonify({"error": "Conversation not found"}), 404

    try:
        os.remove(log_path)
        if os.path.exists(session_path):
            os.remove(session_path)
        admin_db.delete_conversation(safe_id)
        logger.info("Conversation deleted: %s", safe_id)
        return jsonify({"success": True}), 200
    except OSError as e:
        logger.error("Failed to delete conversation files for %s: %s", safe_id, e)
        return jsonify({"error": "Failed to delete conversation files"}), 500
    except Exception as e:
        logger.error("Failed to delete conversation %s: %s", safe_id, e)
        return jsonify({"error": "Internal server error"}), 500
```

**Rate limit:** `"10 per minute"` (stricter than the standard 30 — this is a destructive operation).

---

## Frontend: `portal/js/storage.js`

Insert after `deleteNote()` (line 688):

```javascript
/**
 * Permanently delete a conversation via API, then remove it from localStorage.
 * @param {string} conversationId
 * @returns {Promise<boolean>}
 */
async deleteConversation(conversationId) {
  const result = await this._apiCall(
    'DELETE',
    `/admin/api/conversations/${conversationId}`
  );
  if (!result.ok) throw new Error(result.error);
  // Remove from local cache immediately (resource is gone, no refresh needed)
  const convs = this._read(KEYS.CONVERSATIONS) || [];
  this._write(KEYS.CONVERSATIONS, convs.filter(c => c.id !== conversationId));
  return true;
}
```

---

## Frontend: `portal/js/app.js`

### New method — insert after `_handleDeleteNote()` (line 1158):

```javascript
/**
 * Handle the "Delete Conversation" button. Prompts for confirmation then
 * permanently deletes the conversation and all associated data.
 * @param {string} convId
 */
async _handleDeleteConversation(convId) {
  const confirmed = window.confirm(
    'Permanently delete this conversation?\n\n' +
    'This will remove all messages, notes, labels, and ratings ' +
    'for this conversation. This action cannot be undone.\n\n' +
    'Session: ' + convId
  );
  if (!confirmed) return;

  const btn = document.getElementById('detailDeleteBtn');
  if (btn) btn.disabled = true;

  try {
    await storageManager.deleteConversation(convId);
    this.currentConversationId = null;
    this.showToast('Conversation deleted.', 'info');
    this.renderConversationDetail(null);   // shows empty state
    this.renderConversationList();          // removes from list
  } catch (err) {
    console.error('Failed to delete conversation:', err);
    this.showToast('Failed to delete conversation: ' + err.message, 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}
```

### Event binding — insert after `detailExportBtn` binding (line 1737):

```javascript
const detailDeleteBtn = document.getElementById('detailDeleteBtn');
if (detailDeleteBtn) {
  detailDeleteBtn.addEventListener('click', async () => {
    if (self.currentConversationId) {
      await self._handleDeleteConversation(self.currentConversationId);
    }
  });
}
```

---

## Frontend: `frontend/templates/portal.html`

Insert inside `div.detail-header-actions` after the Export button (line 254):

```html
<button class="btn btn-sm btn-danger" id="detailDeleteBtn"
    aria-label="Delete this conversation"
    title="Permanently delete this conversation">
    &#128465; Delete
</button>
```

---

## Data Flow

```
User clicks Delete button
  → window.confirm() dialog (with session ID shown)
    → Cancel: return (no side effects)
    → Confirm:
       → btn.disabled = true
       → storageManager.deleteConversation(convId)
          → DELETE /admin/api/conversations/<id>
             → sanitize_session_id()
             → check log file exists (404 if not)
             → os.remove(log file)
             → os.remove(session file) if exists
             → admin_db.delete_conversation()
                → DELETE conversation_labels, conversation_notes,
                   message_metadata, conversation_metadata
             → return {"success": true}
          → filter conversation out of localStorage
       → currentConversationId = null
       → showToast('Conversation deleted.', 'info')
       → renderConversationDetail(null)  → shows empty state
       → renderConversationList()        → list refreshed without deleted item
       → btn.disabled = false
```

---

## Edge Cases

| Scenario | Handling |
|----------|----------|
| Path traversal in session ID | `sanitize_session_id()` strips it; empty result → 400 |
| Log file already missing | Route returns 404; frontend shows error toast |
| Session file never created | `os.path.exists()` guard before `os.remove()` |
| No DB metadata row (never annotated) | `delete_conversation()` deletes zero rows; route still returns 200 |
| User double-clicks before first completes | `btn.disabled = true` prevents second request |

---

## Verification

1. Start backend: `cd backend && python app.py`
2. Open admin portal → log in → select any conversation
3. Verify: red "Delete" button appears next to Export in the header
4. Click Delete → `confirm()` dialog appears with session ID
5. **Confirm** → conversation disappears from list; detail panel shows empty state; toast: "Conversation deleted"
6. **Cancel** → no change
7. Verify log file gone: `ls backend/data/logs/chat_<id>.json` → not found
8. Verify DB clean: `sqlite3 backend/data/portal.db "SELECT * FROM conversation_metadata WHERE session_id='<id>'"` → empty
