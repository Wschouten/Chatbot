"""Model switch to gpt-5.6-luna (2026-10-23).

A reasoning model rejects every temperature but 1 unless reasoning_effort is
"none", and with reasoning on it spent detect_ticket_intent's 10-token budget
thinking: "hoeveel kost een bigbag boomschors?" came back empty, which the
classifier turns into 'giving_name'.
"""
import re
from pathlib import Path
from unittest.mock import MagicMock

BACKEND = Path(__file__).resolve().parent.parent


def test_every_chat_call_disables_reasoning():
    for name in ("rag_engine.py", "evaluate_rag.py"):
        source = (BACKEND / name).read_text(encoding="utf-8")
        calls = source.count("chat.completions.create(")
        assert calls > 0
        assert len(re.findall(r'reasoning_effort="none"', source)) == calls, name


def test_classifier_sends_reasoning_effort_none():
    from rag_engine import RagEngine

    engine = RagEngine.__new__(RagEngine)
    engine.chat_model = "gpt-5.6-luna"
    engine.openai_client = MagicMock()
    engine.openai_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="new_question"))]

    assert engine.detect_ticket_intent("hoeveel kost een bigbag boomschors?") == "new_question"
    kwargs = engine.openai_client.chat.completions.create.call_args.kwargs
    assert kwargs["reasoning_effort"] == "none"


def _client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.limiter.enabled = False
    flask_app.rag_engine.detect_language = MagicMock(return_value="nl")
    return flask_app, flask_app.app.test_client()


def _post(client, sid, message):
    resp = client.post("/api/chat", json={"message": message, "session_id": sid})
    assert resp.status_code == 200
    return resp.get_json()["response"]


def test_new_question_during_handoff_is_answered_not_handed_off_again():
    """Production replay 2026-10-23: "ik wil iemand spreken", then "hoeveel kost een
    bigbag boomschors?" got "Wat is je naam?" again whenever the model read the
    handoff request in the history as a fresh one."""
    import uuid
    from unittest.mock import patch

    flask_app, client = _client()
    sid = f"test_{uuid.uuid4().hex[:12]}"
    model = lambda q, chat_history=None, language="nl": (  # noqa: E731
        "__HUMAN_REQUESTED__" if chat_history else "Een bigbag kost € 219,95.")

    with patch.object(flask_app.rag_engine, "get_answer", side_effect=model), \
         patch.object(flask_app.rag_engine, "detect_ticket_intent", return_value="new_question"):
        assert "naam" in _post(client, sid, "ik wil iemand spreken")
        assert _post(client, sid, "hoeveel kost een bigbag boomschors?") == "Een bigbag kost € 219,95."
    assert flask_app.get_session_state(sid).get("state") != "awaiting_name"
