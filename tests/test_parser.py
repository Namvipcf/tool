"""Test parser HTML dua tren fixture lay tu HTML thuc te cua mql5.com."""

from __future__ import annotations

import os

from crawler.parser import has_next_page, matches_keywords, parse_detail, parse_listing
from crawler.search import SearchQuery
from models.source import SourceRecord, SourceType

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def test_parse_listing():
    records = parse_listing(_read("listing.html"))
    assert len(records) == 2
    first = records[0]
    assert first.source_id == "12345"
    assert first.name == "Gold Scalping EA"
    assert first.type is SourceType.EA
    assert first.source_url == "https://www.mql5.com/en/code/12345"
    assert "XAUUSD" in first.description
    assert records[1].type is SourceType.INDICATOR


def test_has_next_page():
    assert has_next_page(_read("listing.html"))
    assert not has_next_page("<html><body></body></html>")


def test_parse_detail():
    record = SourceRecord(source_id="12345", source_url="https://www.mql5.com/en/code/12345")
    parse_detail(_read("detail.html"), record)
    assert record.name.startswith("Gold Scalping EA")
    assert record.author == "Tester Name"
    assert record.views == 1234
    assert record.rating == 4.5
    assert record.votes == 7
    assert record.published.startswith("2026-08-19")
    assert record.type is SourceType.EA
    assert len(record.attachments) == 2
    assert record.attachments[0].extension == "mq5"
    assert record.attachments[0].size == "27.74 KB"
    assert record.file_url.endswith("12345.zip")
    assert record.has_public_source
    assert record.extension == "mq5"


def test_matches_keywords():
    record = SourceRecord(source_id="1", name="Gold Scalping EA", description="XAUUSD M1")
    assert matches_keywords(record, [])
    assert matches_keywords(record, ["gold"])
    assert matches_keywords(record, ["xauusd"])
    assert not matches_keywords(record, ["bitcoin"])


def test_parse_keywords():
    assert SearchQuery.parse_keywords("Gold, XAUUSD Scalping") == ["gold", "xauusd", "scalping"]
    assert SearchQuery.parse_keywords("") == []
    assert SearchQuery.parse_keywords("Gold, gold") == ["gold"]
