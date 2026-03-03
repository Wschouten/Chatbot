"""Exact 200 order verification client.

Connects directly to the Exact 200 database via ODBC/pyodbc to verify
that a given combination of order date and email address exists in the
order records before the chatbot reveals any shipment information.

Configuration (environment variables):
    EXACT200_DSN          ODBC DSN name or full connection string
    EXACT200_TABLE        Table name for orders (default: Verkooporders)
    EXACT200_DATE_FIELD   Column name for order date (default: Datum)
    EXACT200_EMAIL_FIELD  Column name for customer email (default: Email)

If EXACT200_DSN is not set the client runs in MOCK MODE: every call to
verify_order() returns True and a warning is logged. This allows the
chatbot to run and be tested locally without a live Exact 200 connection.
"""

import logging
import os

logger = logging.getLogger(__name__)

_DSN = os.environ.get('EXACT200_DSN', '').strip()
_TABLE = os.environ.get('EXACT200_TABLE', 'Verkooporders').strip()
_DATE_FIELD = os.environ.get('EXACT200_DATE_FIELD', 'Datum').strip()
_EMAIL_FIELD = os.environ.get('EXACT200_EMAIL_FIELD', 'Email').strip()

MOCK_MODE = not bool(_DSN)

if MOCK_MODE:
    logger.warning(
        "Exact 200 client: EXACT200_DSN is not configured — running in MOCK MODE. "
        "All order verifications will return True. Set EXACT200_DSN for production."
    )


def verify_order(order_date: str, email: str) -> bool:
    """Return True if an order matching order_date and email exists in Exact 200.

    Args:
        order_date: Normalised date string in YYYY-MM-DD format.
        email:      Customer email address (case-insensitive comparison).

    Returns:
        True  – matching order found (or mock mode is active).
        False – no match found, or a database error occurred.
    """
    if MOCK_MODE:
        logger.info("Exact 200 MOCK verify_order(%r, %r) -> True", order_date, email)
        return True

    try:
        import pyodbc  # noqa: PLC0415 (deferred import so pyodbc is optional in dev)
    except ImportError:
        logger.error(
            "pyodbc is not installed. Install it with: pip install pyodbc. "
            "Cannot connect to Exact 200 — order verification denied."
        )
        return False

    try:
        conn = pyodbc.connect(_DSN, timeout=5)
        cursor = conn.cursor()
        # Parameterised query — safe against SQL injection
        query = (
            f"SELECT TOP 1 1 FROM [{_TABLE}] "  # noqa: S608
            f"WHERE [{_DATE_FIELD}] = ? AND LOWER([{_EMAIL_FIELD}]) = LOWER(?)"
        )
        cursor.execute(query, order_date, email.strip())
        row = cursor.fetchone()
        conn.close()
        found = row is not None
        logger.info("Exact 200 verify_order(%r, %r) -> %s", order_date, email, found)
        return found
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Exact 200 database error in verify_order: %s", exc)
        # Fail closed on database errors — do not grant access
        return False
