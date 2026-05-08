from __future__ import annotations

from core.redis.selector import Selector


class ProxyLoaded(Selector):
    name = "loaded"


class ProxyToCheck(Selector):
    name = "to_check"


class ProxyAvailable(Selector):
    name = "available"


class ProxyReported(Selector):
    name = "reported"


class ProxyBanned(Selector):
    name = "banned"


class TasksRegistry(Selector):
    name = "tasks"


class Proxy(Selector):
    name = "proxy"

    loaded = ProxyLoaded
    to_check = ProxyToCheck
    available = ProxyAvailable
    reported = ProxyReported
    banned = ProxyBanned
    tasks = TasksRegistry


__all__ = [
    "Proxy",
]
