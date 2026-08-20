"""Bang ket qua crawl."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from models.source import SourceRecord, Status

COLUMNS = ["#", "Name", "Type", "Author", "MQ5", "Views", "Rating", "URL", "Status"]

STATUS_COLORS = {
    Status.READY: "#eef4ff",
    Status.DOWNLOADED: "#e6f7e6",
    Status.SKIPPED: "#fff6e0",
    Status.NOT_AVAILABLE: "#f2f2f2",
    Status.DUPLICATE: "#fdf0ff",
    Status.ERROR: "#ffe6e6",
}


class ResultTable(QTableWidget):
    """Hien thi cac SourceRecord; phat tin hieu khi nguoi dung chon 1 dong."""

    record_selected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(COLUMNS), parent)
        self.setHorizontalHeaderLabels(COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.Interactive)
        self.setColumnWidth(7, 260)
        self._records: list[SourceRecord] = []
        self.itemSelectionChanged.connect(self._on_selection)

    # ------------------------------------------------------------------
    @property
    def records(self) -> list[SourceRecord]:
        return list(self._records)

    def clear_records(self) -> None:
        self._records.clear()
        self.setRowCount(0)

    def add_record(self, record: SourceRecord) -> int:
        row = self.rowCount()
        self.insertRow(row)
        self._records.append(record)
        self._fill_row(row, record)
        return row

    def update_record(self, record: SourceRecord) -> None:
        for row, existing in enumerate(self._records):
            if existing.source_id == record.source_id:
                self._records[row] = record
                self._fill_row(row, record)
                return
        self.add_record(record)

    def selected_record(self) -> SourceRecord | None:
        rows = {i.row() for i in self.selectedIndexes()}
        if not rows:
            return None
        row = min(rows)
        return self._records[row] if 0 <= row < len(self._records) else None

    # ------------------------------------------------------------------
    def _fill_row(self, row: int, record: SourceRecord) -> None:
        values = [
            str(row + 1),
            record.name,
            record.type.value,
            record.author,
            "Yes" if record.has_public_source else "No",
            "" if record.views is None else str(record.views),
            "" if record.rating is None else f"{record.rating:.1f}",
            record.source_url,
            record.status.value,
        ]
        color = QColor(STATUS_COLORS.get(record.status, "#ffffff"))
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col in (0, 4, 5, 6, 8):
                item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(color)
            if record.error:
                item.setToolTip(record.error)
            self.setItem(row, col, item)

    def _on_selection(self) -> None:
        record = self.selected_record()
        if record is not None:
            self.record_selected.emit(record)
