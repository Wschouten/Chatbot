"""SMTP Email client for escalation emails."""
import logging
import os
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional

from brand_config import get_brand_config

# Configure logging
logger = logging.getLogger(__name__)

# SMTP timeout in seconds
SMTP_TIMEOUT = 30


class EmailClient:
    """Client for sending escalation emails via SMTP (Outlook/Office 365)."""

    def __init__(self) -> None:
        """Initialize email client with SMTP credentials from environment."""
        self.smtp_server = os.environ.get("SMTP_SERVER", "smtp.office365.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.from_email = os.environ.get("SMTP_FROM_EMAIL")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.to_email = os.environ.get("SMTP_TO_EMAIL")

    @property
    def use_mock(self) -> bool:
        """Check if running in mock mode (credentials missing)."""
        return not self.is_configured()

    def is_configured(self) -> bool:
        """Check if SMTP credentials are configured."""
        return bool(self.from_email and self.password and self.to_email)

    def send_email(
        self,
        name: str,
        requester_email: str,
        question: str,
        session_history: Optional[list[dict[str, str]]] = None
    ) -> Optional[dict[str, Any]]:
        """Send an escalation email via SMTP.

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

        # Construct MIME message
        message = MIMEMultipart()
        message["From"] = self.from_email
        message["To"] = self.to_email
        message["Subject"] = subject
        message["Reply-To"] = requester_email
        message.attach(MIMEText(body, "plain", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=SMTP_TIMEOUT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.from_email, self.password)
                server.send_message(message)

            logger.info("Escalation email sent successfully for: %s", name)
            return {"ticket": {"id": "EMAIL-SENT", "subject": subject}}

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP Authentication Error: Invalid credentials for SMTP account")
            return None
        except smtplib.SMTPConnectError as e:
            logger.error("SMTP Connection Error: Could not connect to %s:%s - %s",
                         self.smtp_server, self.smtp_port, e)
            return None
        except socket.timeout:
            logger.error("SMTP Error: Connection timed out to %s:%s",
                         self.smtp_server, self.smtp_port)
            return None
        except smtplib.SMTPException as e:
            logger.error("SMTP Error: %s", e)
            return None
        except OSError as e:
            logger.error("Network Error sending email: %s", e)
            return None
