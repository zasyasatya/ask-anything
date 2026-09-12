import os
import sys
import tempfile

os.environ["ASK_PROVIDER"] = "mock"
os.environ["ASK_DB_PATH"] = os.path.join(
    tempfile.mkdtemp(prefix="askanything_test_"), "test.db"
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _forget_payload_memory():
    """Providers remember which payload rung a server accepted; tests must not."""
    from app.providers import OpenAIProtocolProvider

    OpenAIProtocolProvider.reset_payload_memory()
    yield
    OpenAIProtocolProvider.reset_payload_memory()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
