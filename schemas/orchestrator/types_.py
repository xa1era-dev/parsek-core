from __future__ import annotations

from pathlib import Path

type NestedDict[T] = dict[str, "NestedDict[T]" | T]
type EnvValues = bool | int | Path | str

__all__ = ["NestedDict", "EnvValues"]
