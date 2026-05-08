import asyncio
import functools
from collections.abc import Coroutine
from typing import Any, Callable


def as_task[**P, R](
    func: Callable[P, Coroutine[Any, Any, R]],
) -> Callable[P, asyncio.Task[R]]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> asyncio.Task[R]:
        return asyncio.create_task(func(*args, **kwargs))

    return wrapper
