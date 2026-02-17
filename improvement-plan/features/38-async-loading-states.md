# Feature 38: Async Loading States

**Effort:** ~20 min
**Status:** Todo
**Priority:** Low (UX polish)
**Dependencies:** None
**Blocks:** None

---

## Problem

When the admin portal makes API calls (add label, set rating, etc.), buttons remain clickable during the request. This can lead to:
- Double-click creating duplicate labels (backend returns 409, but the error toast is confusing)
- Rapid clicks queuing multiple API calls unnecessarily
- No visual feedback that something is happening

---

## Solution

Disable interactive elements during async API operations and re-enable them afterward.

### Implementation

**File:** `portal/js/app.js`

Apply a disable/enable pattern to each async handler using try/finally:

#### Handlers to Update

| Handler | Line | Element(s) to Disable |
|---------|------|-----------------------|
| `_addLabelToConversation()` | ~949 | Add Label button (`#addLabelBtn`) |
| `_removeLabelFromConversation()` | ~970 | The clicked remove button |
| `_handleRating()` | ~1027 | Both thumbs-up and thumbs-down buttons |
| `_handleAddNote()` | ~1094 | Save Note button |
| `_handleDeleteNote()` | ~1123 | The clicked delete button |
| Status select change | ~1717 | The status `<select>` element |

#### Pattern

```javascript
async _addLabelToConversation(label) {
    if (!this.currentConversationId) return;
    this._closeAddLabelMenu();

    const btn = document.getElementById('addLabelBtn');
    if (btn) btn.disabled = true;

    try {
        await storageManager.addLabel(this.currentConversationId, null, label);
        this.showToast('Label "' + label + '" added.', 'success');
        this.renderConversationDetail(this.currentConversationId);
        this.renderConversationList();
    } catch (err) {
        console.error('Failed to add label:', err);
        this.showToast('Failed to add label: ' + err.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}
```

---

## Verification

1. Open portal, select a conversation
2. Click "Add label" — verify button shows disabled state briefly
3. Click thumbs-up — verify both thumb buttons disable during API call
4. Add a note — verify "Save Note" button disables during API call
5. Try rapid double-clicking — verify no duplicate toasts or errors
