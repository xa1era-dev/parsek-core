from __future__ import annotations

import asyncio
import sys
import weakref
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from functools import wraps
from typing import Any, Callable


class SSEEventType(StrEnum):
    PING = auto()
    WORKER_STATE_CHANGED = auto()
    THREAD_STATE_CHANGED = auto()
    QUERIES_INITIALIZED = auto()
    QUERY_PARSED = auto()
    QUERY_FAILED = auto()
    QUERY_ADDED = auto()


@dataclass
class SSEPayload:
    type: SSEEventType
    data: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    uuid: str | None = None

    async def broadcast(self):
        await SSEBus()._broadcast(self)


_SSE_BUS_KEY = "__sse_bus_instance__"


class SSEBus:
    _subscribers: list[asyncio.Queue[SSEPayload]]

    def __new__(cls) -> SSEBus:
        inst = sys.modules.get(_SSE_BUS_KEY)
        if inst is None:
            inst = super().__new__(cls)
            inst._subscribers = []
            sys.modules[_SSE_BUS_KEY] = inst
        return inst

    def _broadcast_sync(self, payload: SSEPayload) -> None:
        for q in self._subscribers:
            q.put_nowait(payload)

    async def _broadcast(self, payload: SSEPayload) -> None:
        for q in self._subscribers:
            await q.put(payload)

    def subscribe(self) -> _Subscription:
        return _Subscription(self)

    def __aiter__(self) -> _Subscription:
        return self.subscribe()


class _Subscription:
    def __init__(self, bus: SSEBus) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[SSEPayload] = asyncio.Queue()
        bus._subscribers.append(self._queue)

    def __aiter__(self) -> _Subscription:
        return self

    async def __anext__(self) -> SSEPayload:
        return await self._queue.get()

    async def aclose(self) -> None:
        try:
            self._bus._subscribers.remove(self._queue)
        except ValueError:
            pass

    async def __aenter__(self) -> _Subscription:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()


def emit(
    event_type: SSEEventType,
    *,
    data_extractor: Callable[..., Any] | None = None,
) -> Callable:
    """Decorator that publishes an SSEPayload after the wrapped coroutine completes."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            data = data_extractor(result, *args, **kwargs) if data_extractor else result
            uuid = None
            if isinstance(data, tuple):
                uuid, data = data
            await SSEPayload(type=event_type, data=data, uuid=uuid).broadcast()
            return result

        return wrapper

    return decorator


class watched:
    """Wraps a @property and emits an SSEPayload when the value changes.

    For properties with a setter: emits on each assignment that changes the value.
    For read-only properties (no setter): polls every `interval` seconds and emits
    when the value changes.

    Usage (with setter):
        @watched(SSEEventType.WORKER_STATE_CHANGED)
        @property
        def state(self):
            return self._state

        @state.setter
        def state(self, value):
            self._state = value

    Usage (read-only, polled):
        @watched(SSEEventType.QUERY_PARSED, interval=2.0)
        @property
        def parsed_count(self):
            return self._counter
    """

    def __init__(
        self, event_type: SSEEventType, *, uuid=None, interval: float = 1.0
    ) -> None:
        self._event_type = event_type
        self._interval = interval
        self._prop: property | None = None
        self._name: str = ""
        self._uuid = uuid
        self._poll_tasks: weakref.WeakKeyDictionary[Any, asyncio.Task] = (
            weakref.WeakKeyDictionary()
        )
        self._last_values: weakref.WeakKeyDictionary[Any, Any] = (
            weakref.WeakKeyDictionary()
        )

    def __call__(self, prop: property) -> watched:
        self._prop = prop
        return self

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    @property
    def _is_readonly(self) -> bool:
        return self._prop is not None and self._prop.fset is None

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        if self._is_readonly:
            self._ensure_polling(obj)
        return self._prop.__get__(obj, objtype)  # type: ignore[union-attr]

    def _ensure_polling(self, obj: Any) -> None:
        task = self._poll_tasks.get(obj)
        if task is not None and not task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        try:
            self._last_values[obj] = self._prop.fget(obj)  # type: ignore[union-attr]
        except Exception:
            pass
        self._poll_tasks[obj] = loop.create_task(self._poll_loop(obj))

    async def _poll_loop(self, obj: Any) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                new = self._prop.fget(obj)  # type: ignore[union-attr]
            except Exception:
                continue
            old = self._last_values.get(obj)
            if old != new:
                self._last_values[obj] = new
                payload_kwargs = dict(type=self._event_type, data=new)
                if self._uuid:
                    payload_kwargs["uuid"] = self._uuid
                await SSEPayload(**payload_kwargs).broadcast()

    def __set__(self, obj: Any, value: Any) -> None:
        old = self._prop.fget(obj)  # type: ignore[union-attr]
        self._prop.__set__(obj, value)  # type: ignore[union-attr]
        new = self._prop.fget(obj)  # type: ignore[union-attr]
        if old == new:
            return
        await SSEPayload(type=self._event_type, data=new).broadcast()

    def __delete__(self, obj: Any) -> None:
        self._prop.__delete__(obj)  # type: ignore[union-attr]

    def _clone_with(self, prop: property) -> watched:
        clone = watched(self._event_type, interval=self._interval)
        clone._prop = prop
        clone._name = self._name
        clone._poll_tasks = self._poll_tasks
        clone._last_values = self._last_values
        return clone

    def setter(self, fset: Callable) -> watched:
        return self._clone_with(self._prop.setter(fset))  # type: ignore[union-attr]

    def getter(self, fget: Callable) -> watched:
        return self._clone_with(self._prop.getter(fget))  # type: ignore[union-attr]

    def deleter(self, fdel: Callable) -> watched:
        return self._clone_with(self._prop.deleter(fdel))  # type: ignore[union-attr]
