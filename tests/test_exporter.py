"""Test exporter CSV/JSON/XLSX/MQ5."""

from __future__ import annotations

import csv
import json
import os

from exporter.exporter import Exporter
from models.source import SourceRecord, SourceType, Status


def _record(tmp_path) -> SourceRecord:
    path = tmp_path / "Gold_EA.mq5"
    path.write_text("void OnTick(){}", encoding="utf-8")
    return SourceRecord(
        source_id="12345",
        name="Gold EA",
        author="Tester",
        type=SourceType.EA,
        status=Status.DOWNLOADED,
        filename="Gold_EA.mq5",
        extension="mq5",
        local_path=str(path),
        sha256="a" * 64,
    )


def test_export_csv_json(tmp_path):
    exporter = Exporter(str(tmp_path / "out"))
    records = [_record(tmp_path)]
    csv_path = exporter.export_csv(records)
    json_path = exporter.export_json(records)

    with open(csv_path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["name"] == "Gold EA"
    assert rows[0]["status"] == "DOWNLOADED"

    with open(json_path, encoding="utf-8") as fh:
        data = json.loads(fh.read())
    assert data[0]["source_id"] == "12345"


def test_export_excel_and_mq5(tmp_path):
    exporter = Exporter(str(tmp_path / "out"))
    records = [_record(tmp_path)]
    xlsx = exporter.export_excel(records)
    assert os.path.exists(xlsx)
    target = exporter.export_mq5(records)
    assert os.path.exists(os.path.join(target, "Gold_EA.mq5"))


def test_export_all_with_db(tmp_path):
    db_file = tmp_path / "database.db"
    db_file.write_bytes(b"sqlite")
    exporter = Exporter(str(tmp_path / "out"))
    out = exporter.export_all([_record(tmp_path)], str(db_file))
    assert set(out) >= {"csv", "json", "mq5", "db"}
    assert os.path.exists(out["db"])


def test_export_dict_rows(tmp_path):
    exporter = Exporter(str(tmp_path / "out"))
    path = exporter.export_csv([{"source_id": "7", "name": "From DB"}])
    with open(path, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["name"] == "From DB"
