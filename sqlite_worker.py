import queue
import sqlite3
import threading
import traceback
from pathlib import Path
from time import time
from typing import Any


class SQLiteBackgroundWorker:
    """Базовый класс для неблокирующей записи в SQLite через фоновый поток.

    Подклассы должны переопределить:
      - _schema_sql() → DDL-строка для инициализации схемы
      - _handle(conn, items) → обработка батча элементов из очереди (без commit)
    """

    def __init__(self, db_path: str | Path, thread_name: str = "sqlite-worker") -> None:
        self.db_path = str(db_path)
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._SENTINEL = object()
        self._init_schema()
        self._thread = threading.Thread(
            target=self._bg_worker, daemon=True, name=thread_name
        )
        self._thread.start()

    # --- override in subclasses ---

    def _schema_sql(self) -> str:
        return ""

    def _handle(self, conn: sqlite3.Connection, items: list[Any]) -> None:
        raise NotImplementedError

    # --- internal ---

    def _init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=60)
        if sql := self._schema_sql():
            conn.executescript(sql)
            conn.commit()
        conn.close()

    def _configure_conn(self, conn: sqlite3.Connection) -> None:
        conn.execute("PRAGMA journal_mode=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")

    def _flush(self, conn: sqlite3.Connection, items: list[Any]) -> None:
        try:
            self._handle(conn, items)
            conn.commit()
        except Exception:
            conn.rollback()
            print(traceback.format_exc())
        items.clear()

    def _bg_worker(self) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            self._configure_conn(conn)
        except Exception:
            traceback.print_exc()
            return

        items: list[Any] = []
        last_flush = time()

        try:
            while True:
                item = self._queue.get()
                if item is self._SENTINEL:
                    break
                items.append(item)
                if time() - last_flush >= 1:
                    self._flush(conn, items)
                    last_flush = time()
        finally:
            if items:
                self._flush(conn, items)
            conn.close()

    def close(self) -> None:
        self._queue.put_nowait(self._SENTINEL)
        t = time()
        print(f"Closing {self.__class__.__name__}...")
        self._thread.join()
        print(f"Closed {self.__class__.__name__} after {time() - t:.2f}s")
