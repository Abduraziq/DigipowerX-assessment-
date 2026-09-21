from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any


_DB_LOCKS: dict[Path, Lock] = {}
_DB_LOCKS_GUARD = Lock()


class UsageMeteringRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_path = self.db_path.resolve()
        with _DB_LOCKS_GUARD:
            self._lock = _DB_LOCKS.setdefault(resolved_path, Lock())
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_records (
                    request_id TEXT PRIMARY KEY,
                    customer TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    worker_id TEXT,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            connection.execute("PRAGMA journal_mode=WAL")
            connection.commit()

    def record_usage(
        self,
        request_id: str,
        customer: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        latency_ms: int,
        worker_id: str | None,
        status: str,
        timestamp: str,
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO usage_records (
                        request_id, customer, model, input_tokens, output_tokens, total_tokens,
                        latency_ms, worker_id, status, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        customer,
                        model,
                        int(input_tokens),
                        int(output_tokens),
                        int(total_tokens),
                        int(latency_ms),
                        worker_id,
                        status,
                        timestamp,
                    ),
                )
                connection.commit()

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT request_id, customer, model, input_tokens, output_tokens, total_tokens,
                       latency_ms, worker_id, status, timestamp
                FROM usage_records
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "request_id": row[0],
                "customer": row[1],
                "model": row[2],
                "input_tokens": row[3],
                "output_tokens": row[4],
                "total_tokens": row[5],
                "latency_ms": row[6],
                "worker_id": row[7],
                "status": row[8],
                "timestamp": row[9],
            }
            for row in rows
        ]

    def close(self) -> None:
        pass
