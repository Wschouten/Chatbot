"""Microsoft Graph API email client for escalation emails."""
import logging
import os
import threading
from typing import Any, Optional

import requests as http_requests

from brand_config import get_brand_config

# Configure logging
logger = logging.getLogger(__name__)

# Graph API endpoints
TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{from_email}/sendMail"

# HTTP timeout in seconds
HTTP_TIMEOUT = 15


class EmailClient:
    """Client for sending escalation emails via Microsoft Graph API (Office 365)."""

    def __init__(self) -> None:
        """Initialize email client with Graph API credentials from environment."""
        self.tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")
        self.client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
        self.from_email = os.environ.get("SMTP_FROM_EMAIL")
        self.to_email = os.environ.get("SMTP_TO_EMAIL")

    def is_configured(self) -> bool:
        """Check if Graph API credentials are configured."""
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.from_email
            and self.to_email
        )

    def _get_access_token(self) -> Optional[str]:
        """Acquire an access token using OAuth2 client credentials flow."""
        url = TOKEN_URL.format(tenant_id=self.tenant_id)
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        try:
            resp = http_requests.post(url, data=data, timeout=HTTP_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("access_token")
        except http_requests.RequestException as e:
            logger.error("Graph API token request failed: %s", e)
            return None

    def send_email(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> Optional[dict[str, Any]]:
        """Send an escalation email via Microsoft Graph API.

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

        body = f"Customer Name: {name}\n"
        body += f"Customer Email: {requester_email}\n"
        body += f"Original Question: {question}\n\n"
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

        # Get access token
        token = self._get_access_token()
        if not token:
            logger.error("Failed to acquire Graph API access token")
            return None

        # Build Graph API sendMail payload
        mail_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "Text",
                    "content": body,
                },
                "toRecipients": [
                    {"emailAddress": {"address": self.to_email}}
                ],
                "replyTo": [
                    {"emailAddress": {"address": requester_email}}
                ],
            },
            "saveToSentItems": "false",
        }

        url = SEND_MAIL_URL.format(from_email=self.from_email)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            resp = http_requests.post(
                url, json=mail_payload, headers=headers, timeout=HTTP_TIMEOUT
            )
            resp.raise_for_status()
            logger.info("Escalation email sent successfully for: %s", name)
            return {"ticket": {"id": "EMAIL-SENT", "subject": subject}}
        except http_requests.RequestException as e:
            logger.error("Graph API sendMail failed: %s", e)
            return None

    def send_email_async(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> dict[str, Any]:
        """Queue an escalation email to be sent in a background thread.

        Returns immediately with a success result. The actual Graph API send
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
