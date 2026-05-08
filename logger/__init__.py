import logging
import os
import sys
from pathlib import Path

_NOISY_LOGGERS = ["hpack.hpack", "hpack", "grpc", "asyncio", "httpcore"]

_LOG_TYPE_STDOUT = "stdout"
_LOG_TYPE_DB = "db"


def _suppress_noisy() -> None:
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def setup_logging() -> logging.Logger:
    from .db_logger import DBHandler, RoutingHandler
    from .st_logger import ColoredFormatter

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    log_type = os.environ.get("LOG_TYPE", _LOG_TYPE_STDOUT).lower()

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    if log_type == _LOG_TYPE_DB:
        db_path = Path.cwd() / "artifacts" / "logs.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        fallback: logging.Handler = DBHandler(db_path)
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
        fallback = console_handler

    root.addHandler(RoutingHandler(fallback))

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.CRITICAL)
    stderr_handler.setFormatter(ColoredFormatter(datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(stderr_handler)

    _suppress_noisy()
    sys.excepthook = handle_exception

    return root
