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
        _log.DEBUG(f"[Life][Store]初始化 SQLite 存档: {self.client.db_path}")
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
        _log.DEBUG(f"[Life][Store]保存存档: {profile_id} bytes={len(payload.encode('utf-8'))}")

    def load_profile(self, profile_id: str) -> dict[str, Any] | None:
        row = self.client.query_one(
            "SELECT payload FROM life_profile WHERE profile_id = ?",
            (profile_id,),
        )

        if not row:
            _log.DEBUG(f"[Life][Store]存档不存在: {profile_id}")
            return None

        try:
            payload = json.loads(row[0])
            _log.DEBUG(f"[Life][Store]读取存档成功: {profile_id}")
            return payload
        except Exception as exc:
            _log.EXCEPTION(f"[Life][Store]读取存档失败 {profile_id}", exc)
            return None
