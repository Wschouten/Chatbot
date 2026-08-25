"""Regression tests for the bugs found in the 2026-07-29 chatlog analysis.

Each test is named after the production session that exposed the bug. See
improvement-plan/CHATLOG-ANALYSE-2026-07-29.md for the full transcripts.

Run from the backend/ directory:
    pytest tests/test_chatlog_regressions.py -v
"""
import json
import os
import sys
import uuid
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_chat_flows.py)
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


def _make_client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["RATELIMIT_ENABLED"] = False
    # This module posts a lot of messages; without disabling the limiter object
    # itself the 30/min cap on /api/chat leaks into later test modules as 429s.
    flask_app.limiter.enabled = False
    flask_app.rag_engine.generate_response = MagicMock(return_value="RAG answer")
    flask_app.rag_engine.detect_language = MagicMock(return_value="nl")
    flask_app.rag_engine.detect_ticket_intent = MagicMock(return_value="giving_name")
    return flask_app.app.test_client()


def _tracking_state(**extra) -> dict:
    """Session sitting in step 1 of the tracking flow (waiting for a shipment number)."""
    import datetime
    state = {
        "awaiting_order_number": True,
        "tracking_timestamp": datetime.datetime.now().isoformat(),
        "language": "nl",
        "chat_history": [],
    }
    state.update(extra)
    return state


# ---------------------------------------------------------------------------
# P0-1: a bare word must never be read as an order number
# sess_7Xo9Rz (2026-07-28), sess_Zk0FF, sess_u444ko, sess_d0hsN8, sess_fM-Mei
# ---------------------------------------------------------------------------

