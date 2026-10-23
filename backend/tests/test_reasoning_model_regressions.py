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
