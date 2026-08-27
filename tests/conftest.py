from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leaddesk.app import create_app
from leaddesk.config import PROJECT_ROOT, Settings


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "test.db",
        business_file=PROJECT_ROOT / "data" / "business.json",
        knowledge_file=PROJECT_ROOT / "data" / "knowledge_base.json",
        admin_token="test-admin-token",
        openai_api_key=None,
        store_conversations=True,
        rate_limit_per_minute=50,
    )
    return TestClient(create_app(settings))


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "test-admin-token"}

