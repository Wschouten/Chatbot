"""Fase 4 regressions — intent router and escalation catalogue.

Table-driven, one row per finding in P1-1 and P1-2 of
improvement-plan/CHATLOG-ANALYSE-2026-07-29.md. The customer sentences are the
phrasings from the report; each case names the production session it came from.

Two layers:
- classify_intent: pure, no Flask, no mocks. This is where routing is decided.
- the chat endpoint: proves the router actually replaces the old flow order, e.g.
  that an order change no longer gets the shipment-number prompt.
"""
import json
import os
import sys
import uuid
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import classify_intent  # noqa: E402


# ---------------------------------------------------------------------------
# classify_intent — routing table
# ---------------------------------------------------------------------------

ORDER_ADMIN_CASES = [
    ("sess_AzJ5", "Kan ik de afleverplek nog wijzigen?"),
    ("sess_rTH9QN", "Ik wil mijn bestelling annuleren"),
    ("sess_t07xU9", "Kan mijn bestelling gewijzigd worden?"),
    ("sess_R1ozEf", "Ik wil een ander afleveradres doorgeven"),
    ("sess_3cqmat", "Kan de leverdatum verzet worden naar volgende week?"),
    ("sess_1WhsN", "Kunnen jullie BS6794 in mijn bestelling wijzigen naar Bojardin Premium?"),
    ("sess_hxOpVpQ", "Ik wil mijn bestelling wijzigen, is een mail naar jullie voldoende?"),
    ("sess_SCh48", "Ik heb een aanmaning gekregen maar ik heb al betaald"),
    ("sess_B9h3CC", "Kan ik een factuur krijgen van mijn bestelling?"),
    ("sess_nwSmDx", "Ik heb een btw-factuur nodig voor de boekhouding"),
    ("sess_i2lToQ", "BS7950"),
]

# Verbatim from chat-export-2026-07-29.json (typos included). The first draft of
# the catalogue was written from the report's summaries and missed most of these —
# "er zat te weinig aarde in" and "Dat staat wel op de zak" both fell through to RAG.
ESCALATE_TOPIC_CASES = [
    ("sess_Q7lJWI", "Zending staat manco"),
    ("sess_HLzFUh", "Ik heb een big bag ontvangen maar er zat te weinig aarde in voor wat ik besteld heb"),
    ("sess_YUdjVS", "we wachten nu 10 dagen?"),
    ("sess_GiDjnx", "Waarom vragen jullie een andere prijs als waar je het voor aanbied?"),
    ("sess_GiDjnx", "Op internet bied je 1m3 voor € 174,90 aan en als je hem in het "
                    "winkelwagendje hebt, betaal je € 229,95???"),
    ("sess_en-gDo", "Graag zou ik een offerte ontvangen voor 15m3 boomschors met keuring "
                    "t.b.v. valbescherming bij een glijbaan."),
    ("sess_2qw1YT", "We hebben 3 kuub nodig maar de staffel gaat maar tot 2kuub"),
    ("sess_2qw1YT", "Wie kan die info wel geven"),
    ("sess_8K0j5", "maar waarom doet jullie telefoonnummer het niet?"),
    ("sess_8K0j5", "Hij gaat 1x over en daarna wordt het verbroken"),
    ("sess_8Qchs", "Ik heb gisterenmiddag telefonisch iemand gesproken en zou worsen "
                   "teruggebeld. Is nog niet geneurs"),
    ("sess_B9h3CC", "Betaling gelukt maar daarna een fout op de website en heb nog geen "
                    "email ontvangen van bevestiging"),
    ("sess_TDOgT58", "Dat staat wel op de zak"),
    ("sess_epXnDes", "Er staat letterlijk op de zijkant van de bigbag dat ie hergebruikt "
                     "kan worden via boomschors.nl/hergebruik"),
    ("sess_Lv59sQ", "Ik wil twee keer 36 zakken Bemeste Tuinaarde bestellen en laten "
                    "leveren in Noord-Frankrijk. Kan ik daarvoor een prijsopgave ontvangen?"),
    ("_damage", "De zakken kwamen kapot aan"),
    ("_manco", "De helft is geleverd, de rest niet"),
]

