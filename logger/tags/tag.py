from typing import Callable, Iterable

from .context import logger_context


class ContextTagger:
    def enter(self):
        current_context = logger_context.get()
        new_context = current_context + [self]
        logger_context.set(new_context)
        return self

    def exit(self, exc_type=None, exc_val=None, exc_tb=None):
        current_context = logger_context.get()
        new_context = [tag for tag in current_context if tag is not self]
        logger_context.set(new_context)

    def __enter__(self):
        return self.enter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exit(exc_type, exc_val, exc_tb)

    async def __aenter__(self):
        return self.enter()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit(exc_type, exc_val, exc_tb)

    def to_db_tags(self) -> list[tuple[str, str | None]]:
        return [(str(self), None)]


class LoggerTags(ContextTagger):
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def __str__(self) -> str:
        return "; ".join([f"{key}={value}" for key, value in self.kwargs.items()])

    def __repr__(self) -> str:
        return f"<Tag {str(self)}>"

    def to_db_tags(self) -> list[tuple[str, str | None]]:
        return [(k, str(v)) for k, v in self.kwargs.items()]


class LoggerTag(ContextTagger):
    def __init__(self, tag: str | Callable[[], str]) -> None:
        self.tag = tag

    def __str__(self) -> str:
        if isinstance(self.tag, str):
            return self.tag
        return self.tag()

    def __repr__(self) -> str:
        return f"<Tag {str(self)}>"

    def to_db_tags(self) -> list[tuple[str, str | None]]:
        return [(str(self), None)]


class LoggerProgressIter[T](ContextTagger):
    def __init__(self, iterator: Iterable[T], total_count: int | None = None) -> None:
        self.__iterator = iter(iterator)
        self.__max = total_count or len(list(iterator))
        self.__cur_index = 0

    def __str__(self) -> str:
        return rf"<{self.__cur_index} \ {self.__max}>"

    def __repr__(self) -> str:
        return f"<Tag {str(self)}>"

    def to_db_tags(self) -> list[tuple[str, str | None]]:
        return [("progress", f"{self.__cur_index}/{self.__max}")]

    def __iter__(self):
        self.enter()
        return self

    def __next__(self):
        self.__cur_index += 1
        try:
            return next(self.__iterator)
        except StopIteration:
            self.exit()
            raise
