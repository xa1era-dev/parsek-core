import logging
from urllib.parse import ParseResult


class ProxyValidaterMixin:
    def _is_proxy_line(self, parsed_url: ParseResult) -> bool:
        if parsed_url.query:
            logging.warning(
                f"Proxy line '{parsed_url.geturl()}' contains query parameters, which is not expected. Skipping."
            )
        return (
            parsed_url.scheme in ("http", "https", "socks4", "socks5")
            and parsed_url.netloc != ""
            and parsed_url.port is not None
        )
