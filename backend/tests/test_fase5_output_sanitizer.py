"""Fase 5 — output sanitizer, calculation block and pasted product URLs.

The defects here are generation defects, not reasoning ones: no prompt rule stops the
model from dropping a Devanagari word into a Dutch sentence. Hence a hard gate on the
way out, tested with the real strings from CHATLOG-ANALYSE-2026-07-29.md.
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rag_engine  # noqa: E402
from rag_engine import RagEngine, check_output, guess_language, slug_to_query  # noqa: E402


# ---------------------------------------------------------------------------
# check_output
# ---------------------------------------------------------------------------

def test_sess_wgocfxem_devanagari_is_rejected():
    """"mail naar ... voor meer जानकारी" — seven sessions had this."""
    assert check_output("Stuur een mail naar klantenservice voor meer जानकारी", "nl") == 'foreign_script'


def test_sess_j5mh_armenian_is_rejected():
    """"een SKAL-certificaat niet պարտ verplicht"."""
    assert check_output("Een SKAL-certificaat is niet պարտ verplicht", "nl") == 'foreign_script'


@pytest.mark.parametrize("text", [
    "De prijslijst is hier niet ingevuld, daarom kan ik de prijs niet geven.",
    "Dat staat niet in de context die ik heb.",
    "Volgens de aangeleverde informatie is dat niet mogelijk.",
    "I can't find that in the knowledge base.",
])
def test_leaked_system_language_is_rejected(text):
    """Backstop for the fase-3 prompt rules: customers read "omdat de actuele
    prijslijst hier niet is ingevuld"."""
    lang = 'en' if text.startswith("I can't") else 'nl'
    assert check_output(text, lang) == 'system_language'


def test_sess_piduLB_english_answer_to_a_dutch_question_is_rejected():
    """A Dutch address change was answered entirely in English."""
    text = ("You can change the address if you contact us, and we will forward this to "
            "the carrier for you. Please note that this is not always possible.")
    assert check_output(text, "nl") == 'wrong_language'


def test_dutch_answer_to_an_english_question_is_rejected():
    text = ("Je kunt het adres niet meer wijzigen, want de zending is al onderweg naar "
            "de vervoerder. Neem gerust contact met ons op.")
    assert check_output(text, "en") == 'wrong_language'


@pytest.mark.parametrize("text,lang", [
    ("Nee, onze biologische moestuinpotgrond is niet turfvrij. Die bevat turfsoorten.", "nl"),
    ("48 m x 0,8 m x 0,08 m = 3,072 m³, dus ongeveer 3,1 kuub.", "nl"),
    ("No, that soil is not peat-free. It contains peat types.", "en"),
    ("Bekijk het product hier: https://www.boomschors.nl/products/franse-boomschors", "nl"),
])
def test_good_answers_pass_untouched(text, lang):
    """A false positive costs a needless OpenAI call, so the gate must be quiet."""
    assert check_output(text, lang) is None


def test_control_tokens_are_never_sanitized():
    """__UNKNOWN__ and __HUMAN_REQUESTED__ are consumed by app.py, not by the customer."""
    assert check_output("__UNKNOWN__", "nl") is None
    assert check_output("__HUMAN_REQUESTED__", "en") is None


def test_a_single_emoji_is_not_a_foreign_script():
    assert check_output("Top, dat regel ik voor je! 👍🌱", "nl") is None


# ---------------------------------------------------------------------------
# guess_language — corrects the language stored on the session
# ---------------------------------------------------------------------------

def test_sess_ow87gm_dutch_message_corrects_a_stuck_english_session():
    """Seven English canned flow messages in a row while the customer wrote Dutch.
    Those are not model output, so the output gate never sees them — the stored
    language itself has to be corrected.

    Found by running check_output over all 803 real bot answers in the export, not by
    the tests: 7 of the 10 language flags were canned strings, not generated text.
    """
    assert guess_language("Ik heb het zendingnummer niet, kun je het voor mij opzoeken?") == 'nl'
    assert guess_language("Waar is mijn pakket? Het is nog niet geleverd") == 'nl'


