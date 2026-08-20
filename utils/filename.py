"""Sanitize ten file va xu ly truong hop trung ten."""

from __future__ import annotations

import os
import re

_INVALID = re.compile(r"[^A-Za-z0-9._-]+")
_DASHES = re.compile(r"_{2,}")


def sanitize_filename(name: str, default: str = "source", max_len: int = 120) -> str:
    """Chuyen ten bat ky thanh ten file an toan tren Windows/Linux.

    >>> sanitize_filename("Gold Scalping EA: XAU/USD.mq5")
    'Gold_Scalping_EA_XAU_USD.mq5'
    """
    name = name.strip()
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    stem = _DASHES.sub("_", _INVALID.sub("_", stem)).strip("._-")
    ext = _INVALID.sub("", ext).lower()
    if not stem:
        stem = default
    stem = stem[:max_len]
    return f"{stem}.{ext}" if ext else stem


def unique_path(directory: str, filename: str) -> str:
    """Tra ve duong dan chua ton tai; neu trung thi them _001, _002..."""
    filename = sanitize_filename(filename)
    candidate = os.path.join(directory, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, dot, ext = filename.rpartition(".")
    if not dot:
        stem, ext = filename, ""
    for i in range(1, 1000):
        suffix = f"_{i:03d}"
        new_name = f"{stem}{suffix}.{ext}" if ext else f"{stem}{suffix}"
        candidate = os.path.join(directory, new_name)
        if not os.path.exists(candidate):
            return candidate
    raise RuntimeError(f"Khong tim duoc ten file trong cho {filename}")
