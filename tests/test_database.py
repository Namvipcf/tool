"""Test SQLite storage + phat hien trung sha256."""

from __future__ import annotations

from database.database import Database
from models.source import SourceRecord, SourceType, Status


def _record(**kwargs) -> SourceRecord:
    base = {
        "source_id": "12345",
        "name": "Gold EA",
        "author": "Tester",
        "type": SourceType.EA,
        "source_url": "https://www.mql5.com/en/code/12345",
        "filename": "Gold_EA.mq5",
        "extension": "mq5",
        "status": Status.DOWNLOADED,
        "sha256": "a" * 64,
        "views": 100,
    }
    base.update(kwargs)
    return SourceRecord(**base)


def test_insert_and_query(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert(_record())
    assert db.count() == 1
    assert db.exists_hash("a" * 64)
    assert not db.exists_hash("b" * 64)
    assert db.exists_source("12345")
    rows = db.all_records()
    assert rows[0]["name"] == "Gold EA"
    assert rows[0]["status"] == "DOWNLOADED"
    db.close()


def test_duplicate_hash_updates_not_duplicates(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert(_record())
    db.upsert(_record(name="Gold EA v2"))
    assert db.count() == 1
    assert db.all_records()[0]["name"] == "Gold EA v2"
    db.close()


def test_search_and_stats(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert(_record())
    db.upsert(
        _record(
            source_id="2",
            name="RSI Indicator",
            type=SourceType.INDICATOR,
            sha256="b" * 64,
            status=Status.READY,
        )
    )
    assert len(db.search("gold")) == 1
    assert len(db.search(type_="Indicator")) == 1
    assert len(db.search(status="READY")) == 1
    assert db.stats() == {"DOWNLOADED": 1, "READY": 1}
    records = list(db.records())
    assert {r.name for r in records} == {"Gold EA", "RSI Indicator"}
    db.close()
