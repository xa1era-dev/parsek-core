from typing import Any


class ToDictSerializableMixin:
    def to_dict(self) -> dict[Any, Any]:
        result = {}
        for key, value in self.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, ToDictSerializableMixin):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result
