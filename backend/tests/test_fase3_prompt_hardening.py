"""Fase 3 regressions — prompt hardening (chatlog analysis 2026-07-29).

These assert on the system prompt that get_answer actually builds, not on model
output: the failures in the report (fabricated actions, internal system language,
false "zoals ik eerder noemde") were all prescribed or permitted by the prompt
text itself. Each test is named after the production session that exposed it.

No OpenAI calls — a stub captures the messages that would have been sent.
"""
from types import SimpleNamespace

import pytest

import rag_engine
from rag_engine import RagEngine

_CONTEXT = "Franse Boomschors Premium: grove fractie 20-40 mm, per bigbag van 1 m3."


class _FakeOpenAI:
    """Records the messages of every chat completion instead of sending them."""

    def __init__(self, sink: list) -> None:
        self._sink = sink
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self._sink.append(kwargs["messages"])
        message = SimpleNamespace(content="ok")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _Stub:
    """Minimal stand-in for RagEngine: only what get_answer touches en route to
    the prompt. Context comes from the cache so no embedding call is needed."""

    chat_model = "gpt-5.4-mini"
    relevance_threshold = 1.2
    _build_conversation_summary = staticmethod(RagEngine._build_conversation_summary)

    def __init__(self, *, with_context: bool) -> None:
        self.sink: list = []
        self.openai_client = _FakeOpenAI(self.sink)
        self.collection = object() if with_context else None

    def _get_cached_context(self, query: str) -> str:
        return _CONTEXT


def _system_prompt(language: str, monkeypatch) -> str:
    """The system prompt for the normal (with-context) path."""
    monkeypatch.setattr(rag_engine, "RAG_DEPENDENCIES_LOADED", True)
    stub = _Stub(with_context=True)
    RagEngine.get_answer(stub, "Hoeveel kuub heb ik nodig?", language=language)
    assert stub.sink, "no completion was requested"
    return stub.sink[-1][0]["content"]


@pytest.fixture
def prompt_nl(monkeypatch):
    return _system_prompt("nl", monkeypatch)


@pytest.fixture
def prompt_en(monkeypatch):
    return _system_prompt("en", monkeypatch)


def test_sess_zcbdeiy_prompt_forbids_confirming_admin_actions(prompt_nl, prompt_en):
    """"26 mei heb ik genoteerd" — the bot promised actions the system never does."""
    assert "WAT JE NOOIT BEVESTIGT" in prompt_nl
    for phrase in ["noteren", "annuleren", "losplek", "chauffeur", "terugbetaling"]:
        assert phrase in prompt_nl, phrase
    assert "genoteerd" in prompt_nl  # the exact promise it must not make

    assert "WHAT YOU NEVER CONFIRM" in prompt_en
    for phrase in ["note down", "cancel", "unloading spot", "driver", "refund"]:
        assert phrase in prompt_en, phrase


def test_sess_jdhaifes_prompt_forbids_internal_system_language(prompt_nl, prompt_en):
    """Customers read "omdat de actuele prijslijst hier niet is ingevuld"."""
    assert "kennisbank" in prompt_nl and "niet ingevuld" in prompt_nl
    assert "webshop" in prompt_nl
    assert "knowledge base" in prompt_en and "not filled in" in prompt_en


def test_sess_b0kxul_prompt_no_longer_prescribes_as_i_mentioned(prompt_nl, prompt_en):
    """The prompt used to prescribe the phrase, so the bot claimed things it
    never said and held its ground after the customer corrected it."""
    assert "verwijs dan naar je eerdere antwoord" not in prompt_nl
    assert "reference your previous answer" not in prompt_en
    # The replacement must be present, not just the old line removed.
    assert "letterlijk in de geschiedenis staat" in prompt_nl
    assert "literally in the history" in prompt_en


def test_sess_rmc_prompt_requires_yes_no_alignment(prompt_nl, prompt_en):
    """"Ja, voor biologische aarde is een SKAL-certificaat niet verplicht"."""
    assert "'nee, maar...'" in prompt_nl
    assert "'no, but...'" in prompt_en


def test_sess_o7lco1_prompt_allows_arithmetic(prompt_nl, prompt_en):
    """48 x 0,80 x 0,08 came out as 3,84 m3 (is 3,07), and sess_OG881c refused
    to convert 5 cm at all. Arithmetic is not knowledge."""
    assert "rekenkunde, geen kennis" in prompt_nl
    assert "156 zakken" in prompt_nl  # the 4 x 39 unit mix-up
    assert "arithmetic, not knowledge" in prompt_en
    assert "156 bags" in prompt_en


def test_sess_re9gb_graag_is_consent_not_thanks(prompt_nl, prompt_en):
    """"Graag" (= yes please) was answered with "Graag gedaan!", and in
    sess__7oLpL it routed into the handoff flow instead of the offer."""
    assert "geen bedankje" in prompt_nl
    assert "graag gedaan" in prompt_nl
    assert "not a thank-you" in prompt_en
    # Affirming a non-escalation offer must not trigger a handoff.
    assert "stuur geen __HUMAN_REQUESTED__" in prompt_nl
    assert "do not send __HUMAN_REQUESTED__" in prompt_en


def test_sess_gralegm_no_country_from_place_name(prompt_nl, prompt_en):
    """A customer in Breskens (NL) got Belgian payment and delivery times."""
    assert "Leid nooit een land af uit een plaatsnaam" in prompt_nl
    assert "Never infer a country from a place name" in prompt_en


def test_sess_rlz7_dutch_grammar_rule(prompt_nl):
    """"zou wij" instead of "zouden wij" — Dutch-only rule, no EN counterpart."""
    assert "'zouden wij'" in prompt_nl


def test_sess_2lftnn_no_parroting(prompt_nl, prompt_en):
    """"Ja, die 78 cm massieve kunststof paaltjes bedoel je." — no answer at all."""
    assert "Papegaai" in prompt_nl
    assert "parrot" in prompt_en


def test_no_context_fallback_prompt_is_hardened_too(monkeypatch):
    """The history-only fallback branch prescribed the phrase as well."""
    monkeypatch.setattr(rag_engine, "RAG_DEPENDENCIES_LOADED", True)
    history = [
        {"role": "user", "content": "Wat kost Franse boomschors?"},
        {"role": "assistant", "content": "Die prijs vind je in de webshop."},
    ]
    for language, forbidden, required in (
        ("nl", "Verwijs naar je eerdere antwoorden", "zoals ik eerder noemde"),
        ("en", "Reference your previous answers", "as I mentioned earlier"),
    ):
        stub = _Stub(with_context=False)
        RagEngine.get_answer(stub, "En de levertijd?", chat_history=history, language=language)
        prompt = stub.sink[-1][0]["content"]
        assert forbidden not in prompt
        assert required in prompt  # now named as something never to say
