"""Dieu phoi toan bo qua trinh crawl: search -> detail -> download -> luu DB."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from analyzer.classifier import classify
from analyzer.detector import detect_features
from analyzer.mq5_parser import analyze_source
from crawler.downloader import Downloader
from crawler.http_client import HttpClient, HttpError, RateLimitError, RobotsDenied
from crawler.parser import parse_detail
from crawler.search import SearchEngine, SearchQuery
from database.database import Database
from models.source import SourceRecord, SourceType, Status
from utils.logger import get_logger

log = get_logger("crawler")


@dataclass
class CrawlConfig:
    """Cau hinh mot lan chay crawl."""

    keywords: list[str] = field(default_factory=list)
    types: list[SourceType] = field(default_factory=lambda: [SourceType.EA])
    platforms: list[str] = field(default_factory=lambda: ["mt5"])
    extensions: list[str] = field(default_factory=lambda: ["mq5", "mqh"])
    page_from: int = 1
    page_to: int = 1
    max_results: int = 100
    sort: str = "latest"
    delay: float = 2.0
    timeout: int = 30
    retries: int = 3
    download: bool = True
    respect_robots: bool = True
    skip_duplicates: bool = True
    download_dir: str = "downloads"
    db_path: str = "output/database.db"
    lang: str = "en"

    def to_query(self) -> SearchQuery:
        return SearchQuery(
            keywords=self.keywords,
            types=self.types,
            platforms=self.platforms,
            page_from=self.page_from,
            page_to=self.page_to,
            max_results=self.max_results,
            sort=self.sort,
            lang=self.lang,
        )


@dataclass
class CrawlStats:
    """So lieu tien do hien thi tren GUI."""

    pages_done: int = 0
    pages_total: int = 0
    found: int = 0
    downloaded: int = 0
    skipped: int = 0
    duplicates: int = 0
    not_available: int = 0
    errors: int = 0

    @property
    def percent(self) -> int:
        if self.pages_total <= 0:
            return 0
        return min(100, int(self.pages_done * 100 / self.pages_total))


class CrawlControl:
    """Co dieu khien Start / Pause / Resume / Stop."""

    def __init__(self) -> None:
        self._resume = threading.Event()
        self._resume.set()
        self._stop = threading.Event()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def stop(self) -> None:
        self._stop.set()
        self._resume.set()

    def reset(self) -> None:
        self._stop.clear()
        self._resume.set()

    @property
    def paused(self) -> bool:
        return not self._resume.is_set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def wait_if_paused(self) -> None:
        while not self._resume.wait(timeout=0.2):
            if self._stop.is_set():
                return


class Crawler:
    """Chay crawl dong bo; GUI goi trong QThread rieng.

    Callback:
        on_record(record)        - moi khi mot record hoan tat
        on_progress(stats)       - moi khi so lieu thay doi
        on_message(text)         - log cho nguoi dung
        on_rate_limited(seconds) - website tra HTTP 429, crawl tu dung
    """

    def __init__(
        self,
        config: CrawlConfig,
        database: Database | None = None,
        control: CrawlControl | None = None,
        on_record: Callable[[SourceRecord], None] | None = None,
        on_progress: Callable[[CrawlStats], None] | None = None,
        on_message: Callable[[str], None] | None = None,
        on_rate_limited: Callable[[float | None], None] | None = None,
    ) -> None:
        self.config = config
        self.control = control or CrawlControl()
        self.stats = CrawlStats()
        self.on_record = on_record
        self.on_progress = on_progress
        self.on_message = on_message
        self.on_rate_limited = on_rate_limited

        self.client = HttpClient(
            delay=config.delay,
            timeout=config.timeout,
            retries=config.retries,
            respect_robots=config.respect_robots,
            lang=config.lang,
        )
        self.database = database or Database(config.db_path)
        self.search = SearchEngine(self.client)
        self.downloader = Downloader(
            self.client,
            download_dir=config.download_dir,
            extensions=config.extensions,
            database=self.database,
            skip_duplicates=config.skip_duplicates,
        )
        self.records: list[SourceRecord] = []

    # ------------------------------------------------------------------
    def _msg(self, text: str) -> None:
        log.info(text)
        if self.on_message:
            self.on_message(text)

    def _progress(self) -> None:
        if self.on_progress:
            self.on_progress(self.stats)

    def _emit(self, record: SourceRecord) -> None:
        self.records.append(record)
        if self.on_record:
            self.on_record(record)

    # ------------------------------------------------------------------
    def run(self) -> list[SourceRecord]:
        """Chay full workflow. Tra ve danh sach record da xu ly."""
        self.control.reset()
        self.client.stop_flag.clear()
        query = self.config.to_query()
        self._msg(
            f"Bat dau crawl: keyword={query.keywords or ['(tat ca)']} "
            f"types={[t.value for t in query.types]} pages={query.page_from}-{query.page_to}"
        )

        def on_page(done: int, total: int, url: str) -> None:
            self.stats.pages_done = done
            self.stats.pages_total = total
            self._msg(f"Trang {done}/{total}: {url}")
            self._progress()

        try:
            for record in self.search.iter_results(
                query, on_page=on_page, should_stop=lambda: self.control.stopped
            ):
                self.control.wait_if_paused()
                if self.control.stopped:
                    self._msg("Da dung theo yeu cau.")
                    break
                self.stats.found += 1
                self.process(record)
                self._progress()
        except RateLimitError as exc:
            self.client.stop_flag.set()
            self._msg(
                "Website tra HTTP 429 (Too Many Requests). Da dung crawl. "
                "Hay tang Request delay roi thu lai sau."
            )
            if self.on_rate_limited:
                self.on_rate_limited(exc.retry_after)
        except HttpError as exc:
            self.stats.errors += 1
            self._msg(f"Loi HTTP: {exc}")
        finally:
            self._progress()
            self._msg(
                f"Ket thuc: found={self.stats.found} downloaded={self.stats.downloaded} "
                f"duplicate={self.stats.duplicates} skipped={self.stats.skipped} "
                f"not_available={self.stats.not_available} errors={self.stats.errors}"
            )
        return self.records

    # ------------------------------------------------------------------
    def process(self, record: SourceRecord) -> SourceRecord:
        """Lay chi tiet, tai source (neu bat), phan tich va luu DB."""
        try:
            html = self.client.get(record.source_url)
            parse_detail(html, record)
        except RobotsDenied as exc:
            record.status = Status.SKIPPED
            record.error = str(exc)
            self.stats.skipped += 1
            self._emit(record)
            return record
        except RateLimitError:
            raise
        except HttpError as exc:
            record.status = Status.ERROR
            record.error = str(exc)
            self.stats.errors += 1
            self._emit(record)
            return record

        if not record.has_public_source:
            record.status = Status.NOT_AVAILABLE
            record.error = "SOURCE NOT PUBLICLY AVAILABLE"
            self.stats.not_available += 1
            self._save(record)
            self._emit(record)
            return record

        if not self.config.download:
            record.status = Status.READY
            self._emit(record)
            return record

        try:
            self.downloader.download(record)
        except RateLimitError:
            raise
        except HttpError as exc:
            record.status = Status.ERROR
            record.error = str(exc)

        if record.status is Status.DOWNLOADED:
            self.stats.downloaded += 1
            self.analyze(record)
        elif record.status is Status.DUPLICATE:
            self.stats.duplicates += 1
        elif record.status is Status.NOT_AVAILABLE:
            self.stats.not_available += 1
        elif record.status is Status.SKIPPED:
            self.stats.skipped += 1
        elif record.status is Status.ERROR:
            self.stats.errors += 1

        self._save(record)
        self._emit(record)
        return record

    # ------------------------------------------------------------------
    def analyze(self, record: SourceRecord) -> dict:
        """Static analysis nhanh de log cho nguoi dung."""
        if not record.source_code:
            return {}
        stats = analyze_source(record.source_code)
        features = detect_features(record.source_code)
        strategies = classify(record.source_code, features)
        self._msg(
            f"{record.filename}: {stats.lines} dong, {stats.functions} ham, "
            f"{stats.inputs} input | {', '.join(s.value for s in strategies)}"
        )
        return {"stats": stats, "features": features, "strategies": strategies}

    def _save(self, record: SourceRecord) -> None:
        if not record.sha256 and record.source_url:
            from utils.hashing import sha256_text

            record.sha256 = sha256_text(f"{record.source_url}|{record.status.value}")
        try:
            self.database.upsert(record)
        except Exception as exc:  # noqa: BLE001 - loi DB khong duoc lam chet crawl
            log.error("Loi luu DB cho %s: %s", record.source_url, exc)
