from enum import IntEnum, auto


class ProxyListStrategy(IntEnum):
    PARSER = auto()
    TASK = auto()


class ProxyGetStrategy(IntEnum):
    POP = auto()
    PICK = auto()


class WorkerState(IntEnum):
    INITED = auto()
    RUNNING = auto()
    PAUSING = auto()
    PAUSED = auto()
    STOPPING = auto()
    WAITING = auto()


class TaskState(IntEnum):
    RUNNING = auto()
    PAUSING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()


class TaskSSETypes(IntEnum):
    WORKER_STATE_CHANGED = auto()
    QUERY_PARSED = auto()
    QUERY_FAILED = auto()
    QUERY_ADDED = auto()
