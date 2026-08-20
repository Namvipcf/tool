"""HTTP client co retry, rate limit va kiem tra robots.txt."""

from __future__ import annotations

import threading
import time

import requests

from crawler.rate_limiter import RateLimiter
from utils.logger import get_logger
from utils.robots import RobotsPolicy, get_policy

log = get_logger("http")

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class HttpError(RuntimeError):
    """Loi HTTP khong the phuc hoi sau khi da retry."""


class RateLimitError(HttpError):
    """Website tra HTTP 429 - phai dung crawl."""

    def __init__(self, url: str, retry_after: float | None = None) -> None:
        super().__init__(f"HTTP 429 Too Many Requests: {url}")
        self.url = url
        self.retry_after = retry_after


class RobotsDenied(HttpError):
    """URL bi robots.txt chan - khong duoc phep truy cap."""


class HttpClient:
    """Wrapper quanh requests.Session.

    - Ton trong robots.txt (`respect_robots=True`).
    - Delay giua cac request (RateLimiter).
    - Retry + exponential backoff cho loi tam thoi (5xx, timeout, connection).
    - HTTP 429 duoc nem ra ngoai duoi dang RateLimitError de crawler tu dung.
    """

    def __init__(
        self,
        delay: float = 2.0,
        timeout: int = 30,
        retries: int = 3,
        user_agent: str = DEFAULT_UA,
        respect_robots: bool = True,
        robots: RobotsPolicy | None = None,
        lang: str = "en",
    ) -> None:
        self.timeout = timeout
        self.retries = max(1, retries)
        self.lang = lang
        self.respect_robots = respect_robots
        self.limiter = RateLimiter(delay)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Language": f"{lang},en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        self._robots = robots
        self._robots_lock = threading.Lock()
        self.stop_flag = threading.Event()

    # ------------------------------------------------------------------
    @property
    def robots(self) -> RobotsPolicy:
        if self._robots is None:
            with self._robots_lock:
                if self._robots is None:
                    self._robots = get_policy(self.session.headers.get("User-Agent", ""))
        return self._robots

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        return self.robots.can_fetch(url)

    def set_delay(self, delay: float) -> None:
        self.limiter.set_delay(delay)

    # ------------------------------------------------------------------
    def get(self, url: str, binary: bool = False, allow_redirects: bool = True):
        """Tai `url`. Tra ve str (html) hoac bytes khi `binary=True`."""
        if not self.allowed(url):
            raise RobotsDenied(f"robots.txt khong cho phep tai: {url}")

        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 1):
            if self.stop_flag.is_set():
                raise HttpError("Da dung theo yeu cau nguoi dung")
            self.limiter.wait()
            try:
                resp = self.session.get(
                    url, timeout=self.timeout, allow_redirects=allow_redirects
                )
            except requests.RequestException as exc:
                last_exc = exc
                self._sleep_backoff(attempt, None, f"loi ket noi: {exc}")
                continue

            if resp.status_code == 429:
                retry_after = _retry_after(resp)
                log.error("HTTP 429 tu %s - dung crawl", url)
                raise RateLimitError(url, retry_after)
            if resp.status_code in (403, 401):
                raise HttpError(f"HTTP {resp.status_code} - khong co quyen truy cap: {url}")
            if resp.status_code == 404:
                raise HttpError(f"HTTP 404 - khong tim thay: {url}")
            if 500 <= resp.status_code < 600:
                last_exc = HttpError(f"HTTP {resp.status_code}: {url}")
                self._sleep_backoff(attempt, _retry_after(resp), f"HTTP {resp.status_code}")
                continue

            resp.raise_for_status()
            return resp.content if binary else resp.text

        raise HttpError(f"Khong tai duoc {url} sau {self.retries} lan thu: {last_exc}")

    # ------------------------------------------------------------------
    def _sleep_backoff(self, attempt: int, retry_after: float | None, why: str) -> None:
        wait = self.limiter.backoff(attempt, retry_after)
        log.warning("%s - thu lai lan %d sau %.1fs", why, attempt, wait)
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.stop_flag.is_set():
                return
            time.sleep(0.2)


def _retry_after(resp: requests.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
