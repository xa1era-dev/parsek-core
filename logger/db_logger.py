import logging
import sqlite3
import traceback
from contextvars import ContextVar
from pathlib import Path

from core.sqlite_worker import SQLiteBackgroundWorker

from .tags.context import logger_context

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rows (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    content    TEXT    NOT NULL,
    level      TEXT    NOT NULL,
    timestamp  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    row_id INTEGER NOT NULL REFERENCES rows(id) ON DELETE CASCADE,
    key    TEXT    NOT NULL,
    value  TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    row_id INTEGER NOT NULL REFERENCES rows(id) ON DELETE CASCADE,
    path   TEXT    NOT NULL
);
"""


class DBHandler(logging.Handler, SQLiteBackgroundWorker):
    """Неблокирующий logging-хэндлер: пишет в SQLite через фоновый поток."""

    def __init__(self, db_path: str | Path, level: int = logging.NOTSET) -> None:
        logging.Handler.__init__(self, level)
        SQLiteBackgroundWorker.__init__(self, db_path, thread_name="db-log-worker")

    def _schema_sql(self) -> str:
        return _SCHEMA

    def _handle(self, conn: sqlite3.Connection, items: list[tuple]) -> None:
        for item in items:
            op = item[0]
            if op == "log":
                _, record, tags = item
                self._write_record(conn, record, tags)
            elif op == "attach":
                _, row_id, path = item
                conn.execute(
                    "INSERT INTO attachments (row_id, path) VALUES (?, ?)",
                    (row_id, path),
                )

    # --- public helpers ---

    def attach(self, row_id: int, path: str | Path) -> None:
        """Прикрепить файл-вложение к ранее записанной строке лога."""
        self._queue.put_nowait(("attach", row_id, str(path)))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            tags = list(logger_context.get())
            self._queue.put_nowait(("log", record, tags))
        except Exception:
            self.handleError(record)

    # --- internals ---

    def _write_record(
        self, conn: sqlite3.Connection, record: logging.LogRecord, tags: list
    ) -> None:
        content = record.getMessage()
        if record.exc_info:
            content += "\n" + "".join(traceback.format_exception(*record.exc_info))

        timestamp = int(record.created)

        cursor = conn.execute(
            "INSERT INTO rows (content, level, timestamp) VALUES (?, ?, ?)",
            (content, record.levelname, timestamp),
        )
        row_id = cursor.lastrowid

        for tag in tags:
            for key, value in tag.to_db_tags():
                conn.execute(
                    "INSERT INTO tags (row_id, key, value) VALUES (?, ?, ?)",
                    (row_id, key, value),
                )


_db_handler_ctx: ContextVar["DBHandler | None"] = ContextVar(
    "_db_handler_ctx", default=None
)


class RoutingHandler(logging.Handler):
    """Перенаправляет записи в per-task DBHandler если установлен, иначе в fallback."""

    def __init__(self, fallback: logging.Handler) -> None:
        super().__init__()
        self._fallback = fallback

    def emit(self, record: logging.LogRecord) -> None:
        handler = _db_handler_ctx.get()
        if handler is not None:
            handler.emit(record)
        else:
            self._fallback.emit(record)


class DBLogger:
    """Контекстный менеджер: внутри контекста логи текущей async-задачи идут в SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._handler: DBHandler | None = None
        self._token = None

    def _enter(self) -> "DBLogger":
        self._handler = DBHandler(self._db_path)
        self._token = _db_handler_ctx.set(self._handler)
        return self

    def _exit(self, exc_type=None, exc_val=None, exc_tb=None) -> None:
        if self._token is not None:
            _db_handler_ctx.reset(self._token)
            self._token = None

    def __enter__(self) -> "DBLogger":
        return self._enter()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._exit(exc_type, exc_val, exc_tb)

    async def __aenter__(self) -> "DBLogger":
        return self._enter()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self._exit(exc_type, exc_val, exc_tb)
