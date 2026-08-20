"""Tim kiem source public tren MQL5 Code Base.

Luu y ve robots.txt cua mql5.com: `Disallow: /*/search*` - endpoint tim kiem
toan site khong duoc phep crawl. Vi vay tool duyet cac trang danh sach Code Base
(duoc phep) roi loc keyword phia client.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from crawler.http_client import HttpClient
from crawler.parser import matches_keywords, parse_listing
from models.source import SourceRecord, SourceType
from utils.logger import get_logger

log = get_logger("search")
BASE = "https://www.mql5.com"
PLATFORMS = ("mt5", "mt4")


@dataclass
class SearchQuery:
    """Tham so tim kiem tu GUI."""

    keywords: list[str] = field(default_factory=list)
    types: list[SourceType] = field(default_factory=lambda: [SourceType.EA])
    platforms: list[str] = field(default_factory=lambda: ["mt5"])
    page_from: int = 1
    page_to: int = 1
    max_results: int = 100
    sort: str = "latest"  # latest | best
    lang: str = "en"

    @staticmethod
    def parse_keywords(text: str) -> list[str]:
        """`"Gold, XAUUSD Scalping"` -> `["gold", "xauusd", "scalping"]`."""
        raw = text.replace(";", ",").replace("\n", ",")
        parts = [p.strip() for chunk in raw.split(",") for p in chunk.split() if p.strip()]
        seen: list[str] = []
        for p in parts:
            low = p.lower()
            if low not in seen:
                seen.append(low)
        return seen


class SearchEngine:
    """Duyet listing Code Base va tra ve cac SourceRecord khop keyword."""

    def __init__(self, client: HttpClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    def listing_url(
        self, platform: str, section: str, page: int, sort: str = "latest", lang: str = "en"
    ) -> str:
        url = f"{BASE}/{lang}/code/{platform}/{section}"
        if sort == "best":
            url += "/best"
        if page > 1:
            url += f"/page{page}"
        return url

    # ------------------------------------------------------------------
    def iter_results(
        self,
        query: SearchQuery,
        on_page: Callable[[int, int, str], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> Iterator[SourceRecord]:
        """Sinh ra cac record khop keyword, khong trung source_id."""
        seen: set[str] = set()
        found = 0
        pages = list(range(max(1, query.page_from), max(query.page_from, query.page_to) + 1))
        targets = [
            (platform, t.section)
            for platform in (query.platforms or ["mt5"])
            for t in (query.types or [SourceType.EA])
        ]
        total_pages = len(pages) * len(targets)
        done_pages = 0

        for platform, section in targets:
            for page in pages:
                if should_stop and should_stop():
                    return
                url = self.listing_url(platform, section, page, query.sort, query.lang)
                done_pages += 1
                if on_page:
                    on_page(done_pages, total_pages, url)
                log.info("Listing %s", url)
                html = self.client.get(url)
                records = parse_listing(html, platform=platform)
                if not records:
                    log.info("Trang trong, bo qua phan con lai cua %s/%s", platform, section)
                    break
                for record in records:
                    if record.source_id in seen:
                        continue
                    seen.add(record.source_id)
                    if not matches_keywords(record, query.keywords):
                        continue
                    yield record
                    found += 1
                    if query.max_results and found >= query.max_results:
                        return
