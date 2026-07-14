"""MailerSend email client for escalation emails."""
import logging
import os
import threading
from typing import Any, Optional

import requests as http_requests

from brand_config import get_brand_config

# Configure logging
logger = logging.getLogger(__name__)

# MailerSend API endpoint
MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"

# HTTP timeout in seconds
HTTP_TIMEOUT = 15


def _mocks_allowed() -> bool:
    """Whether a mock 'sent' result may stand in for missing MailerSend creds.

    Only in development (FLASK_DEBUG) or when explicitly opted in (USE_MOCKS).
    In production missing creds return a failure so the bot tells the customer
    honestly instead of silently dropping the lead.
    """
    truthy = ('1', 'true', 'yes')
    return (os.environ.get('USE_MOCKS', '').strip().lower() in truthy
            or os.environ.get('FLASK_DEBUG', '').strip().lower() in truthy)


class EmailClient:
    """Client for sending escalation emails via MailerSend API."""

    def __init__(self) -> None:
        """Initialize email client with MailerSend credentials from environment."""
        self.api_key = os.environ.get("MAILERSEND_API_KEY")
        self.from_email = os.environ.get("SMTP_FROM_EMAIL")
        self.to_email = os.environ.get("SMTP_TO_EMAIL")

    def is_configured(self) -> bool:
        """Check if MailerSend API key is configured."""
        return bool(self.api_key and self.from_email and self.to_email)

    @property
    def use_mock(self) -> bool:
        """Check if running in mock mode (credentials missing)."""
        return not self.is_configured()

    def send_email(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> Optional[dict[str, Any]]:
        """Send an escalation email via MailerSend API.

        Args:
            name: Customer name
            requester_email: Customer email address
            question: The original question/issue
            session_history: Optional chat history for context

        Returns:
            dict with email metadata or None on failure
        """
        subject = f"Chatbot Query from {name}"

        if not self.is_configured():
            if _mocks_allowed():
                logger.info("EMAIL MOCK: Email send requested but credentials missing (dev).")
                logger.info("  > Requester: %s (%s)", name, requester_email)
                logger.info("  > Question: %s", question)
                return {"ticket": {"id": "MOCK-EMAIL-123", "subject": subject}}
            logger.error("MailerSend credentials missing - escalation email NOT sent for: %s", name)
            return None

        # Build email body with full conversation history
        brand = get_brand_config()
        welcome_msg = f"{brand.welcome_message_nl} (I also speak English!)"

        body = f"Beste {brand.name},\n\n"
        body += f"Stuur een email naar het volgende mailadres: {requester_email}\n\n"
        body += "=" * 50 + "\n"
        body += "COMPLETE CONVERSATION HISTORY\n"
        body += "=" * 50 + "\n\n"
        body += f"Bot: {welcome_msg}\n\n"

        if session_history:
            for msg in session_history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                prefix = "Customer" if role == 'user' else "Bot"
                body += f"{prefix}: {content}\n\n"
        else:
            body += "(No further conversation history)\n"

        # Send via MailerSend API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": {
                "email": self.from_email,
                "name": "GroundCoverGroup Chatbot",
            },
            "to": [
                {
                    "email": self.to_email,
                    "name": "GroundCoverGroup Support",
                }
            ],
            "subject": subject,
            "text": body,
        }

        try:
            resp = http_requests.post(
                MAILERSEND_API_URL, json=payload, headers=headers, timeout=HTTP_TIMEOUT
            )
            resp.raise_for_status()
            logger.info("Escalation email sent successfully for: %s", name)
            return {"ticket": {"id": "EMAIL-SENT", "subject": subject}}
        except http_requests.RequestException as e:
            logger.error("MailerSend API error: %s", e)
            return None

    def send_email_async(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> Optional[dict[str, Any]]:
        """Queue an escalation email to be sent in a background thread.

        Returns a truthy result on queue, or None when credentials are missing in
        production (so the caller can tell the customer honestly instead of
        promising a follow-up that will never be sent). The actual MailerSend API
        call happens in a daemon thread so it doesn't block the HTTP response.
        Any unexpected errors in the thread are logged instead of dying silently.
        """
        if not self.is_configured() and not _mocks_allowed():
            logger.error("MailerSend credentials missing - escalation email NOT queued for: %s", name)
            return None

        def _send_with_logging() -> None:
            try:
                self.send_email(name, requester_email, question, session_history)
            except Exception:
                logger.exception("Background escalation email failed for %s", name)

        thread = threading.Thread(target=_send_with_logging, daemon=True)
        thread.start()
        subject = f"Chatbot Query from {name}"
        return {"ticket": {"id": "EMAIL-QUEUED", "subject": subject}}
