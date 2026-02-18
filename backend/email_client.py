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
            logger.info("EMAIL MOCK: Email send requested but credentials missing.")
            logger.info("  > Requester: %s (%s)", name, requester_email)
            logger.info("  > Question: %s", question)
            return {"ticket": {"id": "MOCK-EMAIL-123", "subject": subject}}

        # Build email body with full conversation history
        brand = get_brand_config()
        welcome_msg = f"{brand.welcome_message_nl} (I also speak English!)"

        body = "Beste GroundCoverGroup,\n\n"
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
    ) -> dict[str, Any]:
        """Queue an escalation email to be sent in a background thread.

        Returns immediately with a success result. The actual MailerSend API call
        happens in a daemon thread so it doesn't block the HTTP response.
        """
        thread = threading.Thread(
            target=self.send_email,
            args=(name, requester_email, question, session_history),
            daemon=True,
        )
        thread.start()
        subject = f"Chatbot Query from {name}"
        return {"ticket": {"id": "EMAIL-QUEUED", "subject": subject}}
