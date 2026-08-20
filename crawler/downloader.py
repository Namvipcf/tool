"""Tai source code public tu MQL5 Code Base.

Chinh sach truy cap (theo robots.txt cua mql5.com):

- `Disallow: /*/code/download/*/` -> link tai tung file (`/en/code/download/<id>/<file>.mq5`)
  KHONG duoc phep cho bot, nen mac dinh tool dung link ZIP tong hop
  (`/en/code/download/<id>.zip`) vi link nay khong bi chan.
- `Disallow: /*/code/viewcode/*` -> khong dung trinh xem code inline cua website.
- Neu ca hai duong dan deu khong kha dung -> tra ve status NOT AVAILABLE,
  tool khong tim cach vuot qua bat ky co che kiem soat truy cap nao.
"""

from __future__ import annotations

import io
import os
import time
import zipfile

from crawler.http_client import HttpClient, HttpError, RobotsDenied
from database.database import Database
from models.source import SourceRecord, Status
from utils.filename import sanitize_filename, unique_path
from utils.hashing import sha256_bytes
from utils.logger import get_logger

log = get_logger("downloader")

TEXT_EXTENSIONS = {"mq5", "mq4", "mqh"}


class Downloader:
    """Tai va luu file source; tinh SHA-256 va bo qua ban trung."""

    def __init__(
        self,
        client: HttpClient,
        download_dir: str = "downloads",
        extensions: list[str] | None = None,
        database: Database | None = None,
        skip_duplicates: bool = True,
    ) -> None:
        self.client = client
        self.download_dir = download_dir
        self.extensions = {e.lower().lstrip(".") for e in (extensions or ["mq5", "mqh"])}
        self.database = database
        self.skip_duplicates = skip_duplicates
        os.makedirs(self.download_dir, exist_ok=True)

    # ------------------------------------------------------------------
    def fetch_files(self, record: SourceRecord) -> dict[str, bytes]:
        """Tra ve dict {ten_file: noi_dung} lay duoc mot cach public."""
        wanted = self._wanted_attachments(record)
        if not wanted and not record.file_url:
            return {}

        if record.file_url.endswith(".zip") and self.client.allowed(record.file_url):
            try:
                blob = self.client.get(record.file_url, binary=True)
                return self._extract_zip(blob)
            except (HttpError, zipfile.BadZipFile) as exc:
                log.warning("Khong lay duoc ZIP %s (%s), thu tung file", record.file_url, exc)

        files: dict[str, bytes] = {}
        for att in wanted:
            if not self.client.allowed(att.url):
                log.info("Bo qua %s: robots.txt khong cho phep", att.url)
                continue
            try:
                files[att.name] = self.client.get(att.url, binary=True)
            except RobotsDenied:
                continue
            except HttpError as exc:
                log.warning("Loi tai %s: %s", att.url, exc)
        return files

    # ------------------------------------------------------------------
    def download(self, record: SourceRecord) -> SourceRecord:
        """Tai source cho `record` va cap nhat status/sha256/local_path."""
        if not record.has_public_source:
            record.status = Status.NOT_AVAILABLE
            record.error = "SOURCE NOT PUBLICLY AVAILABLE"
            log.info("%s: khong co file source public", record.name)
            return record

        try:
            files = self.fetch_files(record)
        except HttpError as exc:
            record.status = Status.ERROR
            record.error = str(exc)
            return record

        files = {n: b for n, b in files.items() if self._ext(n) in self.extensions}
        if not files:
            record.status = Status.NOT_AVAILABLE
            record.error = "SOURCE NOT PUBLICLY AVAILABLE"
            return record

        primary_name = self._pick_primary(files)
        primary_bytes = files[primary_name]
        record.sha256 = sha256_bytes(primary_bytes)
        record.extension = self._ext(primary_name)

        if self.skip_duplicates and self.database and self.database.exists_hash(record.sha256):
            existing = self.database.get_by_hash(record.sha256) or {}
            record.status = Status.DUPLICATE
            record.local_path = existing.get("local_path", "")
            record.filename = existing.get("filename", sanitize_filename(primary_name))
            record.source_code = self._decode(primary_bytes)
            record.error = f"Duplicate source (giong {record.filename})"
            log.info("Trung source (sha256=%s): %s", record.sha256[:12], record.name)
            return record

        target_dir = self.download_dir
        os.makedirs(target_dir, exist_ok=True)
        base_name = record.name or primary_name
        primary_path = unique_path(target_dir, f"{sanitize_filename(base_name).rsplit('.', 1)[0]}.{record.extension}")
        with open(primary_path, "wb") as fh:
            fh.write(primary_bytes)
        record.local_path = primary_path
        record.filename = os.path.basename(primary_path)
        record.source_code = self._decode(primary_bytes)

        extra: list[str] = []
        for name, blob in files.items():
            if name == primary_name:
                continue
            path = unique_path(target_dir, name)
            with open(path, "wb") as fh:
                fh.write(blob)
            extra.append(path)
        record.extra_files = extra
        record.download_time = time.strftime("%Y-%m-%d %H:%M:%S")
        record.status = Status.DOWNLOADED
        log.info("Da luu %s (%d bytes, +%d file phu)", primary_path, len(primary_bytes), len(extra))
        return record

    # ------------------------------------------------------------------
    def _wanted_attachments(self, record: SourceRecord):
        return [a for a in record.attachments if a.extension in TEXT_EXTENSIONS]

    def _extract_zip(self, blob: bytes) -> dict[str, bytes]:
        out: dict[str, bytes] = {}
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = os.path.basename(info.filename)
                if self._ext(name) in TEXT_EXTENSIONS:
                    out[name] = zf.read(info)
        return out

    @staticmethod
    def _ext(name: str) -> str:
        return name.rsplit(".", 1)[-1].lower() if "." in name else ""

    def _pick_primary(self, files: dict[str, bytes]) -> str:
        """File chinh la .mq5/.mq4 lon nhat; neu chi co .mqh thi lay file lon nhat."""
        mains = {n: b for n, b in files.items() if self._ext(n) in {"mq5", "mq4"}}
        pool = mains or files
        return max(pool, key=lambda n: len(pool[n]))

    @staticmethod
    def _decode(blob: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
            try:
                return blob.decode(encoding)
            except UnicodeDecodeError:
                continue
        return blob.decode("utf-8", errors="replace")
