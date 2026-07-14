"""Shared pytest configuration for the backend test suite.

The integration clients (shipping / stock / email / zendesk) now only fall back
to fabricated mock responses when mocks are explicitly allowed (USE_MOCKS /
FLASK_DEBUG). The suite was written against the old "auto-mock when no key"
behaviour, so we enable mocks for the whole suite here. Tests that assert the
production behaviour (honest error / None instead of a fake success) override
this with `patch.dict(os.environ, {"USE_MOCKS": "", "FLASK_DEBUG": ""})`.
"""
import os

# Enable mock integrations for the test run (no real API keys required).
os.environ["USE_MOCKS"] = "true"
