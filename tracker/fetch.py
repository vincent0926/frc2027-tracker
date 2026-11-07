"""HTTP 抓取：統一 User-Agent、遵守 robots.txt、請求間隔。"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests


class PoliteFetcher:
    def __init__(self, user_agent: str, delay: float = 2.0, timeout: float = 30):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_request = 0.0

    def _allowed(self, url: str) -> bool:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(host + "/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                else:  # 沒有 robots.txt => 允許
                    rp = None
            except requests.RequestException:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def get(self, url: str, params: dict | None = None) -> requests.Response:
        if not self._allowed(url):
            raise PermissionError(f"robots.txt 不允許抓取 {url}")
        wait = self.delay - (time.monotonic() - self._last_request)
        if wait > 0:
            time.sleep(wait)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                self._last_request = time.monotonic()
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(5 * (attempt + 1))
                    last_exc = requests.HTTPError(f"HTTP {r.status_code}")
                    continue
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last_exc = e
                time.sleep(3 * (attempt + 1))
        raise last_exc  # type: ignore[misc]
