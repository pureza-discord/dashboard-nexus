import os
from urllib.parse import urlparse


class ProxyManager:
    """Gerencia rotacao de proxies HTTP/SOCKS a partir do .env."""

    def __init__(self) -> None:
        self.proxies = self._load_proxies()
        self.index = 0

    def _load_proxies(self) -> list[str]:
        proxies: list[str] = []

        raw_list = os.getenv("PROXY_LIST", "").strip()
        if raw_list:
            proxies.extend([p.strip() for p in raw_list.split(",") if p.strip()])

        proxy_file = os.getenv("PROXY_FILE", "").strip()
        if proxy_file and os.path.exists(proxy_file):
            with open(proxy_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        proxies.append(line)

        return proxies

    def get_proxy(self) -> dict | None:
        if not self.proxies:
            return None

        proxy_url = self.proxies[self.index % len(self.proxies)]
        self.index += 1

        parsed = urlparse(proxy_url)
        if not parsed.scheme:
            proxy_url = f"http://{proxy_url}"
            parsed = urlparse(proxy_url)

        proxy = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username and parsed.password:
            proxy["username"] = parsed.username
            proxy["password"] = parsed.password

        return proxy
