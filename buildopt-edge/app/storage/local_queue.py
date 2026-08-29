"""Durable SQLite store-and-forward queue."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


class LocalQueue:
    def __init__(self, db_path: str, max_rows: int = 50_000) -> None:
        self.db_path = Path(db_path)
        self.max_rows = max_rows
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            create table if not exists telemetry_queue (
                id integer primary key autoincrement,
                dedupe_key text not null,
                payload text not null,
                created_at text not null,
                attempts integer default 0
            )
            """
        )
        self._conn.execute(
            "create unique index if not exists idx_telemetry_dedupe on telemetry_queue(dedupe_key)"
        )
        self._conn.commit()

    def enqueue(self, dedupe_key: str, payload: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._conn.execute(
                "insert into telemetry_queue (dedupe_key, payload, created_at) values (?, ?, ?)",
                (dedupe_key, json.dumps(payload), now),
            )
        except sqlite3.IntegrityError:
            self._conn.execute(
                "update telemetry_queue set payload=?, created_at=? where dedupe_key=?",
                (json.dumps(payload), now, dedupe_key),
            )
        self._conn.commit()
        self._trim()

    def dequeue_batch(self, limit: int = 100) -> List[Tuple[int, Dict[str, Any], int]]:
        rows = self._conn.execute(
            "select id, payload, attempts from telemetry_queue order by id asc limit ?",
            (limit,),
        ).fetchall()
        return [(row[0], json.loads(row[1]), row[2]) for row in rows]

    def ack(self, row_id: int) -> None:
        self._conn.execute("delete from telemetry_queue where id=?", (row_id,))
        self._conn.commit()

    def bump_attempts(self, row_id: int) -> None:
        self._conn.execute("update telemetry_queue set attempts = attempts + 1 where id=?", (row_id,))
        self._conn.commit()

    def depth(self) -> int:
        row = self._conn.execute("select count(*) from telemetry_queue").fetchone()
        return int(row[0]) if row else 0

    def oldest_age_seconds(self) -> int | None:
        row = self._conn.execute(
            "select created_at from telemetry_queue order by id asc limit 1"
        ).fetchone()
        if not row:
            return None
        created = datetime.fromisoformat(row[0])
        return int((datetime.now(timezone.utc) - created).total_seconds())

    def _trim(self) -> None:
        count = self.depth()
        if count <= self.max_rows:
            return
        overflow = count - self.max_rows
        self._conn.execute(
            "delete from telemetry_queue where id in (select id from telemetry_queue order by id asc limit ?)",
            (overflow,),
        )
        self._conn.commit()
