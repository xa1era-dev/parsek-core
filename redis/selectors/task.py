from __future__ import annotations

from core.redis.selector import Selector


class TasksPod(Selector):
    name = "pod"


class TasksGroup(Selector):
    name = "group"


class TasksRawData(Selector):
    name = "raw_data"


class Tasks(Selector):
    name = "tasks"

    pod = TasksPod
    group = TasksGroup
    raw_data = TasksRawData


__all__ = ["Tasks"]
