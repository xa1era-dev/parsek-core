from core.mixins import FromProtoMixin, ToDictSerializableMixin
from core.types_.enums import ProxyGetStrategy, ProxyListStrategy


class TaskSchema(FromProtoMixin, ToDictSerializableMixin):
    uuid: str
    name: str

    proxy: str
    report_to_ban: int | None
    ban_seconds: int
    list_ban_strategy: ProxyListStrategy
    list_strategy: ProxyListStrategy
    pickup_strategy: ProxyGetStrategy

    @property
    def selector(self) -> str:
        self.list_strategy = ProxyListStrategy(self.list_strategy)
        if self.list_strategy == ProxyListStrategy.PARSER:
            return self.name
        elif self.list_strategy == ProxyListStrategy.TASK:
            return self.uuid
        else:
            raise ValueError(f"Unknown list strategy: {self.list_strategy}")
