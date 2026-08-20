"""Test crawler/downloader/rate limiter voi HTTP client gia lap (khong goi mang)."""

from __future__ import annotations

import io
import os
import threading
import zipfile

from crawler.crawler import CrawlConfig, CrawlControl, Crawler
from crawler.downloader import Downloader
from crawler.http_client import HttpError, RateLimitError
from crawler.rate_limiter import RateLimiter
from crawler.search import SearchEngine, SearchQuery
from database.database import Database
from models.source import SourceRecord, SourceType, Status

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, blob in files.items():
            zf.writestr(name, blob)
    return buf.getvalue()


class FakeClient:
    """HttpClient gia lap: tra ve noi dung theo URL, dem so request."""

    def __init__(self, responses: dict[str, object], denied: set[str] | None = None) -> None:
        self.responses = responses
        self.denied = denied or set()
        self.calls: list[str] = []
        self.stop_flag = threading.Event()

    def set_delay(self, delay: float) -> None:
        pass

    def allowed(self, url: str) -> bool:
        return url not in self.denied

    def get(self, url: str, binary: bool = False, allow_redirects: bool = True):
        self.calls.append(url)
        if url in self.denied:
            raise HttpError(f"robots: {url}")
        if url not in self.responses:
            raise HttpError(f"404 {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


# ----------------------------------------------------------------------
def test_rate_limiter_backoff_grows_and_caps():
    limiter = RateLimiter(delay=2.0, max_backoff=30)
    assert limiter.backoff(1) == 2.0
    assert limiter.backoff(2) == 4.0
    assert limiter.backoff(10) == 30
    assert limiter.backoff(1, retry_after=7) == 7


def test_rate_limiter_wait_respects_delay():
    limiter = RateLimiter(delay=0.05, jitter=0.0)
    limiter.wait()
    slept = limiter.wait()
    assert slept > 0


def test_search_engine_filters_keywords():
    url = "https://www.mql5.com/en/code/mt5/experts"
    client = FakeClient({url: _read("listing.html")})
    engine = SearchEngine(client)
    query = SearchQuery(keywords=["gold"], types=[SourceType.EA], page_from=1, page_to=1)
    results = list(engine.iter_results(query))
    assert [r.source_id for r in results] == ["12345"]
    assert client.calls == [url]


def test_search_engine_respects_max_results():
    url = "https://www.mql5.com/en/code/mt5/experts"
    client = FakeClient({url: _read("listing.html")})
    engine = SearchEngine(client)
    query = SearchQuery(keywords=[], max_results=1)
    assert len(list(engine.iter_results(query))) == 1


def test_downloader_extracts_zip(tmp_path):
    record = SourceRecord(source_id="12345", name="Gold Scalping EA")
    from crawler.parser import parse_detail

    parse_detail(_read("detail.html"), record)
    blob = _zip_bytes({"Gold_Scalping_EA.mq5": b"// code\nvoid OnTick(){}", "Helper.mqh": b"// helper"})
    client = FakeClient({record.file_url: blob})
    db = Database(str(tmp_path / "db.sqlite"))
    downloader = Downloader(client, download_dir=str(tmp_path / "dl"), extensions=["mq5", "mqh"], database=db)

    downloader.download(record)
    assert record.status is Status.DOWNLOADED
    assert record.sha256
    assert os.path.exists(record.local_path)
    assert record.source_code.startswith("// code")
    assert len(record.extra_files) == 1
    db.close()


def test_downloader_marks_not_available(tmp_path):
    record = SourceRecord(source_id="1", name="No source")
    downloader = Downloader(FakeClient({}), download_dir=str(tmp_path))
    downloader.download(record)
    assert record.status is Status.NOT_AVAILABLE
    assert "NOT PUBLICLY AVAILABLE" in record.error


def test_downloader_detects_duplicate(tmp_path):
    from crawler.parser import parse_detail

    blob = _zip_bytes({"Gold_Scalping_EA.mq5": b"void OnTick(){}"})
    db = Database(str(tmp_path / "db.sqlite"))
    downloader_dir = str(tmp_path / "dl")

    first = SourceRecord(source_id="12345", name="Gold Scalping EA")
    parse_detail(_read("detail.html"), first)
    client = FakeClient({first.file_url: blob})
    downloader = Downloader(client, download_dir=downloader_dir, database=db)
    downloader.download(first)
    db.upsert(first)

    second = SourceRecord(source_id="99999", name="Gold Scalping EA Copy")
    parse_detail(_read("detail.html"), second)
    downloader.download(second)
    assert second.status is Status.DUPLICATE
    assert second.sha256 == first.sha256
    db.close()


def test_downloader_skips_robots_denied_files(tmp_path):
    from crawler.parser import parse_detail

    record = SourceRecord(source_id="12345", name="Gold Scalping EA")
    parse_detail(_read("detail.html"), record)
    denied = {record.file_url} | {a.url for a in record.attachments}
    client = FakeClient({}, denied=denied)
    downloader = Downloader(client, download_dir=str(tmp_path))
    downloader.download(record)
    assert record.status is Status.NOT_AVAILABLE


def test_crawler_full_flow(tmp_path, monkeypatch):
    listing_url = "https://www.mql5.com/en/code/mt5/experts"
    detail_url = "https://www.mql5.com/en/code/12345"
    zip_url = "https://www.mql5.com/en/code/download/12345.zip"
    source = _read("sample_ea.mq5").encode()
    client = FakeClient(
        {
            listing_url: _read("listing.html"),
            detail_url: _read("detail.html"),
            zip_url: _zip_bytes({"Gold_Scalping_EA.mq5": source}),
        }
    )
    config = CrawlConfig(
        keywords=["gold"],
        page_from=1,
        page_to=1,
        download_dir=str(tmp_path / "dl"),
        db_path=str(tmp_path / "db.sqlite"),
        delay=0,
    )
    db = Database(config.db_path)
    crawler = Crawler(config, database=db)
    crawler.client = client
    crawler.search.client = client
    crawler.downloader.client = client

    records = crawler.run()
    assert len(records) == 1
    record = records[0]
    assert record.status is Status.DOWNLOADED
    assert crawler.stats.downloaded == 1
    assert db.count() == 1
    assert os.path.exists(record.local_path)
    db.close()


def test_crawler_stops_on_http_429(tmp_path):
    listing_url = "https://www.mql5.com/en/code/mt5/experts"
    client = FakeClient({listing_url: RateLimitError(listing_url, retry_after=30)})
    config = CrawlConfig(page_from=1, page_to=1, db_path=str(tmp_path / "db.sqlite"), delay=0)
    db = Database(config.db_path)
    seen: list[float | None] = []
    crawler = Crawler(config, database=db, on_rate_limited=seen.append)
    crawler.client = client
    crawler.search.client = client
    crawler.run()
    assert seen == [30]
    db.close()


def test_crawl_control_pause_stop():
    control = CrawlControl()
    assert not control.paused and not control.stopped
    control.pause()
    assert control.paused
    control.resume()
    assert not control.paused
    control.stop()
    assert control.stopped
    control.wait_if_paused()  # khong treo khi da stop
    control.reset()
    assert not control.stopped
