"""Async-safe SQLite repository boundary for Phase 1."""

from __future__ import annotations

import asyncio
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from .migrations import apply_migrations

T = TypeVar("T")


class SQLiteRepository:
    """Run all blocking sqlite work in a worker thread."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        # Serialize transactions for one repository instance. The lock is
        # acquired only inside the worker thread, so it never blocks HA's
        # event loop while preserving read-modify-write atomicity.
        self._transaction_lock = threading.Lock()

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _run(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        with self._transaction_lock:
            connection = self._connect(self.path)
            try:
                with connection:
                    apply_migrations(connection)
                    return operation(connection)
            finally:
                connection.close()

    async def async_run(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        """Execute a repository operation without blocking HA's event loop."""

        return await asyncio.to_thread(self._run, operation)

    async def async_schema_version(self) -> int:
        return await self.async_run(lambda conn: int(conn.execute("PRAGMA user_version").fetchone()[0]))
