"""SQLite storage cho metadata source MQ5 (table `mq5_sources`)."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterable
from typing import Any

from models.source import SourceRecord, SourceType, Status
from utils.logger import get_logger

log = get_logger("database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS mq5_sources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id     TEXT NOT NULL,
    name          TEXT,
    author        TEXT,
    type          TEXT,
    source_url    TEXT,
    file_url      TEXT,
    filename      TEXT,
    extension     TEXT,
    crawl_time    TEXT,
    download_time TEXT,
    status        TEXT,
    sha256        TEXT,
    description   TEXT,
    published     TEXT,
    views         INTEGER,
    rating        REAL,
    votes         INTEGER,
    platform      TEXT,
    local_path    TEXT,
    UNIQUE(sha256)
);
CREATE INDEX IF NOT EXISTS idx_source_id ON mq5_sources(source_id);
CREATE INDEX IF NOT EXISTS idx_name ON mq5_sources(name);
CREATE INDEX IF NOT EXISTS idx_status ON mq5_sources(status);
"""

COLUMNS = [
    "source_id",
    "name",
    "author",
    "type",
    "source_url",
    "file_url",
    "filename",
    "extension",
    "crawl_time",
    "download_time",
    "status",
    "sha256",
    "description",
    "published",
    "views",
    "rating",
    "votes",
    "platform",
    "local_path",
]


class Database:
    """Wrapper SQLite thread-safe (dung 1 connection + lock)."""

    def __init__(self, path: str = "output/database.db") -> None:
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        log.info("SQLite: %s", os.path.abspath(path))

    # ------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    def upsert(self, record: SourceRecord) -> int:
        """Luu record. Neu sha256 da ton tai thi cap nhat (khong tao ban trung)."""
        row = record.to_row()
        values = [row.get(col) for col in COLUMNS]
        placeholders = ", ".join("?" for _ in COLUMNS)
        updates = ", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "sha256")
        sql = (
            f"INSERT INTO mq5_sources ({', '.join(COLUMNS)}) VALUES ({placeholders}) "
            f"ON CONFLICT(sha256) DO UPDATE SET {updates}"
        )
        with self._lock:
            cur = self.conn.execute(sql, values)
            self.conn.commit()
            return int(cur.lastrowid or 0)

    def exists_hash(self, sha256: str) -> bool:
        if not sha256:
            return False
        with self._lock:
            cur = self.conn.execute("SELECT 1 FROM mq5_sources WHERE sha256=? LIMIT 1", (sha256,))
            return cur.fetchone() is not None

    def exists_source(self, source_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute(
                "SELECT 1 FROM mq5_sources WHERE source_id=? LIMIT 1", (str(source_id),)
            )
            return cur.fetchone() is not None

    def get_by_hash(self, sha256: str) -> dict[str, Any] | None:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM mq5_sources WHERE sha256=?", (sha256,))
            row = cur.fetchone()
            return dict(row) if row else None

    def all_records(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM mq5_sources ORDER BY id DESC")
            return [dict(r) for r in cur.fetchall()]

    def search(self, keyword: str = "", type_: str = "", status: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM mq5_sources WHERE 1=1"
        args: list[Any] = []
        if keyword:
            sql += " AND (name LIKE ? OR description LIKE ? OR author LIKE ?)"
            like = f"%{keyword}%"
            args += [like, like, like]
        if type_:
            sql += " AND type=?"
            args.append(type_)
        if status:
            sql += " AND status=?"
            args.append(status)
        sql += " ORDER BY id DESC"
        with self._lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def count(self) -> int:
        with self._lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM mq5_sources").fetchone()[0])

    def stats(self) -> dict[str, int]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT status, COUNT(*) c FROM mq5_sources GROUP BY status"
            ).fetchall()
        return {r["status"] or "": int(r["c"]) for r in rows}

    def records(self) -> Iterable[SourceRecord]:
        for row in self.all_records():
            yield SourceRecord(
                source_id=row["source_id"],
                name=row["name"] or "",
                author=row["author"] or "",
                type=SourceType(row["type"]) if row["type"] else SourceType.UNKNOWN,
                source_url=row["source_url"] or "",
                file_url=row["file_url"] or "",
                filename=row["filename"] or "",
                extension=row["extension"] or "",
                crawl_time=row["crawl_time"] or "",
                download_time=row["download_time"] or "",
                status=Status(row["status"]) if row["status"] else Status.READY,
                sha256=row["sha256"] or "",
                description=row["description"] or "",
                published=row["published"] or "",
                views=row["views"],
                rating=row["rating"],
                votes=row["votes"],
                platform=row["platform"] or "",
                local_path=row["local_path"] or "",
            )
