from __future__ import annotations

import dataclasses
import inspect
import os
import re
import threading
from enum import Enum
from typing import Any, ClassVar, List, Type, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T", bound="EnvConfigMixin")

_pending_prefix: threading.local = threading.local()


def _is_classvar(annotation: Any) -> bool:
    return (
        annotation is ClassVar
        or get_origin(annotation) is ClassVar
        or str(annotation).startswith("typing.ClassVar")
    )


def _cast(value: str, annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if non_none:
            return _cast(value, non_none[0])
    if annotation is bool:
        return value.lower() in ("1", "true", "yes")
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    return value



def _unwrap_optional(annotation: Any) -> Any:
    """Возвращает внутренний тип из Optional[X], иначе сам annotation."""
    if get_origin(annotation) is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        return non_none[0] if non_none else annotation
    return annotation


def _apply_env_to_object(obj: Any, prefix: str) -> None:
    """Применяет env к обычному (не-dataclass) объекту, мутируя его атрибуты.

    Обрабатывает:
    - class-level атрибуты с type-аннотациями (включая вложенные dataclass)
    - instance-атрибуты (например, из **kwargs)
    """
    try:
        hints = get_type_hints(type(obj))
    except Exception:
        hints = {}

    processed: set[str] = set()

    # 1. Type-annotated поля класса (class-level defaults, вложенные dataclass)
    for attr, annotation in hints.items():
        if attr.startswith("_") or _is_classvar(annotation):
            continue
        processed.add(attr)
        current = getattr(obj, attr, None)
        key = f"{prefix}:{attr.upper()}"
        inner = _unwrap_optional(annotation)

        if isinstance(inner, type) and dataclasses.is_dataclass(inner):
            # Если значение не является нужным типом (например, Field-объект), создаём инстанс
            if not isinstance(current, inner):
                current = inner()
                setattr(obj, attr, current)
            new_val = _apply_env_to_dataclass(current, key)
            if new_val is not current:
                setattr(obj, attr, new_val)
        else:
            raw = os.getenv(key)
            if raw is not None:
                setattr(obj, attr, _cast(raw, annotation))

    # 2. Instance-атрибуты без type-аннотаций (например, kwargs в ParserConfig)
    for attr, current in list(vars(obj).items()):
        if attr.startswith("_") or attr in processed:
            continue
        key = f"{prefix}:{attr.upper()}"
        if dataclasses.is_dataclass(current):
            new_val = _apply_env_to_dataclass(current, key)
            if new_val is not current:
                setattr(obj, attr, new_val)
        else:
            raw = os.getenv(key)
            if raw is not None:
                annotation = type(current) if current is not None else str
                setattr(obj, attr, _cast(raw, annotation))


def _apply_env(obj: Any, prefix: str) -> None:
    """Применяет env к instance-уровню EnvConfigMixin-объекта.

    Обрабатывается только поле `config`, прозрачно маппится
    на уровень prefix без вложения :CONFIG:.
    Для frozen dataclass создаёт новый экземпляр через replace.
    Для обычного объекта мутирует атрибуты на месте.
    """
    current = getattr(obj, "config", None)
    if current is None:
        # Config annotation exists but no instance yet (required fields).
        # Build it from env vars so required fields are satisfied.
        try:
            hints = get_type_hints(type(obj))
        except Exception:
            hints = {}
        cfg_type = hints.get("config")
        if cfg_type is None or not dataclasses.is_dataclass(cfg_type):
            return
        dc_hints = get_type_hints(cfg_type)
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cfg_type):
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:  # type: ignore[misc]
                key = f"{prefix}:{f.name.upper()}"
                raw = os.getenv(key)
                if raw is not None:
                    kwargs[f.name] = _cast(raw, dc_hints.get(f.name, str))
        try:
            current = cfg_type(**kwargs)  # type: ignore[operator]
        except TypeError:
            return
        setattr(obj, "config", current)
    if dataclasses.is_dataclass(current):
        new_val = _apply_env_to_dataclass(current, prefix)
        if new_val is not current:
            setattr(obj, "config", new_val)
    else:
        _apply_env_to_object(current, prefix)


def _apply_env_to_dataclass(obj: Any, prefix: str) -> Any:
    """Применяет env к dataclass, возвращая новый экземпляр при изменениях.

    Поддерживает frozen dataclass через dataclasses.replace().
    """
    hints = get_type_hints(type(obj))
    changes: dict[str, Any] = {}
    for f in dataclasses.fields(obj):
        annotation = hints.get(f.name, str)
        current = getattr(obj, f.name)
        key = f"{prefix}:{f.name.upper()}"
        if dataclasses.is_dataclass(current):
            new_val = _apply_env_to_dataclass(current, key)
            if new_val is not current:
                changes[f.name] = new_val
        else:
            raw = os.getenv(key)
            if raw is not None:
                changes[f.name] = _cast(raw, annotation)
    return dataclasses.replace(obj, **changes) if changes else obj


