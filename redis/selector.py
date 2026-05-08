from __future__ import annotations


class SelectorMetaClass(type):
    def __getattribute__(cls, name: str) -> Selector | type[Selector]:
        if name in ("name", "_prev", "add_child", "select") or (
            name.startswith("__") and name.endswith("__")
        ):
            return super().__getattribute__(name)
        item = cls.__dict__.get(name)
        if isinstance(item, str):
            selector = Selector()
            selector.name = item
            selector._prev = cls
            return selector
        if isinstance(item, type) and issubclass(item, Selector):
            item._prev = cls
            return item
        raise AttributeError(f"{cls.__name__} has no attribute {name}")

    def __getattr__(cls, name):
        item = cls.__dict__.get(name)
        if isinstance(item, str):
            selector = Selector()
            selector.name = item
            selector._prev = cls
            return selector
        if isinstance(item, type) and issubclass(item, Selector):
            item._prev = cls
            return item
        raise AttributeError(f"{cls.__name__} has no attribute {name}")


# TODO: Сделать типизацию для селекторов
class Selector(metaclass=SelectorMetaClass):
    name: str
    _prev: Selector | None = None

    # TODO: Сделать добавления селектора в тип, чтобы ide не ругался на несуществующий атрибут
    @classmethod
    def add_child(cls, selector: type[Selector]):
        setattr(cls, selector.__name__, selector)

    @classmethod
    def select(cls, name: str) -> str:
        selector = Selector()
        selector.name = name
        selector._prev = cls
        return selector()

    def __str__(self):
        items = []
        selector = self
        while selector is not None:
            items.append(selector.name)
            selector = selector._prev
        return ":".join(reversed(items))

    def __repr__(self):
        return f"<Selector {str(self)}>"

    def __call__(self):
        return str(self)
