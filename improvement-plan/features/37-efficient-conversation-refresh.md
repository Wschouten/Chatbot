# Feature 37: Efficient Conversation Refresh

**Effort:** ~25 min
**Status:** Todo
**Priority:** Medium (performance optimization)
**Dependencies:** Feature 36 (single-conversation API endpoint)
**Blocks:** None

---

## Problem

Every mutation method in `portal/js/storage.js` (`addLabel`, `removeLabel`, `setRating`, `addNote`, `deleteNote`, `setStatus`) follows this pattern:

```javascript
async addLabel(conversationId, messageId, labelName) {
    // 1. Call mutation API
    const result = await this._apiCall('POST', `/admin/api/conversations/${conversationId}/labels`, { label_name: labelName });
    // 2. Re-fetch ALL conversations
    await this.syncFromApi();
}
```

`syncFromApi()` fetches every conversation from the backend. With hundreds of conversations, this adds unnecessary latency after every single label or note change.

---

## Solution

Add `_refreshConversation(sessionId)` method that fetches only the affected conversation using the Feature 36 endpoint, and update it in localStorage.

### Implementation

**File:** `portal/js/storage.js`

**1. Add `_refreshConversation()` method:**

```javascript
/**
 * Refresh a single conversation from the backend API.
 * More efficient than syncFromApi() which re-fetches everything.
 *
 * @param {string} sessionId - The conversation session ID
 * @returns {Promise<void>}
 */
async _refreshConversation(sessionId) {
    const result = await this._apiCall('GET', `/admin/api/conversations/${sessionId}`);
    if (!result.ok) {
        console.warn('Failed to refresh conversation:', result.error);
        return;
    }

    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const transformed = this._transformApiConversation(result.data);
    const idx = convs.findIndex(c => c.id === sessionId);
    if (idx !== -1) {
        convs[idx] = transformed;
    }
    this._write(KEYS.CONVERSATIONS, convs);
}
```

**2. Update mutation methods** — replace `await this.syncFromApi()` with `await this._refreshConversation(conversationId)` in:

| Method | Approximate Line |
|--------|-----------------|
| `addLabel()` | ~984 |
| `removeLabel()` | ~1012 |
| `setRating()` | ~1076 |
| `addNote()` | ~1109 |
| `deleteNote()` | ~1130 |
| `setStatus()` | ~1149 |

### Existing Code to Reuse

- `_apiCall(method, path, body)` — authenticated fetch helper (storage.js line 655)
- `_transformApiConversation(apiConv)` — transforms API response to portal format (storage.js line 756)
- `_read(key)` / `_write(key, data)` — localStorage helpers (already in class)
- `KEYS.CONVERSATIONS` — localStorage key constant (already defined)

---

## Verification

1. Open portal, select a conversation
2. Open DevTools Network tab
3. Add a label — verify network request goes to `POST .../labels` then `GET .../conversations/<id>` (NOT `GET .../conversations`)
4. Verify label appears immediately in the UI
5. Refresh page — verify label persists
6. Repeat for: remove label, set rating, add note, delete note, change status