def _type_name(annotation: Any) -> str | list[str]:
    """Возвращает читаемое имя типа для схемы.

    Для enum возвращает список допустимых имён значений.
    """
    if annotation is str:
        return "str"
    if annotation is int:
        return "int"
    if annotation is float:
        return "float"
    if annotation is bool:
        return "bool"
    origin = get_origin(annotation)
    if origin is Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _type_name(non_none[0])
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return [m.name for m in annotation]
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    return str(annotation)


def _serialize_value(value: Any) -> Any:
    """Приводит значение к сериализуемому виду для схемы."""
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, dataclasses.Field):
        return None
    return value


def _get_field_comments(cls: type) -> dict[str, str]:
    """Извлекает inline # комментарии к полям из исходного кода класса."""
    try:
        source_lines = inspect.getsource(cls).splitlines()
    except (OSError, TypeError):
        return {}
    comments: dict[str, str] = {}
    for line in source_lines:
        if "#" not in line:
            continue
        code, _, comment = line.partition("#")
        stripped = code.strip()
        if not stripped:
            continue
        m = re.match(r"^(\w+)\s*(?::|=)", stripped)
        if m:
            comments[m.group(1)] = comment.strip()
    return comments


def _dump_config(cfg: Any) -> dict:
    """Рекурсивно собирает значения из dataclass или обычного объекта конфига."""
    if dataclasses.is_dataclass(cfg):
        result = {}
        for f in dataclasses.fields(cfg):
            value = getattr(cfg, f.name, None)
            if value is not None and dataclasses.is_dataclass(value):
                result[f.name] = _dump_config(value)
            else:
                result[f.name] = value
        return result
    # Обычный объект (например ParserConfig с **kwargs или class-level attrs)
    try:
        hints = get_type_hints(type(cfg))
    except Exception:
        hints = {}
    result = {}
    seen: set[str] = set()
    # class-level annotated attrs
    for attr in hints:
        if attr.startswith("_") or _is_classvar(hints[attr]):
            continue
        seen.add(attr)
        value = getattr(cfg, attr, None)
        if value is not None and dataclasses.is_dataclass(value):
            result[attr] = _dump_config(value)
        elif not isinstance(value, dataclasses.Field):
            result[attr] = value
    # instance-only attrs (kwargs)
    for attr, value in vars(cfg).items():
        if attr.startswith("_") or attr in seen:
            continue
        if dataclasses.is_dataclass(value):
            result[attr] = _dump_config(value)
        else:
            result[attr] = value
    return result


def _dump_values(obj: Any) -> dict:
    """Рекурсивно собирает текущие значения полей объекта."""
    if dataclasses.is_dataclass(obj):
        return _dump_config(obj)
    cfg = getattr(obj, "config", None)
    if cfg is not None and not isinstance(cfg, type):
        return _dump_config(cfg)
    return {}


def _build_schema_from_instance(obj: Any) -> dict:
    """Строит схему из инстанса обычного (не-dataclass) объекта конфига."""
    try:
        hints = get_type_hints(type(obj))
    except Exception:
        hints = {}
    comments = _get_field_comments(type(obj))
    result = {}
    seen: set[str] = set()
    # class-level annotated attrs
    for attr, annotation in hints.items():
        if attr.startswith("_") or _is_classvar(annotation):
            continue
        seen.add(attr)
        value = getattr(obj, attr, None)
        inner = _unwrap_optional(annotation)
        if isinstance(inner, type) and dataclasses.is_dataclass(inner):
            nested = value if isinstance(value, inner) else None
            result[attr] = _build_schema(inner, nested)
        else:
            entry: dict[str, Any] = {"type": _type_name(annotation), "value": _serialize_value(value)}
            if label := comments.get(attr):
                entry["label"] = label
            result[attr] = entry
    # instance-only attrs (kwargs, без аннотаций)
    for attr, value in vars(obj).items():
        if attr.startswith("_") or attr in seen:
            continue
        if dataclasses.is_dataclass(value):
            result[attr] = _build_schema(type(value), value)
        else:
            entry = {"type": _type_name(type(value) if value is not None else str), "value": _serialize_value(value)}
            if label := comments.get(attr):
                entry["label"] = label
            result[attr] = entry
    return result


def _find_config_value(cls: type) -> Any:
    """Ищет конкретное значение config (не тип и не None) в MRO класса."""
    for klass in cls.__mro__:
        val = klass.__dict__.get("config")
        if val is not None and not isinstance(val, type):
            return val
    return None


def _find_config_type(cls: type) -> type | None:
    """Ищет тип аннотации config (не ClassVar) в MRO класса.

    Используется для instance-based конфигов, у которых нет значения в class dict.
    """
    for klass in cls.__mro__:
        if "config" not in klass.__dict__.get("__annotations__", {}):
            continue
        try:
            hints = get_type_hints(klass)
            hint = hints.get("config")
            if hint is not None and not _is_classvar(hint) and isinstance(hint, type):
                return hint
        except Exception:
            raw = klass.__dict__.get("__annotations__", {}).get("config")
            if isinstance(raw, type) and not _is_classvar(raw):
                return raw
    return None


