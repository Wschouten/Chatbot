"""End-to-end state machine flow tests using Flask's built-in test client.

All external dependencies (RAG engine, Shopify, shipping API) are mocked so
the suite runs offline with no API keys required.

Run from the backend/ directory:
    pytest tests/ -v
"""
import json
import os
import sys
import uuid
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_id() -> str:
    return f"test_{uuid.uuid4().hex[:12]}"


def _seed_session(session_id: str, state: dict) -> None:
    """Write session state directly to disk so the app picks it up."""
    safe_id = session_id  # already alphanumeric
    os.makedirs("data/sessions", exist_ok=True)
    path = os.path.join("data/sessions", f"{safe_id}.json")
    with open(path, "w", encoding="utf-8") as f:
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


# ---------------------------------------------------------------------------
# Fixtures / setup
# ---------------------------------------------------------------------------

def _make_client():
    """Return a Flask test client with rate-limiting disabled and rag mocked."""
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    flask_app.app.config["RATELIMIT_ENABLED"] = False

    # Mock the rag_engine instance methods so no OpenAI calls are made
    flask_app.rag_engine.generate_response = MagicMock(
        return_value="RAG answer"
    )
    flask_app.rag_engine.detect_language = MagicMock(return_value="nl")
    flask_app.rag_engine.detect_ticket_intent = MagicMock(return_value="provide_name")

    return flask_app.app.test_client()


# ---------------------------------------------------------------------------
# Flow 1: Pre-purchase question bypasses WISMO
# ---------------------------------------------------------------------------

class TestPrePurchaseBypassesWismo:
    def test_response_does_not_ask_for_order_number(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(
            client,
            "als ik vandaag bestel, wanneer wordt het geleverd?",
            sid,
        )

        response = data["response"].lower()
        assert "bestelnummer" not in response, (
            "Pre-purchase question must NOT trigger the WISMO order-number prompt"
        )
        assert "order number" not in response

    def test_session_does_not_enter_awaiting_shopify_order_number(self):
        client = _make_client()
        sid = _make_session_id()

        _post(client, "als ik vandaag bestel, wanneer wordt het geleverd?", sid)

        session = _load_session(sid)
        assert not session.get("awaiting_shopify_order_number"), (
            "Session must NOT have awaiting_shopify_order_number set after a pre-purchase question"
        )


# ---------------------------------------------------------------------------
# Flow 2: Normal tracking question triggers WISMO
# ---------------------------------------------------------------------------

class TestTrackingQuestionTriggersWismo:
    def test_response_asks_for_shipment_number(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "waar is mijn pakket?", sid)

        response = data["response"].lower()
        assert "zendingnummer" in response or "shipment number" in response, (
            "Tracking question must prompt for zendingnummer/shipment number"
        )

    def test_session_awaiting_order_number_is_set(self):
        client = _make_client()
        sid = _make_session_id()

        _post(client, "waar is mijn pakket?", sid)

        session = _load_session(sid)
        assert session.get("awaiting_order_number") is True, (
            "Session must have awaiting_order_number=True after tracking question"
        )

    def test_waar_blijft_mij_zending_triggers_wismo(self):
        """Regression: 'waar blijft' and 'mij' (informal possessive) must trigger WISMO."""
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "Waar blijft mij zending?", sid)

        response = data["response"].lower()
        assert "zendingnummer" in response or "shipment number" in response, (
            "'Waar blijft mij zending?' must trigger WISMO and ask for shipment number"
        )
        session = _load_session(sid)
        assert session.get("awaiting_order_number") is True, (
            "Session must have awaiting_order_number=True after 'waar blijft mij zending?'"
        )

    def test_has_shipment_number_declaration_triggers_wismo(self):
        """Regression: 'ik heb een zendingsnummer' must trigger WISMO directly."""
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "ik heb een zendingsnummer", sid)

        response = data["response"].lower()
        assert "zendingnummer" in response or "shipment number" in response, (
            "'ik heb een zendingsnummer' must trigger WISMO and ask for the shipment number"
        )
        session = _load_session(sid)
        assert session.get("awaiting_order_number") is True, (
            "Session must have awaiting_order_number=True after 'ik heb een zendingsnummer'"
        )


# ---------------------------------------------------------------------------
# Flow 3: WISMO → "no order yet" clears state and gives delivery info
# ---------------------------------------------------------------------------

