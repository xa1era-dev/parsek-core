import dataclasses
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Protocol,
    get_type_hints,
    runtime_checkable,
)

from core.mixins.env_config_mixin import EnvConfigMixin


class BasePipeline(EnvConfigMixin, ABC):
    var_group = "PIPELINE"

    def __init__(self) -> None:
        # Config without required fields: create a default instance now so _apply_env
        # has something to patch. Configs with required fields are built inside _apply_env
        # directly from env vars (cfg_type() would fail for those).
        if not hasattr(self, "config"):
            hints = get_type_hints(type(self))
            cfg_type = hints.get("config")
            if cfg_type is not None and dataclasses.is_dataclass(cfg_type):
                required = [
                    f for f in dataclasses.fields(cfg_type)
                    if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING  # type: ignore[misc]
                ]
                if not required:
                    self.config = cfg_type()
        super().__init__()


class TransformPipeline[TInput, TOutput](BasePipeline):
    @abstractmethod
    async def pre_parse_process(
        self, source: AsyncIterator[TInput]
    ) -> AsyncIterator[TOutput]: ...

    @abstractmethod
    async def post_parser_process(
        self, source: AsyncIterator[TInput]
    ) -> AsyncIterator[TOutput]: ...


class SourcePipeline[TInput, TOutput](BasePipeline):
    @abstractmethod
    async def pre_parse_process(self) -> AsyncIterator[TOutput]: ...

    @abstractmethod
    async def post_parser_process(self, source: AsyncIterator[TInput]) -> None: ...


class KeyedSourcePipeline[TInput, TOutput](BasePipeline):
    """SourcePipeline с поддержкой получения результата по ключу.

    post_parser_process — асинхронный генератор: сохраняет каждый элемент
    из source и yield-ит ключ, по которому его можно получить позднее.
    """

    @abstractmethod
    async def pre_parse_process(self) -> AsyncIterator[TOutput]: ...

    @abstractmethod
    def post_parser_process(
        self, source: AsyncIterator[TInput]
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def get_by_key(self, key: str) -> Any: ...


@runtime_checkable
class ReverseSourcePipelineProtocol[TInput, TOutput](Protocol):
    async def get_by_key(self, key: str) -> TOutput: ...
    async def calc_key(self, result: TOutput) -> str: ...
