"""Tests for input validation functions."""
import pytest
import sys
import os

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
        """Test shipping status with valid order ID."""
        from shipping_api import get_shipment_status

        result = get_shipment_status("12345")
        assert "12345" in result
        assert "Status" in result

    def test_empty_order_id(self):
        """Test shipping status with empty order ID."""
        from shipping_api import get_shipment_status

        result = get_shipment_status("")
        assert "valid Order ID" in result


class TestZendeskClient:
    """Tests for Zendesk client."""

    def test_mock_ticket_creation(self):
        """Test ticket creation without credentials returns mock."""
        from zendesk_client import ZendeskClient

        # Without env vars, should return mock
        client = ZendeskClient()

        # Clear any existing env vars for this test
        original_subdomain = os.environ.pop("ZENDESK_SUBDOMAIN", None)
        original_email = os.environ.pop("ZENDESK_EMAIL", None)
        original_token = os.environ.pop("ZENDESK_API_TOKEN", None)

        try:
            client = ZendeskClient()
            result = client.create_ticket(
                name="Test User",
                requester_email="test@example.com",
                question="Test question"
            )

            assert result is not None
            assert result["ticket"]["id"] == "MOCK-123"
        finally:
            # Restore env vars
            if original_subdomain:
                os.environ["ZENDESK_SUBDOMAIN"] = original_subdomain
            if original_email:
                os.environ["ZENDESK_EMAIL"] = original_email
            if original_token:
                os.environ["ZENDESK_API_TOKEN"] = original_token

    def test_is_configured_false(self):
        """Test is_configured returns False without credentials."""
        from zendesk_client import ZendeskClient

        # Save and clear env vars
        original_subdomain = os.environ.pop("ZENDESK_SUBDOMAIN", None)
        original_email = os.environ.pop("ZENDESK_EMAIL", None)
        original_token = os.environ.pop("ZENDESK_API_TOKEN", None)

        try:
            client = ZendeskClient()
            assert not client.is_configured()
        finally:
            # Restore env vars
            if original_subdomain:
                os.environ["ZENDESK_SUBDOMAIN"] = original_subdomain
            if original_email:
                os.environ["ZENDESK_EMAIL"] = original_email
            if original_token:
                os.environ["ZENDESK_API_TOKEN"] = original_token