def test_english_customer_is_still_recognised():
    assert guess_language("Can you tell me if the bark is available for delivery?") == 'en'


@pytest.mark.parametrize("text", ["hoi", "BS6794", "ok", "3 kuub", "👍"])
def test_no_guess_without_evidence(text):
    """Silence beats a coin flip: an unlucky guess would flip the whole conversation."""
    assert guess_language(text) is None


# ---------------------------------------------------------------------------
# Pasted product URLs
# ---------------------------------------------------------------------------

def test_sess_xdtnfb_pasted_product_url_becomes_a_search_query():
    url = ("https://www.boomschors.nl/products/franse-boomschors-45-80mm-in-big-bag"
           "?_pos=3&_psq=Franse+boomschors")
    assert slug_to_query(url) == "franse boomschors 45 80mm in big bag"


def test_non_product_text_yields_no_query():
    assert slug_to_query("Hebben jullie Franse boomschors?") is None
    assert slug_to_query("https://www.example.com/products/iets-anders") is None


# ---------------------------------------------------------------------------
# The gate inside get_answer: one retry, then a safe answer
# ---------------------------------------------------------------------------

class _ScriptedOpenAI:
    """Returns the queued answers in order and records how often it was called."""

    def __init__(self, answers):
        self._answers = list(answers)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        text = self._answers.pop(0) if self._answers else ""
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class _Stub:
    chat_model = "gpt-5.4-mini"
    relevance_threshold = 1.2
    _build_conversation_summary = staticmethod(RagEngine._build_conversation_summary)

    def __init__(self, answers):
        self.openai_client = _ScriptedOpenAI(answers)
        self.collection = object()

    def _get_cached_context(self, query):
        return "Franse Boomschors Premium: grove fractie, per bigbag van 1 m3."


def _answer(monkeypatch, answers, query="Wat kost een bigbag?"):
    monkeypatch.setattr(rag_engine, "RAG_DEPENDENCIES_LOADED", True)
    stub = _Stub(answers)
    result = RagEngine.get_answer(stub, query, language="nl")
    return result, stub.openai_client.calls


def test_a_rejected_answer_is_regenerated_once(monkeypatch):
    result, calls = _answer(monkeypatch, [
        "De prijs staat niet in de context.",          # rejected
        "Die prijs vind je in de webshop.",            # accepted
    ])
    assert result == "Die prijs vind je in de webshop."
    assert calls == 2, "expected exactly one retry"


def test_a_still_broken_retry_falls_back_instead_of_shipping_it(monkeypatch):
    result, calls = _answer(monkeypatch, [
        "Voor meer जानकारी kun je mailen.",
        "Nog steeds जानकारी in het antwoord.",
    ])
    assert "जानकारी" not in result
    assert "collega" in result
    assert calls == 2


def test_a_good_answer_costs_no_extra_call(monkeypatch):
    result, calls = _answer(monkeypatch, ["Die prijs vind je in de webshop."])
    assert result == "Die prijs vind je in de webshop."
    assert calls == 1


def test_the_calculation_is_handed_to_the_model_precomputed(monkeypatch):
    """sess_O7LCO1: the model reported 3,84 m³ for a 3,072 m³ path. It no longer has
    to multiply anything — the line is in the prompt."""
    monkeypatch.setattr(rag_engine, "RAG_DEPENDENCIES_LOADED", True)
    captured = {}

    class _Capturing(_ScriptedOpenAI):
        def _create(self, **kwargs):
            captured['messages'] = kwargs['messages']
            return super()._create(**kwargs)

    stub = _Stub(["3,072 m3 dus ongeveer 3,1 kuub."])
    stub.openai_client = _Capturing(["3,072 m3 dus ongeveer 3,1 kuub."])
    RagEngine.get_answer(
        stub, "hoeveel kuub voor 48 m lang, 80 cm breed en 8 cm diep?", language="nl"
    )
    prompt = captured['messages'][-1]['content']
    assert "REKENHULP" in prompt
    assert "3,072 m3" in prompt
