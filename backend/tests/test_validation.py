"""Tests for input validation functions."""
import pytest
import sys
import os
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEmailValidation:
    """Tests for email validation."""

    def test_valid_emails(self):
        """Test that valid emails pass validation."""
        from app import is_valid_email

        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
            "user123@example.co.uk",
            "test.email@company.org",
        ]

        for email in valid_emails:
            assert is_valid_email(email), f"Expected {email} to be valid"

    def test_invalid_emails(self):
        """Test that invalid emails fail validation."""
        from app import is_valid_email

        invalid_emails = [
            "",
            "@",
            "user@",
            "@example.com",
            "user",
            "user@.com",
            "user@example",
            "user name@example.com",
            "user@@example.com",
        ]

        for email in invalid_emails:
            assert not is_valid_email(email), f"Expected {email} to be invalid"


class TestSessionIdSanitization:
    """Tests for session ID sanitization."""

    def test_valid_session_id(self):
        """Test that valid session IDs pass through."""
        from app import sanitize_session_id

        assert sanitize_session_id("sess_123_abc") == "sess_123_abc"
        assert sanitize_session_id("session-456") == "session-456"
        assert sanitize_session_id("ABC123") == "ABC123"

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        from app import sanitize_session_id

        # Should strip out dots and slashes
        assert sanitize_session_id("../../../etc/passwd") == "etcpasswd"
        assert sanitize_session_id("..\\..\\windows") == "windows"
        assert sanitize_session_id("session/../admin") == "sessionadmin"

    def test_special_characters_removed(self):
        """Test that special characters are removed."""
        from app import sanitize_session_id

        assert sanitize_session_id("session<script>") == "sessionscript"
        assert sanitize_session_id("session;drop table") == "sessiondroptable"
        assert sanitize_session_id("session'OR'1'='1") == "sessionOR11"

    def test_length_limit(self):
        """Test that session IDs are truncated to 100 chars."""
        from app import sanitize_session_id

        long_id = "a" * 200
        result = sanitize_session_id(long_id)
        assert len(result) == 100


class TestShippingApi:
    """Tests for shipping API."""

    def test_valid_order_id(self):
        """Mock shipment lookup returns the in-transit mock response (mock mode)."""
        import shipping_api as _sa
        from shipping_api import get_shipping_client

        with patch.dict(os.environ, {'SHIPPING_API_KEY': '', 'USE_MOCKS': 'true'}):
            _sa._shipping_client = None
            result = get_shipping_client().get_shipment_status("12345")
            _sa._shipping_client = None
        assert result["success"] is True
        assert result["status"] == "in_transit"
        assert result["details"]["tracking_code"] == "12345"
        assert "onderweg" in result["details"]["status_description"].lower()

    def test_empty_order_id(self):
        """Empty tracking code returns the invalid-number error outcome."""
        import shipping_api as _sa
        from shipping_api import get_shipping_client, ShippingAPIClient
        from unittest.mock import MagicMock

        with patch.dict(os.environ, {'SHIPPING_API_KEY': 'dummy-key-for-test'}):
            _sa._shipping_client = None
            # Patch auth and SOAP so no network calls are made;
            # int("") raises ValueError before any SOAP method is invoked.
            with patch.object(ShippingAPIClient, '_get_session_id', return_value='dummy-session'), \
                 patch.object(ShippingAPIClient, '_get_soap_client', return_value=MagicMock()):
                result = get_shipping_client().get_shipment_status("")
            _sa._shipping_client = None
        assert result["success"] is False
        assert result["status"] == "invalid_number"
        assert "geldig zendingnummer" in result["error"]


class TestZendeskClient:
    """Tests for Zendesk client."""

    def test_mock_ticket_creation(self, monkeypatch):
        """Without credentials (mocks enabled), ticket creation returns a mock."""
        from zendesk_client import ZendeskClient

        monkeypatch.delenv("ZENDESK_SUBDOMAIN", raising=False)
        monkeypatch.delenv("ZENDESK_EMAIL", raising=False)
        monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)

        client = ZendeskClient()
        result = client.create_ticket(
            name="Test User",
            requester_email="test@example.com",
            question="Test question",
        )

        assert result is not None
        assert result["ticket"]["id"] == "MOCK-123"

    def test_is_configured_false(self, monkeypatch):
        """is_configured() is False without credentials."""
        from zendesk_client import ZendeskClient

        monkeypatch.delenv("ZENDESK_SUBDOMAIN", raising=False)
        monkeypatch.delenv("ZENDESK_EMAIL", raising=False)
        monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)

        client = ZendeskClient()
        assert not client.is_configured()
