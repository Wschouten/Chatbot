"""MailerSend email client for escalation emails."""
import logging
import os
from typing import Any, Optional

import requests as http_requests

from brand_config import get_brand_config
from mocks import mocks_allowed as _mocks_allowed

# Configure logging
logger = logging.getLogger(__name__)

# MailerSend API endpoint
MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"

# HTTP timeout in seconds
HTTP_TIMEOUT = 15


def format_transcript(session_history: Optional[list[dict[str, str]]]) -> str:
    """The conversation as plain text, for the escalation email and Zendesk ticket.

    No made-up opening line: both used to start with "Bot: <BRAND_WELCOME_NL>", a
    greeting the customer never saw (the widget shows its own).
    """
    text = "=" * 50 + "\nCOMPLETE CONVERSATION HISTORY\n" + "=" * 50 + "\n\n"
    if not session_history:
        return text + "(No further conversation history)\n"
    for msg in session_history:
        prefix = "Customer" if msg.get('role') == 'user' else "Bot"
        text += f"{prefix}: {msg.get('content', '')}\n\n"
    return text


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
        """Mock mode: credentials missing *and* mocks allowed — same rule as shipping."""
        return not self.is_configured() and _mocks_allowed()

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
            logger.error("MailerSend credentials missing - escalation email NOT sent")
            return None

        # Build email body with full conversation history
        brand = get_brand_config()

        body = f"Beste {brand.name},\n\n"
        body += f"Stuur een email naar het volgende mailadres: {requester_email}\n\n"
        body += f"Naam: {name}\n"
        body += f"Vraag: {question or '(geen vraag vastgelegd)'}\n\n"
        body += format_transcript(session_history)

        # Send via MailerSend API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": {
                "email": self.from_email,
                "name": "Boomschors.nl Chatbot",
            },
            "to": [
                {
                    "email": self.to_email,
                    "name": "Boomschors.nl Support",
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
            logger.info("Escalation email sent successfully")
            return {"ticket": {"id": "EMAIL-SENT", "subject": subject}}
        except http_requests.RequestException as e:
            logger.error("MailerSend API error: %s", e)
            return None
