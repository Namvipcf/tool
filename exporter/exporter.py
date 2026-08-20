"""Xuat ket qua crawl: file .mq5, CSV, Excel (xlsx), JSON va copy database.

Cau truc output:

    output/
    |-- mq5/
    |   |-- EA_001.mq5
    |-- backtest/
    |   |-- EA_001.set
    |-- metadata.csv
    |-- metadata.xlsx
    |-- metadata.json
    |-- database.db
"""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections.abc import Iterable, Sequence

from analyzer.backtest import suggest_setup, to_set_content
from models.source import SourceRecord
from utils.filename import sanitize_filename, unique_path
from utils.logger import get_logger

log = get_logger("exporter")

CSV_COLUMNS = [
    "source_id",
    "name",
    "author",
    "type",
    "status",
    "filename",
    "extension",
    "source_url",
    "file_url",
    "local_path",
    "sha256",
    "views",
    "rating",
    "votes",
    "published",
    "crawl_time",
    "download_time",
    "platform",
    "description",
]


class Exporter:
    """Xuat danh sach SourceRecord (hoac dict tu DB) ra nhieu dinh dang."""

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    @staticmethod
    def _rows(records: Iterable[SourceRecord | dict]) -> list[dict]:
        rows = []
        for r in records:
            row = r.to_row() if isinstance(r, SourceRecord) else dict(r)
            rows.append({c: row.get(c, "") for c in CSV_COLUMNS})
        return rows

    # ------------------------------------------------------------------
    def export_csv(self, records: Sequence[SourceRecord | dict], filename: str = "metadata.csv") -> str:
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(self._rows(records))
        log.info("Da xuat CSV: %s (%d dong)", path, len(records))
        return path

    def export_json(self, records: Sequence[SourceRecord | dict], filename: str = "metadata.json") -> str:
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._rows(records), fh, ensure_ascii=False, indent=2)
        log.info("Da xuat JSON: %s", path)
        return path

    def export_excel(self, records: Sequence[SourceRecord | dict], filename: str = "metadata.xlsx") -> str:
        try:
            from openpyxl import Workbook
        except ImportError as exc:  # pragma: no cover - phu thuoc tuy chon
            raise RuntimeError("Can cai openpyxl de xuat Excel: pip install openpyxl") from exc

        path = os.path.join(self.output_dir, filename)
        wb = Workbook()
        ws = wb.active
        ws.title = "mq5_sources"
        ws.append(CSV_COLUMNS)
        for row in self._rows(records):
            ws.append([row.get(c, "") for c in CSV_COLUMNS])
        for idx, col in enumerate(CSV_COLUMNS, 1):
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(
                40, max(12, len(col) + 4)
            )
        ws.freeze_panes = "A2"
        wb.save(path)
        log.info("Da xuat Excel: %s", path)
        return path

    def export_mq5(self, records: Sequence[SourceRecord | dict], subdir: str = "mq5") -> str:
        """Copy cac file source da tai vao output/mq5/."""
        target = os.path.join(self.output_dir, subdir)
        os.makedirs(target, exist_ok=True)
        count = 0
        for record in records:
            row = record.to_row() if isinstance(record, SourceRecord) else dict(record)
            src = row.get("local_path") or ""
            if not src or not os.path.exists(src):
                continue
            dest = unique_path(target, os.path.basename(src))
            shutil.copy2(src, dest)
            count += 1
        log.info("Da copy %d file source vao %s", count, target)
        return target

    def export_backtest_sets(
        self, records: Sequence[SourceRecord | dict], subdir: str = "backtest"
    ) -> str:
        """Tao file .set (Strategy Tester) cho tung source da tai ve."""
        target = os.path.join(self.output_dir, subdir)
        os.makedirs(target, exist_ok=True)
        count = 0
        for record in records:
            row = record.to_row() if isinstance(record, SourceRecord) else dict(record)
            src = row.get("local_path") or ""
            if not src or not os.path.exists(src):
                continue
            with open(src, encoding="utf-8", errors="replace") as fh:
                code = fh.read()
            setup = suggest_setup(code, str(row.get("description") or ""))
            stem = os.path.splitext(os.path.basename(src))[0]
            dest = unique_path(target, sanitize_filename(f"{stem}.set"))
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(to_set_content(setup, title=str(row.get("name") or stem)))
            count += 1
        log.info("Da tao %d file .set backtest trong %s", count, target)
        return target

    def export_database(self, db_path: str, filename: str = "database.db") -> str:
        dest = os.path.join(self.output_dir, filename)
        if os.path.abspath(db_path) != os.path.abspath(dest) and os.path.exists(db_path):
            shutil.copy2(db_path, dest)
        return dest

    def export_all(
        self, records: Sequence[SourceRecord | dict], db_path: str | None = None
    ) -> dict[str, str]:
        out = {
            "csv": self.export_csv(records),
            "json": self.export_json(records),
            "mq5": self.export_mq5(records),
            "backtest": self.export_backtest_sets(records),
        }
        try:
            out["xlsx"] = self.export_excel(records)
        except RuntimeError as exc:
            log.warning("%s", exc)
        if db_path:
            out["db"] = self.export_database(db_path)
        return out
