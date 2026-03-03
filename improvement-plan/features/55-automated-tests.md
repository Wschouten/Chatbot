# Feature 55: Automated Backend Tests

**Effort:** ~2-3 hours
**Status:** Todo
**Priority:** Medium (prevents regressions when adding new features)
**Dependencies:** None (can start independently)
**Blocks:** None

---

## Problem

There are no automated tests. Regressions in the admin API, chat flow, or database layer are only caught during manual testing. As the codebase grows (shipping integration, admin portal features), manual verification becomes unreliable and slow.

---

## Solution

Add a `tests/` directory with pytest-based tests covering:
1. Admin API endpoints (auth, CRUD operations)
2. Database layer (`admin_db.py`)
3. Core chat flow (session creation, basic message handling)

---

## Files to Create

```
tests/
├── conftest.py              # Shared fixtures (test client, temp DB, session setup)
├── test_admin_api.py        # All /admin/api/* endpoints
├── test_admin_db.py         # admin_db.py functions in isolation
└── test_chat_api.py         # /api/chat and /api/session endpoints
```

---

## Test Coverage Plan

### `tests/conftest.py`

```python
import pytest
import tempfile
import os
from backend.app import app
import backend.admin_db as admin_db

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Test client with isolated temp directories."""
    monkeypatch.setenv("ADMIN_API_KEY", "test-key-abc123")
    monkeypatch.setenv("PORTAL_DB_PATH", str(tmp_path / "test_portal.db"))
    # Point log and session dirs to tmp
    monkeypatch.setattr("backend.app.SESSION_DIR", str(tmp_path / "sessions"))
    os.makedirs(tmp_path / "sessions", exist_ok=True)
    os.makedirs(tmp_path / "logs", exist_ok=True)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c

@pytest.fixture
def auth_headers():
    return {"X-Admin-Key": "test-key-abc123"}
```

### `tests/test_admin_api.py` — key test cases

| Test | Description |
|------|-------------|
| `test_list_conversations_unauthenticated` | Returns 401 without API key |
| `test_list_conversations_authenticated` | Returns 200 + empty list on fresh DB |
| `test_add_label_to_conversation` | POST label → 200, label persists |
| `test_remove_label_from_conversation` | DELETE label → 200, label gone |
| `test_add_note` | POST note → 200, note persists |
| `test_delete_note` | DELETE note → 200, note gone |
| `test_update_metadata_status` | PUT metadata status → 200, status updated |
| `test_delete_conversation` | DELETE conversation → 200, log file + DB rows gone |
| `test_delete_nonexistent_conversation` | DELETE missing session → 404 |
| `test_create_label_definition` | POST label def → 200, definition retrievable |
| `test_delete_label_definition` | DELETE label def → 200, gone |

### `tests/test_admin_db.py` — key test cases

| Test | Description |
|------|-------------|
| `test_upsert_and_get_metadata` | upsert → get returns same values |
| `test_add_remove_label` | add label → present; remove → gone |
| `test_add_delete_note` | add note → retrievable; delete → gone |
| `test_delete_conversation_cascades` | delete conversation removes all 4 tables |
| `test_get_all_metadata_empty` | empty DB → returns empty list |

### `tests/test_chat_api.py` — key test cases

| Test | Description |
|------|-------------|
| `test_session_endpoint` | POST /api/session → returns session_id |
| `test_health_endpoint` | GET /health → 200 with status key |
| `test_chat_requires_session` | POST /api/chat without session → 400 |

---

## Setup Requirements

Add to `requirements.txt` (or `requirements-dev.txt`):
```
pytest>=8.0
pytest-flask>=1.3
```

Add `pytest.ini` or `pyproject.toml` section:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

---

## Running Tests

```bash
# From project root
pip install pytest pytest-flask
pytest tests/ -v

# Run just API tests
pytest tests/test_admin_api.py -v

# Run with coverage report
pip install pytest-cov
pytest tests/ --cov=backend --cov-report=term-missing
```

---

## CI Integration (Optional, Future)

Once tests pass locally, add a GitHub Actions workflow (`.github/workflows/test.yml`):
```yaml
- name: Run tests
  run: pytest tests/ -v
```

This would automatically run tests on every push and pull request.

---

## Scope Notes

- Tests use an in-memory/temp SQLite DB — no production data at risk
- Tests mock the OpenAI API call to avoid real LLM calls during CI
- Shipping API calls are mocked (they require external whitelist)
- Email escalation is mocked (requires SMTP credentials)

---

## Verification

```bash
pytest tests/ -v
# Expected: all tests pass
# Coverage target: >80% of backend/admin_db.py and admin API routes
```
