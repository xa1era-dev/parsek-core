from __future__ import annotations

from core.redis.selector import Selector


class GroupLimit(Selector):
    name = "limit"


class Group(Selector):
    name = "group"

    limit = GroupLimit


__all__ = ["Group"]