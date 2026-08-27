from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self, seed_articles: list[dict[str, Any]]) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS leads (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    postal_code TEXT NOT NULL DEFAULT '',
                    service TEXT NOT NULL,
                    property_size TEXT NOT NULL DEFAULT '',
                    preferred_date TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    consent INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    source_page TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    answer_mode TEXT NOT NULL,
                    matched_article_ids TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge_articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    keywords TEXT NOT NULL,
                    content TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_conversations_created_at
                    ON conversations(created_at DESC);
                """
            )
            count = connection.execute("SELECT COUNT(*) FROM knowledge_articles").fetchone()[0]
            if count == 0:
                for article in seed_articles:
                    connection.execute(
                        """
                        INSERT INTO knowledge_articles
                            (id, title, category, url, keywords, content, enabled, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                        """,
                        (
                            article["id"],
                            article["title"],
                            article.get("category", "General"),
                            article.get("url", ""),
                            json.dumps(article.get("keywords", [])),
                            article["content"],
                            now_iso(),
                        ),
                    )

    def ping(self) -> bool:
        try:
            with self.connect() as connection:
                return connection.execute("SELECT 1").fetchone()[0] == 1
        except sqlite3.Error:
            return False

    def list_articles(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM knowledge_articles"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY category, title"
        with self.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [self._article_from_row(row) for row in rows]

    def upsert_article(self, article: dict[str, Any]) -> dict[str, Any]:
        article_id = article.get("id") or uuid.uuid4().hex[:12]
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_articles
                    (id, title, category, url, keywords, content, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    category=excluded.category,
                    url=excluded.url,
                    keywords=excluded.keywords,
                    content=excluded.content,
                    enabled=excluded.enabled,
                    updated_at=excluded.updated_at
                """,
                (
                    article_id,
                    article["title"],
                    article.get("category", "General"),
                    article.get("url", ""),
                    json.dumps(article.get("keywords", [])),
                    article["content"],
                    int(article.get("enabled", True)),
                    now_iso(),
                ),
            )
        return next(item for item in self.list_articles() if item["id"] == article_id)

    def delete_article(self, article_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM knowledge_articles WHERE id = ?", (article_id,)
            )
            return cursor.rowcount > 0

    def create_lead(self, lead: dict[str, Any], score: int, status: str) -> dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "created_at": now_iso(),
            **lead,
            "score": score,
            "status": status,
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO leads
                    (id, created_at, name, email, phone, postal_code, service, property_size,
                     preferred_date, message, consent, score, status, source_page)
                VALUES (:id, :created_at, :name, :email, :phone, :postal_code, :service,
                        :property_size, :preferred_date, :message, :consent, :score, :status,
                        :source_page)
                """,
                {**record, "consent": int(record["consent"])},
            )
        record["consent"] = bool(record["consent"])
        return record

    def list_leads(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._dict_with_bool(row, "consent") for row in rows]

    def update_lead_status(self, lead_id: str, status: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE leads SET status = ? WHERE id = ?", (status, lead_id)
            )
            return cursor.rowcount > 0

    def save_conversation(self, conversation: dict[str, Any]) -> None:
        record = {
            "id": str(uuid.uuid4()),
            "created_at": now_iso(),
            **conversation,
            "matched_article_ids": json.dumps(conversation["matched_article_ids"]),
        }
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations
                    (id, created_at, session_id, question, answer, intent, answer_mode,
                     matched_article_ids)
                VALUES (:id, :created_at, :session_id, :question, :answer, :intent,
                        :answer_mode, :matched_article_ids)
                """,
                record,
            )

    def list_conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        records = [dict(row) for row in rows]
        for record in records:
            record["matched_article_ids"] = json.loads(record["matched_article_ids"])
        return records

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            lead_count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            qualified = connection.execute(
                "SELECT COUNT(*) FROM leads WHERE status = 'qualified'"
            ).fetchone()[0]
            conversations = connection.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            unanswered = connection.execute(
                """
                SELECT COUNT(*) FROM conversations
                WHERE matched_article_ids = '[]'
                """
            ).fetchone()[0]
        conversion = round((lead_count / conversations) * 100, 1) if conversations else 0.0
        return {
            "leads": lead_count,
            "qualified_leads": qualified,
            "conversations": conversations,
            "unanswered_questions": unanswered,
            "conversion_rate": conversion,
        }

    @staticmethod
    def _article_from_row(row: sqlite3.Row) -> dict[str, Any]:
        article = dict(row)
        article["keywords"] = json.loads(article["keywords"])
        article["enabled"] = bool(article["enabled"])
        return article

    @staticmethod
    def _dict_with_bool(row: sqlite3.Row, field: str) -> dict[str, Any]:
        record = dict(row)
        record[field] = bool(record[field])
        return record
