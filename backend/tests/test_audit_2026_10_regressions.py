"""Regression tests for the fixes from AUDIT-2026-10-09.md (Fase 1).

Each test is named after the finding it guards. The finding ids (C1…C6) refer to
section 1 of the audit report.
"""
import os
import uuid
from unittest.mock import MagicMock, patch

from tests.conftest import INTEGRATION_KEYS


def _make_client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.limiter.enabled = False
    flask_app.rag_engine.get_answer = MagicMock(return_value="RAG answer")
    return flask_app, flask_app.app.test_client()


def _sid() -> str:
    return f"test_audit_{uuid.uuid4().hex[:8]}"


def _post(client, message, sid):
    resp = client.post("/api/chat", json={"message": message, "session_id": sid})
    assert resp.status_code == 200, resp.data
    return resp.get_json()


# ---------------------------------------------------------------------------
# C2: the suite must never reach live services, even with a filled-in .env
# ---------------------------------------------------------------------------

def test_integration_keys_are_blank_during_tests():
    import app as flask_app  # noqa: F401 — load_dotenv has run by now

    leaked = [k for k in INTEGRATION_KEYS if os.environ.get(k)]
    assert not leaked, f"Live credentials visible to the test suite: {leaked}"
