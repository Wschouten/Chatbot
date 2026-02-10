"""Zendesk API client for ticket creation."""
import base64
import logging
import os
from typing import Any, Optional

import requests

from brand_config import get_brand_config

# Configure logging
logger = logging.getLogger(__name__)

# Request timeout in seconds (connect timeout, read timeout)
REQUEST_TIMEOUT = (5, 30)


class ZendeskClient:
    """Client for interacting with Zendesk API."""

    def __init__(self) -> None:
        """Initialize Zendesk client with credentials from environment."""
        self.subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
        self.email = os.environ.get("ZENDESK_EMAIL")
        self.token = os.environ.get("ZENDESK_API_TOKEN")

    def is_configured(self) -> bool:
        """Check if Zendesk credentials are configured."""
        return bool(self.subdomain and self.email and self.token)

    @property
    def use_mock(self) -> bool:
        """Check if running in mock mode (credentials missing)."""
        return not self.is_configured()

    def create_ticket(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> Optional[dict[str, Any]]:
        """Create a support ticket in Zendesk.

        Args:
            name: Customer name
            requester_email: Customer email address
            question: The original question/issue
            session_history: Optional chat history for context

        Returns:
            Zendesk API response dict or None on failure
        """
        if not self.is_configured():
            logger.info("ZENDESK MOCK: Ticket creation requested but credentials missing.")
            logger.info("  > Requester: %s (%s)", name, requester_email)
            logger.info("  > Question: %s", question)
            return {"ticket": {"id": "MOCK-123", "subject": "Mock Ticket"}}

        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"

        # Basic Auth: email/token:api_token
        auth_string = f"{self.email}/token:{self.token}"
        auth_header = "Basic " + base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header
        }

        # Build Description with full conversation history
        brand = get_brand_config()
        welcome_msg = f"{brand.welcome_message_nl} (I also speak English!)"

        description = f"Original Question: {question}\n\n"
        description += "=" * 50 + "\n"
        description += "COMPLETE CONVERSATION HISTORY\n"
        description += "=" * 50 + "\n\n"

        # Include the welcome message that starts every conversation
        description += f"Bot: {welcome_msg}\n\n"

        if session_history:
            for msg in session_history:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                prefix = "Customer" if role == 'user' else "Bot"
                description += f"{prefix}: {content}\n\n"
        else:
            description += "(No further conversation history)\n"

        payload = {
            "ticket": {
                "subject": f"Chatbot Query from {name}",
                "comment": {"body": description},
                "requester": {"name": name, "email": requester_email}
            }
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout:
            logger.error("Zendesk API Error: Request timed out")
            return None
        except requests.RequestException as e:
            logger.error("Zendesk API Error: %s", e)
            if hasattr(e, 'response') and e.response is not None:
                logger.error("Response: %s", e.response.text)
            return None
