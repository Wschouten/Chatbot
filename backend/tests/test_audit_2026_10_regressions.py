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


# ---------------------------------------------------------------------------
# C1: the escalation email must carry the customer's question and name
# ---------------------------------------------------------------------------

def test_escalation_email_contains_question_and_name():
    from email_client import EmailClient

    env = {"MAILERSEND_API_KEY": "k", "SMTP_FROM_EMAIL": "bot@x.nl", "SMTP_TO_EMAIL": "ks@x.nl"}
    with patch.dict(os.environ, env), patch("email_client.http_requests.post") as post:
        post.return_value.raise_for_status.return_value = None
        EmailClient().send_email("Jan", "jan@example.nl", "Ik wil bestelling BS12345 annuleren", [])

    body = post.call_args.kwargs["json"]["text"]
    assert "Ik wil bestelling BS12345 annuleren" in body
    assert "Jan" in body


def test_forwarded_phone_number_reaches_the_email():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "inactive", "handoff_done": True, "language": "nl",
        "name": "Jan", "email": "jan@example.nl",
    })
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email", return_value={"ticket": {}}) as send:
        _post(client, "Bel me even op 0612345678", sid)

    assert send.called
    question = send.call_args.args[2]
    assert "0612345678" in question


# ---------------------------------------------------------------------------
# C4: a failed send must never be reported to the customer as forwarded
# ---------------------------------------------------------------------------

def test_failed_escalation_is_not_reported_as_sent():
    flask_app, client = _make_client()
    sid = _sid()
    flask_app.save_session_state(sid, {
        "state": "awaiting_email", "language": "nl", "name": "Jan",
        "question": "Ik wil een collega spreken", "chat_history": [],
    })
    with patch.object(flask_app, "ESCALATION_METHOD", "email"), \
         patch.object(flask_app.escalation_client, "send_email", return_value=None):
        data = _post(client, "jan@example.nl", sid)

    assert "doorgestuurd" not in data["response"]
    assert "ging iets mis" in data["response"]
    # Not marked as handed off, so asking again retries instead of "al bij een collega".
    assert not flask_app.get_session_state(sid).get("handoff_done")


# ---------------------------------------------------------------------------
# C5: a missing session id must never map visitors onto one shared session
# ---------------------------------------------------------------------------

def test_null_session_id_is_never_shared():
    flask_app, client = _make_client()
    seen = []
    real_get = flask_app.get_session_state

    def spy(session_id):
        seen.append(session_id)
        return real_get(session_id)

    with patch.object(flask_app, "get_session_state", side_effect=spy):
        for _ in range(2):
            resp = client.post("/api/chat", json={"message": "Hallo", "session_id": None})
            assert resp.status_code == 200

    for sid in seen:  # minted ids are not test_-prefixed, so conftest won't purge them
        for path in (f"data/sessions/{sid}.json", f"data/logs/chat_{sid}.json"):
            if os.path.exists(path):
                os.remove(path)

    assert len(seen) == 2
    assert seen[0] != seen[1], "two visitors without a session id shared one session"
    assert "unknown_session" not in seen
