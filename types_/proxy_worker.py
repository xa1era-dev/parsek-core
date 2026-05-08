from typing import AsyncIterator, Coroutine, Iterator, Protocol
from urllib.parse import ParseResult


class ProxyGetter(Protocol):
    def get_proxies(self) -> Iterator[ParseResult]: ...


class AsyncProxyGetter(Protocol):
    def get_proxies(self) -> AsyncIterator[ParseResult]: ...


class ProxyChecker(Protocol):
    def check(self, proxy: str) -> bool: ...


class AsyncProxyChecker(Protocol):
    def check(self, proxy: str) -> Coroutine[None, None, bool]: ...


class NamedProxyWorker(Protocol):
    name: str


class SyncGetSyncCheck(NamedProxyWorker, ProxyGetter, ProxyChecker, Protocol): ...


class SyncGetAsyncCheck(NamedProxyWorker, ProxyGetter, AsyncProxyChecker, Protocol): ...


class AsyncGetSyncCheck(NamedProxyWorker, AsyncProxyGetter, ProxyChecker, Protocol): ...


class AsyncGetAsyncCheck(
    NamedProxyWorker, AsyncProxyGetter, AsyncProxyChecker, Protocol
): ...


AnyNamedProxyWorker = (
    SyncGetSyncCheck | SyncGetAsyncCheck | AsyncGetSyncCheck | AsyncGetAsyncCheck
)
