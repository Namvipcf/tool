"""Panel tim kiem + bo loc + nut dieu khien crawl."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from crawler.crawler import CrawlConfig
from crawler.search import SearchQuery
from models.source import SourceType


class SearchWidget(QWidget):
    """Nhap keyword, chon loai source, khoang trang, delay va dieu khien crawl."""

    start_requested = Signal(object)  # CrawlConfig
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._paused = False

        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("Gold, XAUUSD, Scalping (de trong = lay tat ca)")
        self.keyword.returnPressed.connect(self._emit_start)

        self.cb_ea = QCheckBox("EA")
        self.cb_ea.setChecked(True)
        self.cb_indicator = QCheckBox("Indicator")
        self.cb_script = QCheckBox("Script")
        self.cb_library = QCheckBox("Library")

        self.cb_mq5 = QCheckBox("MQ5")
        self.cb_mq5.setChecked(True)
        self.cb_mqh = QCheckBox("MQH")
        self.cb_mqh.setChecked(True)

        self.platform = QComboBox()
        self.platform.addItems(["mt5", "mt4", "mt5 + mt4"])

        self.sort = QComboBox()
        self.sort.addItems(["latest", "best"])

        self.page_from = QSpinBox()
        self.page_from.setRange(1, 500)
        self.page_from.setValue(1)
        self.page_to = QSpinBox()
        self.page_to.setRange(1, 500)
        self.page_to.setValue(3)

        self.max_results = QSpinBox()
        self.max_results.setRange(1, 5000)
        self.max_results.setValue(100)

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.5, 60.0)
        self.delay.setSingleStep(0.5)
        self.delay.setValue(2.0)
        self.delay.setSuffix(" s")

        self.auto_download = QCheckBox("Tu dong download source")
        self.auto_download.setChecked(True)

        self.btn_search = QPushButton("SEARCH / START")
        self.btn_search.setObjectName("btnStart")
        self.btn_pause = QPushButton("PAUSE")
        self.btn_stop = QPushButton("STOP")
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)

        self.btn_search.clicked.connect(self._emit_start)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.btn_stop.clicked.connect(self.stop_requested.emit)

        self._build_layout()

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        grid = QGridLayout()
        grid.addWidget(QLabel("Keyword:"), 0, 0)
        grid.addWidget(self.keyword, 0, 1, 1, 5)

        grid.addWidget(QLabel("Source type:"), 1, 0)
        types = QHBoxLayout()
        for cb in (self.cb_ea, self.cb_indicator, self.cb_script, self.cb_library):
            types.addWidget(cb)
        types.addStretch(1)
        types_box = QWidget()
        types_box.setLayout(types)
        grid.addWidget(types_box, 1, 1, 1, 5)

        grid.addWidget(QLabel("Extension:"), 2, 0)
        exts = QHBoxLayout()
        exts.addWidget(self.cb_mq5)
        exts.addWidget(self.cb_mqh)
        exts.addWidget(QLabel("Platform:"))
        exts.addWidget(self.platform)
        exts.addWidget(QLabel("Sort:"))
        exts.addWidget(self.sort)
        exts.addStretch(1)
        ext_box = QWidget()
        ext_box.setLayout(exts)
        grid.addWidget(ext_box, 2, 1, 1, 5)

        grid.addWidget(QLabel("Pages:"), 3, 0)
        grid.addWidget(self.page_from, 3, 1)
        grid.addWidget(QLabel("->"), 3, 2, alignment=Qt.AlignCenter)
        grid.addWidget(self.page_to, 3, 3)
        grid.addWidget(QLabel("Max results:"), 3, 4)
        grid.addWidget(self.max_results, 3, 5)

        grid.addWidget(QLabel("Delay:"), 4, 0)
        grid.addWidget(self.delay, 4, 1)
        grid.addWidget(self.auto_download, 4, 2, 1, 4)

        buttons = QHBoxLayout()
        buttons.addWidget(self.btn_search)
        buttons.addWidget(self.btn_pause)
        buttons.addWidget(self.btn_stop)
        buttons.addStretch(1)

        box = QGroupBox("Search")
        outer = QGridLayout(box)
        outer.addLayout(grid, 0, 0)
        outer.addLayout(buttons, 1, 0)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(box)

    # ------------------------------------------------------------------
    def selected_types(self) -> list[SourceType]:
        out = []
        if self.cb_ea.isChecked():
            out.append(SourceType.EA)
        if self.cb_indicator.isChecked():
            out.append(SourceType.INDICATOR)
        if self.cb_script.isChecked():
            out.append(SourceType.SCRIPT)
        if self.cb_library.isChecked():
            out.append(SourceType.LIBRARY)
        return out or [SourceType.EA]

    def selected_extensions(self) -> list[str]:
        out = []
        if self.cb_mq5.isChecked():
            out += ["mq5", "mq4"]
        if self.cb_mqh.isChecked():
            out.append("mqh")
        return out or ["mq5"]

    def selected_platforms(self) -> list[str]:
        text = self.platform.currentText()
        return ["mt5", "mt4"] if "+" in text else [text]

    def build_config(self, base: CrawlConfig | None = None) -> CrawlConfig:
        config = base or CrawlConfig()
        config.keywords = SearchQuery.parse_keywords(self.keyword.text())
        config.types = self.selected_types()
        config.platforms = self.selected_platforms()
        config.extensions = self.selected_extensions()
        config.page_from = self.page_from.value()
        config.page_to = max(self.page_from.value(), self.page_to.value())
        config.max_results = self.max_results.value()
        config.sort = self.sort.currentText()
        config.delay = self.delay.value()
        config.download = self.auto_download.isChecked()
        return config

    # ------------------------------------------------------------------
    def _emit_start(self) -> None:
        if not self.btn_search.isEnabled():
            return
        self.start_requested.emit(self.build_config())

    def _toggle_pause(self) -> None:
        if self._paused:
            self._paused = False
            self.btn_pause.setText("PAUSE")
            self.resume_requested.emit()
        else:
            self._paused = True
            self.btn_pause.setText("RESUME")
            self.pause_requested.emit()

    def set_running(self, running: bool) -> None:
        self.btn_search.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_stop.setEnabled(running)
        if not running:
            self._paused = False
            self.btn_pause.setText("PAUSE")
