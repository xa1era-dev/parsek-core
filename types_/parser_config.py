from dataclasses import dataclass

from core.types_.enums import ProxyGetStrategy, ProxyListStrategy


@dataclass(frozen=True)
class ParserProxyConfig:
    name: str
    ban_seconds: int = 5 * 60
    list_ban_strategy: ProxyListStrategy = ProxyListStrategy.TASK
    list_strategy: ProxyListStrategy = ProxyListStrategy.TASK
    get_proxy_strategy: ProxyGetStrategy = ProxyGetStrategy.PICK

    @property
    def proxy_manager_config(self):
        return {
            "ban_seconds": self.ban_seconds,
            "list_ban_strategy": self.list_ban_strategy,
            "list_strategy": self.list_strategy,
            "pickup_strategy": self.get_proxy_strategy,
        }


class ParserConfig:
    """Конфиг парсера с поддержкой произвольных полей.

    Кастомные поля передаются как keyword-аргументы и автоматически
    маппируются на env-переменные вида PARSER:<FIELD_NAME>.

    Example::

        config = ParserConfig(
            proxy=ParserProxyConfig(name="residential"),
            timeout=30,
            api_key="abc",
        )
        # Переопределяется через env: PARSER:TIMEOUT=60, PARSER:API_KEY=xyz
    """

    proxy: ParserProxyConfig | None

    def __init__(self, proxy: ParserProxyConfig | None = None, **kwargs):
        self.proxy = proxy
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self) -> str:
        parts = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"ParserConfig({parts})"

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return vars(self) == vars(other)
