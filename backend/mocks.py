"""The one switch that lets fabricated responses stand in for missing integrations."""
import os


def mocks_allowed() -> bool:
    """Whether fabricated mock responses may stand in for missing integrations.

    Only true in development (FLASK_DEBUG) or when explicitly opted in (USE_MOCKS).
    In production this is false, so a missing API key surfaces an honest error to
    the customer instead of a fabricated "success" (fake tracking status, fake
    stock, fake escalation ticket).
    """
    truthy = ('1', 'true', 'yes')
    return (os.getenv('USE_MOCKS', '').strip().lower() in truthy
            or os.getenv('FLASK_DEBUG', '').strip().lower() in truthy)
