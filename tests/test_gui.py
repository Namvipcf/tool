"""Smoke test GUI voi QT_QPA_PLATFORM=offscreen."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from gui.result_table import ResultTable
from gui.search_widget import SearchWidget
from gui.source_viewer import SourceViewer
from models.source import SourceRecord, SourceType, Status


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_search_widget_builds_config(app):
    widget = SearchWidget()
    widget.keyword.setText("Gold, XAUUSD")
    widget.cb_indicator.setChecked(True)
    widget.page_from.setValue(2)
    widget.page_to.setValue(1)  # nho hon page_from -> phai duoc chuan hoa
    config = widget.build_config()
    assert config.keywords == ["gold", "xauusd"]
    assert SourceType.EA in config.types and SourceType.INDICATOR in config.types
    assert config.page_from == 2 and config.page_to == 2
    assert "mq5" in config.extensions


def test_search_widget_running_state(app):
    widget = SearchWidget()
    widget.set_running(True)
    assert not widget.btn_search.isEnabled() and widget.btn_pause.isEnabled()
    widget.set_running(False)
    assert widget.btn_search.isEnabled() and not widget.btn_pause.isEnabled()


def test_result_table_add_and_update(app):
    table = ResultTable()
    record = SourceRecord(source_id="1", name="Gold EA", type=SourceType.EA, status=Status.READY)
    table.add_record(record)
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "Gold EA"

    record.status = Status.DOWNLOADED
    table.update_record(record)
    assert table.rowCount() == 1
    assert table.item(0, 8).text() == "DOWNLOADED"
    table.clear_records()
    assert table.rowCount() == 0


def test_source_viewer_shows_code_and_search(app):
    viewer = SourceViewer()
    record = SourceRecord(
        source_id="1",
        name="Gold EA",
        source_code="void OnTick(){ /* buy */ }\nvoid OnInit(){}",
        status=Status.DOWNLOADED,
    )
    viewer.show_record(record)
    assert "OnTick" in viewer.editor.toPlainText()
    viewer.find_input.setText("OnTick")
    assert viewer.count_matches() == 1
    viewer.replace_input.setText("OnTimer")
    viewer.replace_all()
    assert "OnTimer" in viewer.editor.toPlainText()
    assert "Analysis" in viewer.analysis.text()