class TestNoGarbageOrderNumbers:
    def test_extract_rejects_words_without_digits(self):
        from app import extract_order_identifier

        # These all produced "Je bestelnummer (**GEEN**) heb ik ontvangen" in production.
        for message in (
            "Ik heb nog geen zending",
            "Raar ik hen nochtans deze nummers ontvangen",
            "ik wil weten hoe lang het duurt voordat ik ga bestellen",
            "BESTEL",
            "Heb ik niet",
        ):
            identifier, _ = extract_order_identifier(message)
            assert identifier is None, (
                f"{message!r} contains no digits and must not yield an order number, "
                f"got {identifier!r}"
            )

    def test_sess_7xo9rz_no_shipment_reply_does_not_echo_geen(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        data = _post(client, "Ik heb nog geen zending", sid)

        assert "GEEN" not in data["response"], (
            "The word 'geen' must not come back as an order number"
        )

    def test_statusweb_numbers_still_recognised(self):
        from app import extract_order_identifier

        identifier, is_statusweb = extract_order_identifier("4208384248")
        assert (identifier, is_statusweb) == ("4208384248", True)

    def test_sess_5rpwyj_shipment_number_with_spaces(self):
        """'420 836 0360' was ignored entirely; digits must be joined."""
        from app import extract_order_identifier

        identifier, is_statusweb = extract_order_identifier(
            "Op de status web staat het volgende Zendingsnummer: 420 836 0360"
        )
        assert identifier == "4208360360"
        assert is_statusweb is True

    def test_order_reference_still_recognised(self):
        from app import extract_order_identifier

        identifier, is_statusweb = extract_order_identifier("Het gaat om bestelling BS9940")
        assert identifier == "BS9940"
        assert is_statusweb is False, "BS-references are not StatusWeb codes"

    def test_short_numeric_reference_still_recognised(self):
        from app import extract_order_identifier

        identifier, is_statusweb = extract_order_identifier("6655?")
        assert identifier == "6655"
        assert is_statusweb is False


# ---------------------------------------------------------------------------
# P0-2: a customer must always be able to escape a guided flow
# sess_LRVXh5 (8x identical), sess_rWRRux, sess_RQ86kt, sess_IRUGI, sess_VgkVCn
# ---------------------------------------------------------------------------

class TestEscapeHatch:
    def test_sess_rwrrux_echte_persoon_breaks_out_of_tracking(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        data = _post(client, "Echte persoon", sid)

        assert "zendingnummer" not in data["response"].lower(), (
            "A human request inside the tracking flow must not be answered with "
            "the shipment-number prompt again"
        )
        assert _load_session(sid).get("state") == "awaiting_name"

    def test_sess_rq86kt_verbind_me_door_breaks_out_of_postcode_step(self):
        import datetime

        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "awaiting_shopify_postcode": True,
            "pending_shopify_order_number": "18005131",
            "shopify_verification_timestamp": datetime.datetime.now().isoformat(),
            "language": "nl",
            "chat_history": [],
        })

        data = _post(client, "Verbind me door", sid)

        assert "postcode" not in data["response"].lower()
        assert _load_session(sid).get("state") == "awaiting_name"

    def test_phone_request_breaks_out_of_tracking(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        data = _post(client, "ik wil telefonisch contact", sid)

        assert "0342" in data["response"]
        assert not _load_session(sid).get("awaiting_order_number")

    def test_frustration_breaks_out_of_tracking(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        data = _post(client, "Dit is belachelijk", sid)

        assert "zendingnummer" not in data["response"].lower()
        assert _load_session(sid).get("state") == "awaiting_name"


# ---------------------------------------------------------------------------
# P0-2: no infinite identical re-prompts — offer a human after two attempts
# sess_LRVXh5, sess_IRUGI, sess_XMO4Me, sess_Zk0FF
# ---------------------------------------------------------------------------

class TestFlowDeadEnd:
    def test_sess_lrvxh5_second_failed_attempt_offers_a_human(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        first = _post(client, "dat weet ik niet", sid)["response"]
        second = _post(client, "dat weet ik echt niet", sid)["response"]

        assert first != second, "The bot must not repeat the identical prompt"
        assert _load_session(sid).get("state") == "awaiting_name", (
            "After two failed attempts the flow must hand over to a human"
        )

    def test_dead_end_escalation_records_reason(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        _post(client, "dat weet ik niet", sid)
        _post(client, "dat weet ik echt niet", sid)

        assert _load_session(sid).get("escalation_reason") == "flow_dead_end"


# ---------------------------------------------------------------------------
# P2-4: an email given in the name step
# sess_avyJ8 — "Leuk je te ontmoeten, [EMAIL_REDACTED]!"
# ---------------------------------------------------------------------------

class TestEmailGivenAsName:
    def test_sess_avyj8_email_is_not_greeted_as_a_name(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "awaiting_name",
            "language": "nl",
            "question": "Ik wil een medewerker spreken",
            "chat_history": [],
        })

        data = _post(client, "kirsten@example.com", sid)

        assert "Leuk je te ontmoeten" not in data["response"], (
            "An email address must not be greeted as if it were the customer's name"
        )
        assert _load_session(sid).get("email") == "kirsten@example.com"

    def test_name_after_email_escalates_without_asking_again(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "awaiting_name",
            "language": "nl",
            "question": "Ik wil een medewerker spreken",
            "email": "kirsten@example.com",
            "chat_history": [],
        })

        data = _post(client, "Kirsten", sid)

        assert "e-mailadres" not in data["response"].lower(), (
            "The email is already known — don't ask for it a second time"
        )
        assert _load_session(sid).get("handoff_done") is True


# ---------------------------------------------------------------------------
# P2-4: the handoff must not restart once it has completed
# sess_epXnDes — "Wat is je naam?" four times after the ticket was already sent
# ---------------------------------------------------------------------------

class TestHandoffDoesNotRestart:
    def test_sess_epxndes_second_request_confirms_instead_of_restarting(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "inactive",
            "handoff_done": True,
            "language": "nl",
            "chat_history": [],
        })

        data = _post(client, "Ik wil een medewerker spreken", sid)

        assert "Wat is je naam" not in data["response"], (
            "The handoff already completed — asking for the name again is the bug"
        )
        assert "collega" in data["response"].lower()


# ---------------------------------------------------------------------------
# sess_jLgTn7 (2026-08-24): "vanaf hoe laat kan ik ook met jullie telefonisch
# contact opnemen?" was answered with the phone number and nothing else, twice.
# PHONE_CONTACT_RE returns before the RAG, so the canned reply is the only thing
# the customer sees — it has to name the hours itself.
#
# The same session shows the second half of the bug: the shortcut returned
# without storing the turn, so the follow-up "tussen welke tijden kan dat?" was
# reformulated against the delivery question two turns earlier and got a
# delivery answer.
# ---------------------------------------------------------------------------

class TestPhoneReplyNamesOpeningHours:
    def test_sess_jlgtn7_phone_reply_names_the_opening_hours(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "vanaf hoe laat kan ik ook met jullie telefonisch contact opnemen?", sid)

        assert "09:00" in data["response"] and "17:00" in data["response"], (
            f"A phone question never reaches the KB, so the canned reply must name "
            f"the hours: {data['response']!r}"
        )

    def test_sess_jlgtn7_phone_reply_still_names_the_number(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "kan ik jullie bellen?", sid)

        assert "0342" in data["response"]

    def test_sess_jlgtn7_english_phone_reply_names_the_hours(self):
        import app as flask_app

        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {"state": "inactive", "language": "en", "chat_history": []})
        flask_app.rag_engine.detect_language = MagicMock(return_value="en")
        try:
            data = _post(client, "can I reach you by phone?", sid)
        finally:
            flask_app.rag_engine.detect_language = MagicMock(return_value="nl")

        assert "09:00" in data["response"] and "17:00" in data["response"], (
            f"English customers need the hours too: {data['response']!r}"
        )

    def test_sess_jlgtn7_phone_turn_is_kept_in_chat_history(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {"state": "inactive", "language": "nl", "chat_history": []})

        _post(client, "vanaf hoe laat zijn jullie telefonisch bereikbaar?", sid)

        history = _load_session(sid).get("chat_history", [])
        roles = [turn.get("role") for turn in history]
        assert roles[-2:] == ["user", "assistant"], (
            f"The shortcut must record its turn, or the next follow-up is "
            f"reformulated against a stale history: {history!r}"
        )
        assert "telefonisch" in history[-2]["content"]
        assert "0342" in history[-1]["content"]

    def test_sess_jlgtn7_phone_escape_from_handoff_also_names_hours_and_stores_turn(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "awaiting_name",
            "language": "nl",
            "question": "Ik wil een medewerker spreken",
            "chat_history": [],
        })

        data = _post(client, "ik wil liever telefonisch contact", sid)

        assert "09:00" in data["response"] and "17:00" in data["response"]
        state = _load_session(sid)
        assert state.get("state") == "inactive"
        assert len(state.get("chat_history", [])) == 2

    def test_sess_jlgtn7_phone_escape_from_guided_flow_also_names_hours(self):
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, _tracking_state())

        data = _post(client, "kan ik jullie bellen, en hoe laat kan dat?", sid)

        assert "09:00" in data["response"] and "17:00" in data["response"]
        assert "verzendnummer" not in data["response"].lower()