# Questions that must NOT escalate: the knowledge base answers these. Over-escalation
# is the failure mode this catalogue is most at risk of, so these are the guard rail.
# Running the router over all 803 user messages in the export hands off 10.3% of them.
RAG_CASES = [
    "Hoe werkt retourneren bij jullie?",
    "Wat kost een bigbag Franse boomschors?",
    "Welke fracties boomschors hebben jullie?",
    "Hoeveel kuub heb ik nodig voor 20 m2 bij 6 cm?",
    "Wat zijn de verzendkosten naar Nederland?",
    "Is 5 cm te weinig voor onkruidwering?",
    "Krijg ik korting bij grote hoeveelheden?",
    "Moet er worteldoek onder de cacaodoppen?",
    "Wat is het verschil tussen Franse boomschors en dennenschors?",
    "Is de biologische moestuinpotgrond turfvrij?",
]


# Labels that hand the conversation to a colleague.
HANDOFF_INTENTS = {'human_request', 'order_admin', 'escalate_topic'}


@pytest.mark.parametrize("session,message", ORDER_ADMIN_CASES)
def test_order_admin_routes_to_a_human(session, message):
    """Order changes used to hit TRACKING_INTENT_RE on "mijn bestelling" and got
    the shipment-number prompt instead of a colleague."""
    assert classify_intent(message) == 'order_admin', session


@pytest.mark.parametrize("session,message", ESCALATE_TOPIC_CASES)
def test_escalation_catalogue_routes_to_a_human(session, message):
    """P1-2: situations that need a human by definition. The bot used to repeat
    "dat kan ik niet zien" until the customer gave up.

    Asserts the destination, not the exact label: "zakelijk bestellen op factuur"
    is both an invoice question and a B2B question, and either label sends it to a
    colleague with sensible copy.
    """
    assert classify_intent(message) in HANDOFF_INTENTS, session


@pytest.mark.parametrize("message", RAG_CASES)
def test_knowledge_base_questions_do_not_escalate(message):
    """The catalogue must not swallow ordinary questions — over-escalation is the
    failure mode this design is most at risk of.

    Note these do not all classify as 'rag': "hoe werkt retourneren" is
    'return_payment' and "hebben jullie …" is 'stock'. Both fall through to RAG in
    the handler (stock only enters its flow once Shopify is configured, which is a
    separate known issue). What matters here is that none of them escalate.
    """
    assert classify_intent(message) not in HANDOFF_INTENTS, message


def test_sess_7xo9rz_pre_purchase_beats_tracking():
    """"als ik deze ochtend frans boomschors 1 kuub bestel" — six words between
    "ik" and "bestel", so the old {0,5} gap missed it and WISMO took over."""
    msg = "als ik deze ochtend frans boomschors 1 kuub bestel, wanneer is het er?"
    assert classify_intent(msg) == 'pre_purchase'


def test_sess_rnlik9_no_order_yet_is_not_tracking():
    """The bot answered "Ik heb nog geen bestelling gedaan" with "je zendingnummer
    staat in de verzendbevestigingsmail"."""
    assert classify_intent("Ik heb nog geen bestelling gedaan") == 'pre_purchase'


def test_human_request_wins_over_tracking_keywords():
    """sess_x6Nu71 / sess_rWRRux: the escalation phrase and a tracking keyword in
    one sentence — the human must win."""
    assert classify_intent("Ik wil een medewerker spreken over mijn bestelling") == 'human_request'


def test_tracking_still_routes_to_tracking():
    """Guard against the router quietly disabling track & trace."""
    assert classify_intent("Waar is mijn pakket?") == 'tracking'
    assert classify_intent("Ik heb een zendingnummer") == 'tracking'


# ---------------------------------------------------------------------------
# End-to-end through the chat endpoint
# ---------------------------------------------------------------------------

def _make_session_id() -> str:
    return f"test_{uuid.uuid4().hex[:12]}"


def _seed_session(session_id: str, state: dict) -> None:
    os.makedirs("data/sessions", exist_ok=True)
    with open(os.path.join("data/sessions", f"{session_id}.json"), "w", encoding="utf-8") as f:
        json.dump(state, f)


def _load_session(session_id: str) -> dict:
    path = os.path.join("data/sessions", f"{session_id}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _post(client, message: str, session_id: str) -> dict:
    resp = client.post(
        "/api/chat",
        json={"message": message, "session_id": session_id},
        content_type="application/json",
    )
    assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.data}"
    return resp.get_json()


