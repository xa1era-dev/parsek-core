import enum
from typing import Any, get_type_hints


class FromProtoMixin:
    @classmethod
    def from_proto(cls, data: object):
        obj = cls.__new__(cls)
        hints = get_type_hints(cls)

        def coerce(val: Any, target: Any):
            if (
                isinstance(val, enum.Enum)
                and isinstance(target, type)
                and issubclass(target, enum.Enum)
            ):
                return target[val.name]
            return val

        obj.__dict__.update(
            {k: coerce(getattr(data, k), hints[k]) for k in hints if hasattr(data, k)}
        )
        return obj
