"""Shared pytest configuration for the backend test suite.

The integration clients (shipping / stock / email / zendesk) now only fall back
to fabricated mock responses when mocks are explicitly allowed (USE_MOCKS /
FLASK_DEBUG). The suite was written against the old "auto-mock when no key"
behaviour, so we enable mocks for the whole suite here. Tests that assert the
production behaviour (honest error / None instead of a fake success) override
this with `patch.dict(os.environ, {"USE_MOCKS": "", "FLASK_DEBUG": ""})`.
"""
import glob
import os

import pytest

# Enable mock integrations for the test run (no real API keys required).
os.environ["USE_MOCKS"] = "true"

# Skip import-time KB ingestion (bills the OpenAI API) and the data-retention
# cleanup (deletes files) when `import app` runs during collection.
os.environ["TESTING"] = "1"

# Pin the working directory to backend/ so the suite's relative data/ paths
# (data/sessions, data/logs) resolve identically no matter where pytest is
# invoked from (repo root, backend/, an IDE, CI, ...).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_BACKEND_DIR)


def _purge_test_artifacts():
    """Delete chat logs + session files the suite writes to disk, so they don't
    linger and show up as fake conversations in the admin portal."""
    for pattern in ("data/logs/chat_test_*.json", "data/sessions/test_*.json"):
        for path in glob.glob(pattern):
            try:
                os.remove(path)
            except OSError:
                pass


@pytest.fixture(scope="session", autouse=True)
def _clean_test_artifacts():
    _purge_test_artifacts()  # clear stragglers left by an earlier/crashed run
    yield
    _purge_test_artifacts()  # clean up what this run created