@pytest.fixture
def client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["RATELIMIT_ENABLED"] = False
    # Disable the limiter object itself; RATELIMIT_ENABLED alone leaks the 30/min
    # cap on /api/chat into later test modules as 429s.
    flask_app.limiter.enabled = False
    flask_app.rag_engine.get_answer = MagicMock(return_value="RAG answer")
    flask_app.rag_engine.detect_language = MagicMock(return_value="nl")
    flask_app.rag_engine.detect_ticket_intent = MagicMock(return_value="giving_name")
    flask_app.rag_engine.extract_name = MagicMock(side_effect=lambda t: t.strip())
    return flask_app.app.test_client()


def test_sess_azj5_order_change_gets_a_colleague_not_a_shipment_prompt(client):
    sid = _make_session_id()
    data = _post(client, "Kan ik de afleverplek van mijn bestelling nog wijzigen?", sid)
    assert "zendingnummer" not in data["response"].lower()
    assert "naam" in data["response"].lower()
    state = _load_session(sid)
    assert state.get("state") == "awaiting_name"
    assert state.get("escalation_reason") == "order_admin"


def test_sess_q7ljwi_short_delivery_escalates(client):
    sid = _make_session_id()
    data = _post(client, "Ik heb te weinig geleverd gekregen, er ontbreken 2 zakken", sid)
    assert "naam" in data["response"].lower()
    assert _load_session(sid).get("escalation_reason") == "escalate_topic"


def test_sess_i2ltoq_bs_number_is_never_described_as_a_product(client):
    """"BS7950 is een van onze boomschorsproducten" was invented — the knowledge
    base contains no BS codes at all."""
    sid = _make_session_id()
    data = _post(client, "Wat is BS7950?", sid)
    assert "boomschors" not in data["response"].lower()
    assert _load_session(sid).get("state") == "awaiting_name"


def test_sess_sjnuc_interrupted_handoff_keeps_the_name(client):
    """The handoff used to vanish when the customer asked something in between,
    and started over from "Wat is je naam?" afterwards."""
    sid = _make_session_id()
    _seed_session(sid, {"state": "awaiting_name", "language": "nl"})

    import app as flask_app
    flask_app.rag_engine.detect_ticket_intent = MagicMock(return_value="giving_name")
    _post(client, "Jarno", sid)
    assert _load_session(sid).get("name") == "Jarno"

    # Interruption: a new question instead of the email address.
    flask_app.rag_engine.detect_ticket_intent = MagicMock(return_value="new_question")
    _post(client, "Hoeveel kuub zit er in een bigbag?", sid)
    assert _load_session(sid).get("name") == "Jarno", "name was wiped by the interruption"

    # Asking for a human again must not re-ask for the name.
    data = _post(client, "Ik wil toch een medewerker spreken", sid)
    assert "e-mailadres" in data["response"].lower()
    assert "Jarno" in data["response"]
    assert _load_session(sid).get("state") == "awaiting_email"


def test_sess_epxndes_completed_handoff_is_not_restarted(client):
    """"Ik heb je bericht doorgestuurd" → the customer asks again → "Wat is je
    naam?" four times in a row. The guard now sits inside _start_handoff, so every
    entry point (router, frustration gate, dead end, __HUMAN_REQUESTED__) is covered.
    """
    sid = _make_session_id()
    _seed_session(sid, {"state": "inactive", "handoff_done": True, "language": "nl"})
    data = _post(client, "Ik wil een collega spreken", sid)
    assert "naam" not in data["response"].lower()
    assert "al bij een collega" in data["response"]
    assert _load_session(sid).get("state") != "awaiting_name"


def test_sess_lhvfgm_phone_number_after_handoff_is_forwarded(client):
    """A callback number sent after the handoff went nowhere."""
    import app as flask_app

    sid = _make_session_id()
    _seed_session(sid, {
        "state": "inactive", "handoff_done": True, "language": "nl",
        "name": "Jarno", "email": "jarno@example.com",
    })
    sender = MagicMock(return_value=True)
    flask_app.escalation_client.send_email_async = sender

    data = _post(client, "Bel me even op 06-12345678", sid)
    assert sender.called, "the phone number was not forwarded"
    assert "telefoonnummer" in data["response"].lower()
    assert _load_session(sid).get("phone_forwarded") is True

    # Only once — a second number must not spawn another ticket.
    sender.reset_mock()
    _post(client, "Of bel 0342-784000", sid)
    assert not sender.called
