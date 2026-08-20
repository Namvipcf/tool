"""Doc va ap dung robots.txt cua mql5.com (co ho tro wildcard * va $).

Python `urllib.robotparser` xu ly khong day du cac pattern dang `/*/code/download/*/`
ma mql5.com dung, nen module nay tu match pattern bang regex.
"""

from __future__ import annotations

import contextlib
import re
import time
from urllib.parse import urlsplit

import requests

from utils.logger import get_logger

log = get_logger("robots")
ROBOTS_URL = "https://www.mql5.com/robots.txt"


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    out = []
    for ch in pattern:
        if ch == "*":
            out.append(".*")
        elif ch == "$":
            out.append("$")
        else:
            out.append(re.escape(ch))
    return re.compile("^" + "".join(out))


class RobotsPolicy:
    """Luu rule cho user-agent `*` va tra loi cau hoi co duoc phep fetch URL."""

    def __init__(self, text: str = "") -> None:
        self.allow: list[re.Pattern[str]] = []
        self.disallow: list[re.Pattern[str]] = []
        self.crawl_delay: float | None = None
        self.loaded = False
        if text:
            self.parse(text)

    # ------------------------------------------------------------------
    def parse(self, text: str) -> RobotsPolicy:
        in_star = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                in_star = value == "*"
                continue
            if not in_star or not value:
                continue
            if key == "disallow":
                self.disallow.append(_pattern_to_regex(value))
            elif key == "allow":
                self.allow.append(_pattern_to_regex(value))
            elif key == "crawl-delay":
                with contextlib.suppress(ValueError):
                    self.crawl_delay = float(value)
        self.loaded = True
        return self

    # ------------------------------------------------------------------
    @classmethod
    def fetch(cls, url: str = ROBOTS_URL, timeout: int = 15, user_agent: str = "") -> RobotsPolicy:
        headers = {"User-Agent": user_agent} if user_agent else {}
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            log.info("Da tai robots.txt (%d bytes)", len(resp.content))
            return cls(resp.text)
        except Exception as exc:  # noqa: BLE001 - khong duoc de crawler chet vi robots
            log.warning("Khong tai duoc robots.txt (%s) - se mac dinh cho phep", exc)
            policy = cls()
            policy.loaded = False
            return policy

    # ------------------------------------------------------------------
    def can_fetch(self, url: str) -> bool:
        """Rule chuan robots: `Allow` khop cu the hon se thang `Disallow`."""
        if not self.loaded:
            return True
        parts = urlsplit(url)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        best_disallow = max(
            (len(m.group(0)) for p in self.disallow if (m := p.match(path))), default=-1
        )
        if best_disallow < 0:
            return True
        best_allow = max((len(m.group(0)) for p in self.allow if (m := p.match(path))), default=-1)
        return best_allow >= best_disallow

    def reason(self, url: str) -> str:
        return "" if self.can_fetch(url) else f"robots.txt khong cho phep truy cap {url}"


_CACHED: tuple[float, RobotsPolicy] | None = None
_TTL = 3600.0


def get_policy(user_agent: str = "", force: bool = False) -> RobotsPolicy:
    """Tra ve policy da cache (1 gio)."""
    global _CACHED
    now = time.time()
    if force or _CACHED is None or now - _CACHED[0] > _TTL:
        _CACHED = (now, RobotsPolicy.fetch(user_agent=user_agent))
    return _CACHED[1]
