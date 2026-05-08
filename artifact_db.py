import asyncio
import sqlite3
from pathlib import Path

import aiosqlite

import config


def _resolve(task_uuid: str, filename: str) -> Path:
    return (Path(config.ARTIFACTS_PATH) / task_uuid / filename).absolute()


class SyncConnect:
    """Sync read context manager for artifact SQLite databases.

    Keeps one persistent connection to avoid journal conflicts with the
    background writer (repeated connect/close cycles corrupt DELETE-mode journals).
    """

    def __init__(self, task_uuid: str, filename: str, timeout: float = 30) -> None:
        self.path = _resolve(task_uuid, filename)
        self._timeout = timeout
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = sqlite3.connect(
            str(self.path), isolation_level=None, timeout=self._timeout
        )
        return self._conn

    def __exit__(self, *_) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class AsyncConnect:
    """Async read context manager for artifact SQLite databases.

    Keeps one persistent connection to avoid journal conflicts with the
    background writer (repeated connect/close cycles corrupt DELETE-mode journals).
    """

    def __init__(self, task_uuid: str, filename: str, timeout: float = 30) -> None:
        self.path = _resolve(task_uuid, filename)
        self._timeout = timeout
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> "AsyncConnect":
        self._conn = await aiosqlite.connect(
            self.path, isolation_level=None, timeout=self._timeout
        )
        return self

    async def __aexit__(self, *_) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def execute(
        self, sql: str, parameters: tuple = (), retries: int = 10
    ) -> "_ExecuteContext":
        return _ExecuteContext(self._conn, sql, parameters, retries)


class _ExecuteContext:
    def __init__(
        self,
        conn: aiosqlite.Connection,
        sql: str,
        parameters: tuple,
        retries: int,
    ) -> None:
        self._conn = conn
        self._sql = sql
        self._parameters = parameters
        self._retries = retries
        self._cursor: aiosqlite.Cursor | None = None

    async def __aenter__(self) -> aiosqlite.Cursor:
        is_select = self._sql.lstrip().upper().startswith("SELECT")
        last_exc: Exception | None = None
        for _ in range(self._retries):
            try:
                self._cursor = await self._conn.execute(self._sql, self._parameters)
                return self._cursor
            except sqlite3.DatabaseError as exc:
                if "malformed" in str(exc).lower():
                    last_exc = exc
                    await asyncio.sleep(0.3)
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    async def __aexit__(self, *_) -> None:
        if self._cursor is not None:
            await self._cursor.close()
            self._cursor = None
