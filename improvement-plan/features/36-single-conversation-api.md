# Feature 36: Single-Conversation API Endpoint

**Effort:** ~15 min
**Status:** Todo
**Priority:** Medium (enables Feature 37 performance optimization)
**Dependencies:** None
**Blocks:** Feature 37

---

## Problem

When the admin portal adds a label, note, or rating, `storage.js` calls `syncFromApi()` which re-fetches **all** conversations from `GET /admin/api/conversations`. This is wasteful — only the affected conversation needs refreshing.

There is no endpoint to fetch a single conversation with its metadata.

---

## Solution

Add `GET /admin/api/conversations/<session_id>` to `backend/app.py`.

### Endpoint Specification

```
GET /admin/api/conversations/<session_id>
Headers: X-Admin-Key: <ADMIN_API_KEY>
Rate Limit: 30/min

Response 200:
{
  "id": "sess_abc123",
  "started": "2026-02-15T10:00:00Z",
  "lastMessage": "2026-02-15T10:05:30Z",
  "messageCount": 4,
  "messages": [
    {"timestamp": "...", "user": "...", "bot": "..."}
  ],
  "metadata": {
    "status": "open",
    "rating": null,
    "language": null,
    "labels": ["shipping", "product-info"],
    "notes": [{"id": 1, "text": "...", "author": "admin", "created_at": "..."}]
  }
}

Response 400: {"error": "Invalid session ID"}
Response 404: {"error": "Conversation not found"}
```

### Implementation

**File:** `backend/app.py` — insert after line 840 (after `admin_conversations()`)

The route should:
1. Validate and sanitize the session_id
2. Load the chat log file `logs/chat_<session_id>.json`
3. Return 404 if file not found
4. Overlay metadata from `admin_db.get_metadata(session_id)`
5. Return the conversation object with messages + metadata

Use the same patterns as `admin_conversations()` (lines 765-840) but for a single conversation.

### Existing Code to Reuse

- `sanitize_session_id()` — input validation (already in app.py)
- `admin_db.get_metadata(session_id)` — single-conversation metadata lookup (admin_db.py line 270)
- `@require_admin_key` decorator — auth (app.py line 162)
- `@limiter.limit()` — rate limiting

---

## Verification

```bash
# Start container
docker-compose up --build

# Create a conversation by chatting

# List all conversations to get a session_id
curl -s -H "X-Admin-Key: $KEY" http://localhost:5000/admin/api/conversations | python -m json.tool

# Fetch single conversation
curl -s -H "X-Admin-Key: $KEY" http://localhost:5000/admin/api/conversations/<session_id> | python -m json.tool

# Test 404
curl -s -w "\n%{http_code}" -H "X-Admin-Key: $KEY" http://localhost:5000/admin/api/conversations/nonexistent
# Expect: 404

# Test invalid ID
curl -s -w "\n%{http_code}" -H "X-Admin-Key: $KEY" http://localhost:5000/admin/api/conversations/../etc/passwd
# Expect: 400
```
