"""Cua so chinh: search + queue + results + source viewer + progress."""

from __future__ import annotations

import os

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from crawler.crawler import CrawlConfig, CrawlControl, Crawler, CrawlStats
from database.database import Database
from exporter.exporter import Exporter
from gui.result_table import ResultTable
from gui.search_widget import SearchWidget
from gui.settings import AppSettings, SettingsDialog
from gui.source_viewer import SourceViewer
from models.source import SourceRecord
from utils.logger import get_logger

log = get_logger("gui")


class CrawlWorker(QObject):
    """Chay Crawler trong QThread rieng va bao ket qua ve GUI qua signal."""

    record_ready = Signal(object)
    progress = Signal(object)
    message = Signal(str)
    rate_limited = Signal(object)
    finished = Signal()

    def __init__(self, config: CrawlConfig, database: Database, control: CrawlControl) -> None:
        super().__init__()
        self.config = config
        self.database = database
        self.control = control
        self.crawler: Crawler | None = None

    def run(self) -> None:
        try:
            self.crawler = Crawler(
                self.config,
                database=self.database,
                control=self.control,
                on_record=self.record_ready.emit,
                on_progress=self.progress.emit,
                on_message=self.message.emit,
                on_rate_limited=self.rate_limited.emit,
            )
            self.crawler.run()
        except Exception as exc:
            log.exception("Crawl loi")
            self.message.emit(f"Loi: {exc}")
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    """MQL5 SOURCE CRAWLER - cua so chinh."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MQL5 SOURCE CRAWLER")
        self.resize(1280, 860)

        self.settings = AppSettings.load()
        self.database = Database(self.settings.db_path)
        self.control = CrawlControl()
        self.thread: QThread | None = None
        self.worker: CrawlWorker | None = None

        self.search_widget = SearchWidget()
        self.result_table = ResultTable()
        self.source_viewer = SourceViewer()
        self.queue_list = QListWidget()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel("Pages: 0/0 | Found: 0 | Downloaded: 0 | Skipped: 0 | Errors: 0")

        self._build_ui()
        self._connect()
        self._load_history()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        results_tabs = QTabWidget()
        results_tabs.addTab(self.result_table, "Results")
        results_tabs.addTab(self.queue_list, "Queue")
        results_tabs.addTab(self.log_view, "Log")
        self.results_tabs = results_tabs

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(results_tabs)
        splitter.addWidget(self.source_viewer)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress_bar, 2)
        progress_row.addWidget(self.progress_label, 3)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.search_widget)
        layout.addLayout(progress_row)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._build_menu()
        self.statusBar().showMessage(
            f"SQLite: {os.path.abspath(self.settings.db_path)} | "
            f"{self.database.count()} source da luu"
        )

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        act_settings = QAction("Settings...", self)
        act_settings.triggered.connect(self.open_settings)
        file_menu.addAction(act_settings)
        file_menu.addSeparator()
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        export_menu = self.menuBar().addMenu("&Export")
        for label, handler in (
            ("Export MQ5", self.export_mq5),
            ("Export CSV", self.export_csv),
            ("Export Excel", self.export_excel),
            ("Export JSON", self.export_json),
            ("Export Backtest .set", self.export_backtest),
            ("Export All", self.export_all),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            export_menu.addAction(action)

        help_menu = self.menuBar().addMenu("&Help")
        act_about = QAction("About", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

    def _connect(self) -> None:
        self.search_widget.start_requested.connect(self.start_crawl)
        self.search_widget.pause_requested.connect(self.pause_crawl)
        self.search_widget.resume_requested.connect(self.resume_crawl)
        self.search_widget.stop_requested.connect(self.stop_crawl)
        self.result_table.record_selected.connect(self.source_viewer.show_record)

    def _load_history(self) -> None:
        """Nap lai cac source da luu trong DB de xem offline."""
        records = list(self.database.records())
        for record in records[:200]:
            self.result_table.add_record(record)
        if records:
            self.append_log(f"Da nap {min(len(records), 200)} source tu SQLite.")

    # ------------------------------------------------------------------
    def append_log(self, text: str) -> None:
        self.log_view.appendPlainText(text)

    # ------------------------------------------------------------------
    def start_crawl(self, config: CrawlConfig) -> None:
        if self.thread is not None:
            QMessageBox.information(self, "Crawl", "Dang co phien crawl chay.")
            return
        config.download_dir = self.settings.download_dir
        config.db_path = self.settings.db_path
        config.timeout = self.settings.timeout
        config.retries = self.settings.retries
        config.respect_robots = self.settings.respect_robots
        config.skip_duplicates = self.settings.skip_duplicates

        self.result_table.clear_records()
        self.queue_list.clear()
        self.progress_bar.setValue(0)
        self.append_log(
            f"START keyword={config.keywords or ['(tat ca)']} types={[t.value for t in config.types]} "
            f"pages={config.page_from}-{config.page_to} delay={config.delay}s"
        )

        self.control = CrawlControl()
        self.worker = CrawlWorker(config, self.database, self.control)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.record_ready.connect(self.on_record)
        self.worker.progress.connect(self.on_progress)
        self.worker.message.connect(self.append_log)
        self.worker.rate_limited.connect(self.on_rate_limited)
        self.worker.finished.connect(self.on_finished)
        self.search_widget.set_running(True)
        self.thread.start()

    def pause_crawl(self) -> None:
        self.control.pause()
        self.append_log("PAUSED")

    def resume_crawl(self) -> None:
        self.control.resume()
        self.append_log("RESUMED")

    def stop_crawl(self) -> None:
        self.control.stop()
        self.append_log("STOP da duoc gui, dang ket thuc request hien tai...")

    # ------------------------------------------------------------------
    def on_record(self, record: SourceRecord) -> None:
        self.result_table.update_record(record)
        self.queue_list.addItem(f"[{record.status.value}] {record.name}")
        if record.source_code and not self.source_viewer.record:
            self.source_viewer.show_record(record)

    def on_progress(self, stats: CrawlStats) -> None:
        self.progress_bar.setValue(stats.percent)
        self.progress_label.setText(
            f"Pages: {stats.pages_done}/{stats.pages_total} | Found: {stats.found} | "
            f"Downloaded: {stats.downloaded} | Duplicate: {stats.duplicates} | "
            f"Skipped: {stats.skipped} | N/A: {stats.not_available} | Errors: {stats.errors}"
        )

    def on_rate_limited(self, retry_after: object) -> None:
        extra = f" Retry-After: {retry_after}s." if retry_after else ""
        QMessageBox.warning(
            self,
            "HTTP 429 - Too Many Requests",
            "MQL5.com dang gioi han so request nen tool da dung crawl."
            f"{extra} Hay tang Request delay va thu lai sau.",
        )

    def on_finished(self) -> None:
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        self.thread = None
        self.worker = None
        self.search_widget.set_running(False)
        self.statusBar().showMessage(
            f"Hoan tat. SQLite co {self.database.count()} source. "
            f"Downloads: {os.path.abspath(self.settings.download_dir)}"
        )

    # ------------------------------------------------------------------
    def _records_for_export(self):
        records = self.result_table.records
        return records or self.database.all_records()

    def _exporter(self) -> Exporter:
        return Exporter(self.settings.output_dir)

    def export_csv(self) -> None:
        self._notify_export("CSV", self._exporter().export_csv(self._records_for_export()))

    def export_json(self) -> None:
        self._notify_export("JSON", self._exporter().export_json(self._records_for_export()))

    def export_excel(self) -> None:
        try:
            path = self._exporter().export_excel(self._records_for_export())
        except RuntimeError as exc:
            QMessageBox.warning(self, "Export Excel", str(exc))
            return
        self._notify_export("Excel", path)

    def export_mq5(self) -> None:
        target = QFileDialog.getExistingDirectory(
            self, "Chon thu muc xuat file MQ5", os.path.abspath(self.settings.output_dir)
        )
        if not target:
            return
        exporter = Exporter(target)
        self._notify_export("MQ5", exporter.export_mq5(self._records_for_export()))

    def export_backtest(self) -> None:
        """Tao file .set cho Strategy Tester tu cac source da tai."""
        self._notify_export(
            "Backtest .set", self._exporter().export_backtest_sets(self._records_for_export())
        )

    def export_all(self) -> None:
        out = self._exporter().export_all(self._records_for_export(), self.settings.db_path)
        self._notify_export("All", "\n".join(f"{k}: {v}" for k, v in out.items()))

    def _notify_export(self, label: str, path: str) -> None:
        self.append_log(f"Export {label}: {path}")
        QMessageBox.information(self, f"Export {label}", f"Da xuat:\n{path}")

    # ------------------------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == SettingsDialog.Accepted:
            new_settings = dialog.result_settings()
            db_changed = new_settings.db_path != self.settings.db_path
            self.settings = new_settings
            self.settings.save()
            if db_changed:
                self.database.close()
                self.database = Database(self.settings.db_path)
            self.search_widget.delay.setValue(self.settings.delay)
            self.append_log("Da luu settings.")

    def show_about(self) -> None:
        QMessageBox.information(
            self,
            "About",
            "MQL5 SOURCE CRAWLER\n\n"
            "Thu thap source code MQL5 duoc cong khai tren MQL5.com Code Base.\n"
            "Ton trong robots.txt, khong bypass captcha/login/paywall/anti-bot.\n"
            "Ket qua phan tich chi la static analysis, khong ket luan ve loi nhuan.",
        )

    def closeEvent(self, event) -> None:
        self.control.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait(2000)
        self.database.close()
        super().closeEvent(event)
