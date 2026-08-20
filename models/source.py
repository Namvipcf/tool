"""Data model cho mot source MQL5 thu thap tu MQL5.com Code Base."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum


class SourceType(str, Enum):
    EA = "EA"
    INDICATOR = "Indicator"
    SCRIPT = "Script"
    LIBRARY = "Library"
    UNKNOWN = "Unknown"

    @classmethod
    def from_site_label(cls, label: str) -> SourceType:
        text = (label or "").strip().lower()
        mapping = {
            "expert": cls.EA,
            "experts": cls.EA,
            "expert advisor": cls.EA,
            "indicator": cls.INDICATOR,
            "indicators": cls.INDICATOR,
            "script": cls.SCRIPT,
            "scripts": cls.SCRIPT,
            "library": cls.LIBRARY,
            "libraries": cls.LIBRARY,
        }
        return mapping.get(text, cls.UNKNOWN)

    @property
    def section(self) -> str:
        """Ten segment tuong ung tren mql5.com/en/code/<platform>/<section>."""
        return {
            SourceType.EA: "experts",
            SourceType.INDICATOR: "indicators",
            SourceType.SCRIPT: "scripts",
            SourceType.LIBRARY: "libraries",
        }.get(self, "experts")


class Status(str, Enum):
    READY = "READY"
    DOWNLOADED = "DOWNLOADED"
    SKIPPED = "SKIPPED"
    NOT_AVAILABLE = "NOT AVAILABLE"
    DUPLICATE = "DUPLICATE"
    ERROR = "ERROR"


@dataclass
class Attachment:
    """File dinh kem tren trang code."""

    name: str
    url: str
    size: str = ""

    @property
    def extension(self) -> str:
        return self.name.rsplit(".", 1)[-1].lower() if "." in self.name else ""


@dataclass
class SourceRecord:
    """Metadata + noi dung cua mot source code public tren MQL5 Code Base."""

    source_id: str
    name: str = ""
    author: str = ""
    type: SourceType = SourceType.UNKNOWN
    source_url: str = ""
    file_url: str = ""
    filename: str = ""
    extension: str = ""
    crawl_time: str = ""
    download_time: str = ""
    status: Status = Status.READY
    sha256: str = ""
    description: str = ""
    published: str = ""
    views: int | None = None
    rating: float | None = None
    votes: int | None = None
    platform: str = ""
    local_path: str = ""
    source_code: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    error: str = ""

    def __post_init__(self) -> None:
        if not self.crawl_time:
            self.crawl_time = time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def has_public_source(self) -> bool:
        """True neu trang co it nhat mot file .mq5/.mq4/.mqh tai duoc cong khai.

        Record doc lai tu SQLite khong con danh sach attachments, nen dua vao
        extension cua file da luu.
        """
        sources = {"mq5", "mq4", "mqh"}
        if any(a.extension in sources for a in self.attachments):
            return True
        return bool(self.local_path) and self.extension in sources

    def to_row(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        d["status"] = self.status.value
        d["attachments"] = "; ".join(a.url for a in self.attachments)
        d["extra_files"] = "; ".join(self.extra_files)
        d.pop("source_code", None)
        return d
