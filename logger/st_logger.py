import logging
import os
import sys

from .tags.context import logger_context

BLUE = "\033[34m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


class ContextFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style="%"):
        super().__init__(fmt, datefmt, style)

    def _get_call_context(self):
        context_tags = logger_context.get()
        if not context_tags:
            return ""

        context_info = [str(tag) for tag in context_tags]
        return " | ".join(context_info)

    def format(self, record):
        context = self._get_call_context()
        if context:
            record.msg = f"[{context}] {record.msg}"
        return super().format(record)


class ColoredFormatter(ContextFormatter):
    COLORS = {
        "DEBUG": "\033[36m",  # Бирюзовый
        "INFO": "",  # Стандартный цвет терминала
        "WARNING": "\033[33m",  # Темно-желтый
        "ERROR": "\033[31m",  # Темно-красный
        "CRITICAL": "\033[35m",  # Темно-пурпурный
    }

    def format(self, record):
        colored_time = f"{BLUE}%(asctime)s{RESET}"
        colored_level = f"{self.COLORS.get(record.levelname, '')}%(levelname)-8s{RESET}"

        PATH_WIDTH = 50

        path_str = f"{os.path.relpath(record.pathname)}:{record.lineno}"

        path_str = path_str[:PATH_WIDTH].ljust(PATH_WIDTH)
        colored_path = f"{GREEN}{path_str}{RESET}"

        colored_msg = f"{self.COLORS.get(record.levelname, '')}%(message)s{RESET}"

        self._style._fmt = (
            f"{colored_time} | {colored_level} | {colored_path} - {colored_msg}"
        )

        result = super().format(record)

        return result


def setup_logger():
    formatter = ColoredFormatter(
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    return root_logger
