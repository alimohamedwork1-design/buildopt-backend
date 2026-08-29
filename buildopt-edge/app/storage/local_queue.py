"""Durable SQLite store-and-forward queue with WAL, backoff, and replay metrics."""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("buildopt.edge.queue")


class LocalQueue:
    def __init__(
        self,
        db_path: str,
        max_rows: int = 50_000,
        max_attempts: int = 50,
        base_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 3600.0,
    ) -> None:
        self.db_path = Path(db_path)
        self.max_rows = max_rows
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.critical_overflow = False
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("pragma journal_mode=WAL")
        self._conn.execute("pragma synchronous=NORMAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            create table if not exists telemetry_queue (
                id integer primary key autoincrement,
                event_id text not null,
                dedupe_key text not null,
                payload text not null,
                created_at text not null,
                attempts integer default 0,
                next_retry_at text
            )
            """
        )
        self._conn.execute(
            "create unique index if not exists idx_telemetry_event on telemetry_queue(event_id)"
        )
        self._conn.execute(
            "create unique index if not exists idx_telemetry_dedupe on telemetry_queue(dedupe_key)"
        )
        self._conn.commit()

    def enqueue(self, event_id: str, dedupe_key: str, payload: Dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        payload = dict(payload)
        payload["event_id"] = event_id
        try:
            self._conn.execute(
                """
                insert into telemetry_queue (event_id, dedupe_key, payload, created_at, attempts, next_retry_at)
                values (?, ?, ?, ?, 0, ?)
                """,
                (event_id, dedupe_key, json.dumps(payload), now_iso, now_iso),
            )
        except sqlite3.IntegrityError:
            self._conn.execute(
                """
                update telemetry_queue set payload=?, created_at=?, next_retry_at=?
                where event_id=? or dedupe_key=?
                """,
                (json.dumps(payload), now_iso, now_iso, event_id, dedupe_key),
            )
        self._conn.commit()
        self._trim()

    def dequeue_batch(self, limit: int = 100) -> List[Tuple[int, Dict[str, Any], int]]:
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = self._conn.execute(
            """
            select id, payload, attempts from telemetry_queue
            where next_retry_at is null or next_retry_at <= ?
            order by id asc limit ?
            """,
            (now_iso, limit),
        ).fetchall()
        return [(row[0], json.loads(row[1]), row[2]) for row in rows]

    def ack(self, row_id: int) -> None:
        self._conn.execute("delete from telemetry_queue where id=?", (row_id,))
        self._conn.commit()

    def schedule_retry(self, row_id: int, attempts: int) -> None:
        delay = min(
            self.max_backoff_seconds,
            self.base_backoff_seconds * math.pow(2, min(attempts, 10)),
        )
        next_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        self._conn.execute(
            "update telemetry_queue set attempts=?, next_retry_at=? where id=?",
            (attempts + 1, next_at.isoformat(), row_id),
        )
        self._conn.commit()

    def bump_attempts(self, row_id: int) -> int:
        row = self._conn.execute(
            "select attempts from telemetry_queue where id=?", (row_id,)
        ).fetchone()
        attempts = int(row[0]) if row else 0
        self.schedule_retry(row_id, attempts)
        return attempts + 1

    def depth(self) -> int:
        row = self._conn.execute("select count(*) from telemetry_queue").fetchone()
        return int(row[0]) if row else 0

    def oldest_age_seconds(self) -> Optional[int]:
        row = self._conn.execute(
            "select created_at from telemetry_queue order by id asc limit 1"
        ).fetchone()
        if not row:
            return None
        created = datetime.fromisoformat(row[0])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return int((datetime.now(timezone.utc) - created).total_seconds())

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

    def _trim(self) -> None:
        count = self.depth()
        if count <= self.max_rows:
            return
        overflow = count - self.max_rows
        self.critical_overflow = True
        logger.critical(
            "Queue overflow — dropping %s oldest unacknowledged events (policy: drop_oldest_with_critical_event)",
            overflow,
        )
        self._conn.execute(
            "delete from telemetry_queue where id in (select id from telemetry_queue order by id asc limit ?)",
            (overflow,),
        )
        self._conn.commit()

    def metrics(self) -> Dict[str, Any]:
        return {
            "queue_depth": self.depth(),
            "oldest_queued_event_seconds": self.oldest_age_seconds(),
            "critical_overflow": self.critical_overflow,
        }
