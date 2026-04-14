from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from util.log import _log
from util.sqlite import SqliteClient


class LifeSqliteStore:
    """Life module dedicated sqlite persistence interface."""

    def __init__(self, db_path: str | Path = "data/life.sqlite"):
        self.client = SqliteClient(db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.client.execute(
            """
            CREATE TABLE IF NOT EXISTS life_profile (
                profile_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def save_profile(self, profile_id: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        self.client.execute(
            """
            INSERT INTO life_profile(profile_id, payload, updated_at)
            VALUES(?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id)
            DO UPDATE SET payload = excluded.payload, updated_at = CURRENT_TIMESTAMP
            """,
            (profile_id, payload),
        )
        _log.INFO(f"[Life]保存存档: {profile_id}")

    def load_profile(self, profile_id: str) -> dict[str, Any] | None:
        row = self.client.query_one(
            "SELECT payload FROM life_profile WHERE profile_id = ?",
            (profile_id,),
        )

        if not row:
            return None

        try:
            return json.loads(row[0])
        except Exception as exc:
            _log.ERROR(f"[Life]读取存档失败 {profile_id}: {exc}")
            return None