def _build_schema(cls: type, instance: Any = None) -> dict:
    """Рекурсивно строит схему полей.

    Каждое листовое поле — словарь {"type": ..., "value": ..., "label": ...}.
    Для dataclass — по полям с type hints и inline комментариями.
    Для EnvConfigMixin — ищет config по MRO, не вызывает get_type_hints на
    самом парсере (избегает проблем с TYPE_CHECKING-импортами).
    """
    result = {}

    if dataclasses.is_dataclass(cls):
        try:
            hints = get_type_hints(cls)
        except Exception:
            hints = {}
        comments = _get_field_comments(cls)
        field_labels = {f.name: f.metadata["label"] for f in dataclasses.fields(cls) if f.metadata and "label" in f.metadata}
        dc_names = {f.name for f in dataclasses.fields(cls)}
        for name, hint in hints.items():
            if name not in dc_names:
                continue
            value = getattr(instance, name, None) if instance is not None else None
            inner = _unwrap_optional(hint)
            if isinstance(inner, type) and dataclasses.is_dataclass(inner):
                nested = value if isinstance(value, inner) else None
                result[name] = _build_schema(inner, nested)
            else:
                entry: dict[str, Any] = {"type": _type_name(hint), "value": _serialize_value(value)}
                label = field_labels.get(name) or comments.get(name)
                if label:
                    entry["label"] = label
                result[name] = entry
    else:
        cfg_val = _find_config_value(cls)
        if cfg_val is not None:
            if dataclasses.is_dataclass(cfg_val):
                result.update(_build_schema(type(cfg_val), cfg_val))
            else:
                result.update(_build_schema_from_instance(cfg_val))
        else:
            cfg_type = _find_config_type(cls)
            if cfg_type is not None and dataclasses.is_dataclass(cfg_type):
                result.update(_build_schema(cfg_type))

    return result


class EnvConfigMixin:
    """
    Mixin для классов и dataclass-конфигов. Заполняет поля из переменных окружения.

    Работает как с @dataclass, так и с обычными классами.
    ClassVar[SomeDataclass]-поля применяются на уровне класса через __init_subclass__,
    поддерживая frozen dataclass через dataclasses.replace().

    Формат переменной окружения:
        {VAR_GROUP}:{FIELD}              — верхний уровень
        {VAR_GROUP}:{FIELD}:{SUBFIELD}   — вложенный dataclass
        {VAR_GROUP}1:{FIELD}             — нумерованный экземпляр (пайплайны)

    Атрибут класса var_group задаёт префикс (приводится к верхнему регистру).
    """

    var_group: str = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        prefix = getattr(cls, "var_group", "").upper()
        if not prefix:
            return
        # Обрабатываем только если config задан непосредственно в этом классе
        val = cls.__dict__.get("config")
        if val is None or isinstance(val, type):
            return
        # Проверяем что аннотация config — ClassVar, обходя MRO без полного get_type_hints
        for klass in cls.__mro__:
            # Берём из __dict__ напрямую — избегаем lazy evaluation в Python 3.14+
            raw = klass.__dict__.get("__annotations__", {}).get("config")
            if raw is None:
                continue
            is_cv = _is_classvar(raw) or "ClassVar" in str(raw)
            if not is_cv:
                return  # instance-based config, обрабатывается в __init__
            break
        if dataclasses.is_dataclass(val):
            setattr(cls, "config", _apply_env_to_dataclass(val, prefix))
        else:
            _apply_env_to_object(val, prefix)

    def __init__(self) -> None:
        super().__init__()
        if not dataclasses.is_dataclass(self):
            prefix = getattr(_pending_prefix, "value", None) or type(self).var_group.upper()
            _apply_env(self, prefix)

    def __post_init__(self) -> None:
        prefix = getattr(_pending_prefix, "value", None) or type(self).var_group.upper()
        _apply_env(self, prefix)
        try:
            super().__post_init__()  # type: ignore[misc]
        except AttributeError:
            pass

    @classmethod
    def from_prefix(cls: Type[T], prefix: str) -> T:
        """Создаёт экземпляр с явно заданным префиксом env-переменных."""
        _pending_prefix.value = prefix.upper()
        try:
            return cls()
        finally:
            _pending_prefix.value = None

    @classmethod
    def from_index(cls: Type[T], index: int) -> T:
        """Создаёт экземпляр с нумерованным префиксом: {VAR_GROUP}{index}."""
        return cls.from_prefix(f"{cls.var_group}{index}")

    @classmethod
    def schema(cls) -> dict:
        """Возвращает схему конфига с именами типов в виде вложенного словаря."""
        return {cls.var_group.lower(): _build_schema(cls)}

    def values(self) -> dict:
        """Возвращает текущие значения всех полей в виде вложенного словаря."""
        return {type(self).var_group.lower(): _dump_values(self)}

    @classmethod
    def load_all(cls: Type[T]) -> List[T]:
        """
        Загружает все нумерованные экземпляры подряд.
        Останавливается, когда для следующего индекса нет ни одной переменной.
        """
        group = cls.var_group.upper()
        result: List[T] = []
        i = 1
        while any(k.startswith(f"{group}{i}:") for k in os.environ):
            result.append(cls.from_index(i))
            i += 1
        return result