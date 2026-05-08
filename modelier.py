from typing import Any, Literal, Union, get_args, get_origin


class Props:
    def __init__(self, type: str, name: str = None):
        self.type = type
        self.name = name


# Метаданные для поля
class Field:
    def __init__(self, necessary: bool = False, serialize_class: type = None):
        self.necessary = necessary
        self.serialize_class = serialize_class


class BaseModel:
    __fields__: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__fields__ = {}

    def __init__(self, **kwargs):
        annotations = {}
        for cls in reversed(self.__class__.__mro__):
            if hasattr(cls, "__annotations__"):
                annotations.update(cls.__annotations__)

        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue

            default_value = getattr(self.__class__, field_name, None)

            if isinstance(default_value, Field):
                setattr(self, f"_meta_{field_name}", default_value)
                value = kwargs.pop(field_name, None)
                if value is None:
                    if default_value.necessary:
                        raise ValueError(f"Field '{field_name}' is necessary")
                else:
                    self._validate_type(field_name, value, field_type)
            else:
                value = kwargs.pop(field_name, default_value)
                if value is not None and value is not default_value:
                    self._validate_type(field_name, value, field_type)

            setattr(self, field_name, value)

        for field_name, value in kwargs.items():
            setattr(self, field_name, value)

    def _validate_type(self, field_name: str, value: Any, field_type: Any):
        if field_type is Any:
            return

        origin = get_origin(field_type)
        if origin is Union:
            allowed_types = get_args(field_type)
            if not any(self._check_type(value, t) for t in allowed_types):
                raise TypeError(
                    f"Field '{field_name}' must be one of {allowed_types}, got {type(value)}"
                )
            return

        if origin is Literal:
            allowed_values = get_args(field_type)
            if value not in allowed_values:
                raise ValueError(
                    f"Field '{field_name}' must be one of {allowed_values}, got '{value}'"
                )
            return

        if origin is list:
            if not isinstance(value, list):
                raise TypeError(f"Field '{field_name}' must be list, got {type(value)}")

            item_type = get_args(field_type)
            if item_type:
                for i, item in enumerate(value):
                    if not self._check_type(item, item_type[0]):
                        raise TypeError(
                            f"Field '{field_name}[{i}]' must be {item_type[0]}, got {type(item)}"
                        )
            return

        if not self._check_type(value, field_type):
            raise TypeError(
                f"Field '{field_name}' must be {field_type}, got {type(value)}"
            )

    def _check_type(self, value: Any, expected_type: Any) -> bool:
        if isinstance(expected_type, type) and issubclass(expected_type, BaseModel):
            return isinstance(value, expected_type)

        try:
            return isinstance(value, expected_type)
        except TypeError:
            return False

    def __getattr__(self, name: str) -> Any:
        return self.__fields__.get(name)

    def serialize(self) -> dict:
        """Сериализация в словарь"""
        result = {}

        for attr_name in dir(self):
            if attr_name.startswith("_") or callable(getattr(self, attr_name)):
                continue

            field_value = getattr(self, attr_name)

            meta = getattr(self, f"_meta_{attr_name}", None)
            if meta and meta.serialize_class:
                field_value = meta.serialize_class(field_value)

            if isinstance(field_value, list):
                field_value = [
                    item.serialize() if hasattr(item, "serialize") else item
                    for item in field_value
                ]
            elif hasattr(field_value, "serialize"):
                field_value = field_value.serialize()

            result[attr_name] = field_value

        return result
