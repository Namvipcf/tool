"""Cai dat ung dung (luu bang QSettings) va dialog chinh sua."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

ORG = "MQL5SourceCrawler"
APP = "Crawler"


@dataclass
class AppSettings:
    """Cau hinh nguoi dung, persist qua QSettings."""

    delay: float = 2.0
    timeout: int = 30
    retries: int = 3
    download_dir: str = "downloads"
    output_dir: str = "output"
    db_path: str = "output/database.db"
    respect_robots: bool = True
    skip_duplicates: bool = True
    auto_download: bool = True
    lang: str = "en"

    # ------------------------------------------------------------------
    @classmethod
    def load(cls) -> AppSettings:
        s = QSettings(ORG, APP)
        default = cls()
        return cls(
            delay=float(s.value("delay", default.delay)),
            timeout=int(s.value("timeout", default.timeout)),
            retries=int(s.value("retries", default.retries)),
            download_dir=str(s.value("download_dir", default.download_dir)),
            output_dir=str(s.value("output_dir", default.output_dir)),
            db_path=str(s.value("db_path", default.db_path)),
            respect_robots=_to_bool(s.value("respect_robots", default.respect_robots)),
            skip_duplicates=_to_bool(s.value("skip_duplicates", default.skip_duplicates)),
            auto_download=_to_bool(s.value("auto_download", default.auto_download)),
            lang=str(s.value("lang", default.lang)),
        )

    def save(self) -> None:
        s = QSettings(ORG, APP)
        for key, value in asdict(self).items():
            s.setValue(key, value)
        s.sync()


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class SettingsDialog(QDialog):
    """Dialog chinh sua AppSettings."""

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = settings

        self.delay = QDoubleSpinBox()
        self.delay.setRange(0.5, 60.0)
        self.delay.setSingleStep(0.5)
        self.delay.setSuffix(" s")
        self.delay.setValue(settings.delay)

        self.timeout = QSpinBox()
        self.timeout.setRange(5, 300)
        self.timeout.setSuffix(" s")
        self.timeout.setValue(settings.timeout)

        self.retries = QSpinBox()
        self.retries.setRange(1, 10)
        self.retries.setValue(settings.retries)

        self.download_dir = QLineEdit(settings.download_dir)
        self.output_dir = QLineEdit(settings.output_dir)
        self.db_path = QLineEdit(settings.db_path)

        self.respect_robots = QCheckBox("Ton trong robots.txt (khuyen nghi)")
        self.respect_robots.setChecked(settings.respect_robots)
        self.skip_duplicates = QCheckBox("Bo qua source trung (SHA-256)")
        self.skip_duplicates.setChecked(settings.skip_duplicates)
        self.auto_download = QCheckBox("Tu dong tai source khi crawl")
        self.auto_download.setChecked(settings.auto_download)

        form = QFormLayout()
        form.addRow("Request delay:", self.delay)
        form.addRow("Timeout:", self.timeout)
        form.addRow("Retry:", self.retries)
        form.addRow("Download dir:", self.download_dir)
        form.addRow("Output dir:", self.output_dir)
        form.addRow("SQLite path:", self.db_path)
        form.addRow(self.respect_robots)
        form.addRow(self.skip_duplicates)
        form.addRow(self.auto_download)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        note = QLabel(
            "Tool chi tai source duoc MQL5.com cong khai cho phep va khong vuot qua "
            "captcha/login/paywall hay bat ky co che kiem soat truy cap nao."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def result_settings(self) -> AppSettings:
        return AppSettings(
            delay=self.delay.value(),
            timeout=self.timeout.value(),
            retries=self.retries.value(),
            download_dir=self.download_dir.text().strip() or "downloads",
            output_dir=self.output_dir.text().strip() or "output",
            db_path=self.db_path.text().strip() or "output/database.db",
            respect_robots=self.respect_robots.isChecked(),
            skip_duplicates=self.skip_duplicates.isChecked(),
            auto_download=self.auto_download.isChecked(),
            lang=self.settings.lang,
        )