class TestWismoNoOrderYetClearsState:
    def test_response_contains_delivery_time_info(self):
        import datetime
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "inactive",
            "awaiting_shopify_order_number": True,
            "shopify_verification_timestamp": datetime.datetime.now().isoformat(),
        })

        data = _post(client, "ik heb nog geen bestelling gedaan", sid)

        response = data["response"].lower()
        # Should give delivery time guidance, not ask for an order number again
        assert "werkdagen" in response or "working days" in response or "klantenservice" in response, (
            "Response after no-order-yet must contain delivery time info"
        )
        assert "bestelnummer" not in response, (
            "Response must not ask for a bestelnummer when user hasn't ordered yet"
        )

    def test_session_awaiting_shopify_order_number_is_cleared(self):
        import datetime
        client = _make_client()
        sid = _make_session_id()
        _seed_session(sid, {
            "state": "inactive",
            "awaiting_shopify_order_number": True,
            "shopify_verification_timestamp": datetime.datetime.now().isoformat(),
        })

        _post(client, "ik heb nog geen bestelling gedaan", sid)

        session = _load_session(sid)
        assert not session.get("awaiting_shopify_order_number"), (
            "awaiting_shopify_order_number must be cleared after no-order-yet response"
        )


# ---------------------------------------------------------------------------
# Flow 4: "no shipment number" response when waiting for tracking number
# ---------------------------------------------------------------------------

class TestNoShipmentNumberPath:
    def test_no_shipment_number_triggers_helpful_response(self):
        """When user says they don't have the shipment number, bot should help
        them find it (not loop asking for it again)."""
        client = _make_client()
        sid = _make_session_id()
        import datetime
        _seed_session(sid, {
            "state": "inactive",
            "awaiting_order_number": True,
            "tracking_timestamp": datetime.datetime.now().isoformat(),
        })

        data = _post(client, "ik heb geen zendingnummer", sid)

        response = data["response"].lower()
        assert "verzendbevestiging" in response or "klantenservice" in response or "confirmation" in response, (
            "Bot must tell the user where to find their shipment number, not ask again"
        )

    def test_no_shipment_number_clears_tracking_state(self):
        client = _make_client()
        sid = _make_session_id()
        import datetime
        _seed_session(sid, {
            "state": "inactive",
            "awaiting_order_number": True,
            "tracking_timestamp": datetime.datetime.now().isoformat(),
        })

        _post(client, "ik heb geen zendingnummer", sid)

        session = _load_session(sid)
        assert not session.get("awaiting_order_number"), (
            "awaiting_order_number must be cleared after no-shipment-number response"
        )


# ---------------------------------------------------------------------------
# Flow 5: Escalation flow — name → email
# ---------------------------------------------------------------------------

class TestEscalationFlow:
    def test_escalation_request_sets_awaiting_name(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "ik wil een medewerker spreken", sid)

        response = data["response"].lower()
        assert "naam" in response or "name" in response, (
            "Escalation request must ask for the user's name"
        )
        session = _load_session(sid)
        assert session.get("state") == "awaiting_name", (
            "State must be 'awaiting_name' after escalation request"
        )

    def test_providing_name_transitions_to_awaiting_email(self):
        client = _make_client()
        sid = _make_session_id()

        # First message: trigger escalation
        _post(client, "ik wil een medewerker spreken", sid)

        # Second message: provide name
        data = _post(client, "Jan de Vries", sid)

        response = data["response"].lower()
        assert "e-mail" in response or "email" in response, (
            "After providing name, bot must ask for email address"
        )
        session = _load_session(sid)
        assert session.get("state") == "awaiting_email", (
            "State must be 'awaiting_email' after name is provided"
        )


# ---------------------------------------------------------------------------
# Flow 6: Closing message doesn't loop
# ---------------------------------------------------------------------------

class TestClosingMessage:
    def test_thanks_returns_polite_signoff(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "dankjewel", sid)

        response = data["response"].lower()
        # Must be a polite sign-off, not another question or error
        assert any(kw in response for kw in ("graag", "succes", "hulp", "welcome", "pleasure")), (
            "Closing message must produce a polite sign-off"
        )

    def test_thanks_does_not_ask_question(self):
        client = _make_client()
        sid = _make_session_id()

        data = _post(client, "dankjewel", sid)

        response = data["response"]
        assert "bestelnummer" not in response.lower(), (
            "Closing message must not trigger WISMO order-number prompt"
        )
        assert response.strip() != "", (
            "Response must not be empty"
        )
