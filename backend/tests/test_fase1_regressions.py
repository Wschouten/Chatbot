"""Regression tests for the Fase 1 audit fixes (AUDIT-2026-07-11).

Covers:
- Mock gating: integrations no longer fabricate success in production.
- Null session_id no longer crashes the chat handler.
- Belgian postcodes are accepted (no more infinite "invalid postcode" loop).
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Env that simulates production: no keys, mocks disabled.
_PROD_ENV = {"USE_MOCKS": "", "FLASK_DEBUG": ""}


class TestMockGatingProduction:
    """Missing integration keys must yield honest failures in production, not fakes."""

    def test_shipping_uses_mock_only_when_allowed(self):
        import shipping_api as _sa

        with patch.dict(os.environ, {**_PROD_ENV, "SHIPPING_API_KEY": ""}):
            _sa._shipping_client = None
            client = _sa.ShippingAPIClient()
            _sa._shipping_client = None
        assert client.use_mock is False, "No key + mocks disabled must NOT enable mock shipping"

        with patch.dict(os.environ, {"USE_MOCKS": "true", "SHIPPING_API_KEY": ""}):
            _sa._shipping_client = None
            client = _sa.ShippingAPIClient()
            _sa._shipping_client = None
        assert client.use_mock is True, "No key + USE_MOCKS=true must enable mock shipping (dev)"

    def test_zendesk_no_mock_ticket_in_production(self):
        from zendesk_client import ZendeskClient

        with patch.dict(os.environ, {**_PROD_ENV,
                                     "ZENDESK_SUBDOMAIN": "", "ZENDESK_EMAIL": "",
                                     "ZENDESK_API_TOKEN": ""}):
            client = ZendeskClient()
            result = client.create_ticket("Test User", "test@example.com", "Test question")
        assert result is None, "Missing Zendesk creds in production must return None, not a MOCK ticket"

    def test_email_no_mock_send_in_production(self):
        from email_client import EmailClient

        with patch.dict(os.environ, {**_PROD_ENV,
                                     "MAILERSEND_API_KEY": "", "SMTP_FROM_EMAIL": "",
                                     "SMTP_TO_EMAIL": ""}):
            client = EmailClient()
            result = client.send_email_async("Test User", "test@example.com", "Test question")
        assert result is None, "Missing MailerSend creds in production must return None, not a queued fake"


class TestSessionIdNullCrash:
    """A first message posted with session_id: null must not crash the handler."""

    def test_null_session_id_does_not_crash(self):
        import app as flask_app

        flask_app.app.config["TESTING"] = True
        flask_app.app.config["RATELIMIT_ENABLED"] = False
        client = flask_app.app.test_client()

        # Empty message returns the "type your question" prompt BEFORE any RAG call.
        # Pre-fix, session_id: null crashed in sanitize_session_id(None) and fell
        # through to the generic error fallback instead.
        resp = client.post(
            "/api/chat",
            json={"message": "", "session_id": None},
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()["response"].lower()
        assert "typ" in body, f"Expected the empty-message prompt, got: {body!r}"


class TestBelgianPostcode:
    """POSTCODE_RE must accept Belgian (4-digit) as well as Dutch postcodes."""

    def test_postcode_regex_accepts_nl_and_be(self):
        import app as flask_app

        assert flask_app.POSTCODE_RE.search("1234 AB"), "Dutch postcode must still match"
        assert flask_app.POSTCODE_RE.search("1234AB"), "Dutch postcode without space must match"
        assert flask_app.POSTCODE_RE.search("1000"), "Belgian 4-digit postcode must match"
        assert flask_app.POSTCODE_RE.search("9000"), "Belgian 4-digit postcode must match"
