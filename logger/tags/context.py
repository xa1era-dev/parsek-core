from contextvars import ContextVar
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .tag import ContextTagger

logger_context: ContextVar[List["ContextTagger"]] = ContextVar(
    "logger_context", default=[]
)
