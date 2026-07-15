"""Regression tests for the Fase 5 audit cleanup (AUDIT-2026-07-11).

Only a safe, behavior-preserving dedup landed in Fase 5: the verbatim
conversation-summary block (RAG-context path vs no-context fallback) was
extracted into RagEngine._build_conversation_summary. The mocked flow suite
doesn't exercise generate_response internals, so cover the helper directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import RagEngine

_HISTORY = [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "We sell bark mulch."},
    {"role": "user", "content": "and gravel?"},
    {"role": "assistant", "content": "Yes, gravel too."},
]


def test_summary_nl():
    out = RagEngine._build_conversation_summary(_HISTORY, "nl")
    assert "Je recente uitspraken" in out
    assert "gravel too" in out  # includes the last assistant statement


def test_summary_en():
    out = RagEngine._build_conversation_summary(_HISTORY, "en")
    assert "Your recent statements" in out
    assert "You said:" in out


def test_summary_empty():
    assert RagEngine._build_conversation_summary([], "nl") == ""
    assert RagEngine._build_conversation_summary([{"role": "user", "content": "hi"}], "en") == ""
