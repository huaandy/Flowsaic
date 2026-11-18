"""A polite HTTP client for SAU's public sites (catalog.saumag.edu, www.saumag.edu).

- One request at a time across the whole process (a module-level lock), so the course
  and degree map scrapers never overlap.
- Obeys robots.txt: skips disallowed paths (e.g. /ajax/) and waits its crawl-delay
  (120 s today) between requests, never less than settings.catalog_min_delay_seconds.
- An honest User-Agent that says what we are.
- A bot challenge (AWS WAF "x-amzn-waf-action") or a 403 stops the run. We never try to
  get past bot protection, with a headless browser or otherwise.
"""

import threading
import time
import urllib.robotparser
from collections.abc import Callable

import httpx

from app.config import get_settings

USER_AGENT = "Mozilla/5.0 (compatible; FlowsaicCatalogBot/0.1; student course-planning project)"
ROBOTS_AGENT = "FlowsaicCatalogBot"
TIMEOUT_SECONDS = 30

_request_lock = threading.Lock()
_last_request_at = 0.0  # time.monotonic() of the last request, shared by every client


class CatalogBlocked(RuntimeError):
    """The site refused us (bot challenge, 403) or robots.txt disallows the page."""


class PoliteClient:
    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        min_delay: float | None = None,
        base_url: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.catalog_base_url).rstrip("/")
        self.min_delay = settings.catalog_min_delay_seconds if min_delay is None else min_delay
        self.sleep = sleep
        self.http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            transport=transport,
        )
        self.robots: urllib.robotparser.RobotFileParser | None = None
        self.delay = self.min_delay

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "PoliteClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _wait_turn(self) -> None:
        global _last_request_at
        wait = _last_request_at + self.delay - time.monotonic()
        if _last_request_at and wait > 0:
            self.sleep(wait)
        _last_request_at = time.monotonic()

    def _load_robots(self) -> None:
        robots = urllib.robotparser.RobotFileParser()
        with _request_lock:
            self._wait_turn()
            response = self.http.get(f"{self.base_url}/robots.txt")
        robots.parse(response.text.splitlines() if response.status_code == 200 else [])
        self.robots = robots
        crawl_delay = robots.crawl_delay(ROBOTS_AGENT)
        self.delay = max(self.min_delay, float(crawl_delay or 0))

    def get(self, path: str) -> str:
        """GET a catalog path like '/preview_course_nopop.php?catoid=10&coid=1'. Returns HTML."""
        if self.robots is None:
            self._load_robots()
        url = f"{self.base_url}{path}"
        if not self.robots.can_fetch(ROBOTS_AGENT, url):
            raise CatalogBlocked(f"robots.txt disallows {path.split('?')[0]}")
        with _request_lock:
            self._wait_turn()
            response = self.http.get(url)
        if response.headers.get("x-amzn-waf-action") or response.status_code == 403:
            raise CatalogBlocked(f"bot protection on {path.split('?')[0]} (HTTP {response.status_code})")
        response.raise_for_status()
        return decode(response.content)


def decode(content: bytes) -> str:
    """The catalog says UTF-8 but sometimes sends cp1252 bytes (e.g. a raw 0xA0 nbsp)."""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")
