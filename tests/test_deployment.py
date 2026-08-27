from pathlib import Path

import pytest

from leaddesk.config import PROJECT_ROOT, Settings


def production_settings(tmp_path: Path, token: str) -> Settings:
    return Settings(
        database_path=tmp_path / "production.db",
        business_file=PROJECT_ROOT / "data" / "business.json",
        knowledge_file=PROJECT_ROOT / "data" / "knowledge_base.json",
        admin_token=token,
        app_env="production",
    )


def test_production_rejects_weak_admin_token(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 24 characters"):
        production_settings(tmp_path, "too-short").validate()


def test_production_accepts_strong_admin_token(tmp_path: Path) -> None:
    production_settings(tmp_path, "a-strong-production-token-123456").validate()


def test_deployment_assets_use_dynamic_port_and_exclude_secrets() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")
    homepage = (PROJECT_ROOT / "src/leaddesk/static/index.html").read_text(encoding="utf-8")
    widget = (PROJECT_ROOT / "src/leaddesk/static/widget.html").read_text(encoding="utf-8")

    assert "${PORT:-8000}" in dockerfile
    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert homepage.count("data-open-quote") == 4
    assert "leaddesk:show-lead" in homepage
    assert "leaddesk:show-lead" in widget

