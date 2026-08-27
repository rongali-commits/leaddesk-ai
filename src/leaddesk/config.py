from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DEFAULTS = Path(__file__).resolve().parent / "defaults"


def _path_from_env(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else Path.cwd() / value


def _data_path_from_env(name: str, default: str, packaged_name: str) -> Path:
    value = Path(os.getenv(name, default))
    if value.is_absolute():
        return value
    candidates = (Path.cwd() / value, PROJECT_ROOT / value, PACKAGE_DEFAULTS / packaged_name)
    return next((candidate for candidate in candidates if candidate.exists()), candidates[0])


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    business_file: Path
    knowledge_file: Path
    admin_token: str
    app_env: str = "development"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    lead_webhook_url: str | None = None
    cors_origins: tuple[str, ...] = ()
    store_conversations: bool = True
    rate_limit_per_minute: int = 20

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(Path.cwd() / ".env")
        if PROJECT_ROOT != Path.cwd():
            load_dotenv(PROJECT_ROOT / ".env", override=False)
        origins = tuple(
            item.strip() for item in os.getenv("CORS_ORIGINS", "").split(",") if item.strip()
        )
        settings = cls(
            database_path=_path_from_env("DATABASE_PATH", "runtime/leaddesk.db"),
            business_file=_data_path_from_env(
                "BUSINESS_FILE", "data/business.json", "business.json"
            ),
            knowledge_file=_data_path_from_env(
                "KNOWLEDGE_FILE", "data/knowledge_base.json", "knowledge_base.json"
            ),
            admin_token=os.getenv("ADMIN_TOKEN", "change-me-before-deploying"),
            app_env=os.getenv("APP_ENV", "development").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            lead_webhook_url=os.getenv("LEAD_WEBHOOK_URL") or None,
            cors_origins=origins,
            store_conversations=_as_bool(os.getenv("STORE_CONVERSATIONS"), True),
            rate_limit_per_minute=max(3, int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production")
        weak_tokens = {"", "change-me-before-deploying", "replace-with-a-long-random-secret"}
        if self.app_env == "production" and (
            self.admin_token in weak_tokens or len(self.admin_token) < 24
        ):
            raise ValueError(
                "Production requires an ADMIN_TOKEN containing at least 24 characters"
            )

    def load_business(self) -> dict[str, Any]:
        return json.loads(self.business_file.read_text(encoding="utf-8"))

    def load_seed_articles(self) -> list[dict[str, Any]]:
        return json.loads(self.knowledge_file.read_text(encoding="utf-8"))
