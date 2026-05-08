from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

from core.mixins.env_config_mixin import EnvConfigMixin
from core.types_.parser_config import ParserConfig
from core.types_.query import Query, Result

if TYPE_CHECKING:
    from services.proxy_manager import ProxyParserInterface
    from services.queues import QueryQueueParserInterface


@runtime_checkable
class Parser(Protocol):
    @classmethod
    async def init(cls) -> None: ...

    @classmethod
    async def destroy(cls) -> None: ...

    async def init_thread(self) -> None: ...

    async def destroy_thread(self) -> None: ...

    async def parse[T](self, query: Query, result: Result[T]) -> Result[T]: ...


class ConfigParser(EnvConfigMixin):
    var_group = "PARSER"
    config: ClassVar[ParserConfig]


class BaseParser(Parser, ConfigParser):
    proxy: ProxyParserInterface
    query: QueryQueueParserInterface

    @classmethod
    async def init(cls) -> None: ...

    @classmethod
    async def destroy(cls) -> None: ...

    async def init_thread(self) -> None: ...

    async def destroy_thread(self) -> None: ...
