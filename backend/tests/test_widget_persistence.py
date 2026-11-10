"""The widget must keep the conversation across page navigation (2026-11-10).

The session id lived in sessionStorage and the transcript nowhere: every page change
showed an empty chat, and a bot link (target=_blank, noopener) opened a tab with a
brand-new session. Verified in a headless browser; this guards the source against
a regression back to per-tab storage. There is no JS test runner in this repo.
"""
import os

WIDGET = os.path.join("..", "frontend", "static", "widget.js")


def _src():
    with open(WIDGET, encoding="utf-8") as f:
        return f.read()


def test_session_id_is_not_per_tab():
    src = _src()
    assert "sessionStorage.setItem(SESSION_KEY" not in src
    assert "sessionStorage.getItem(SESSION_KEY" not in src
    assert "localStorage.setItem(SESSION_KEY" in src


def test_transcript_is_stored_and_restored():
    src = _src()
    assert src.count("remember(") >= 3  # definition + user message + bot reply
    assert "loadHistory().forEach" in src


def test_idle_conversation_expires():
    assert "IDLE_MS" in _src()
