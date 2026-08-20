"""Parser tinh cho file .mq5/.mqh: dem dong, ham, input, include."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Ham MQL5: [modifier] type name(args) { ... } - bo qua tu khoa dieu khien.
_FUNC_RE = re.compile(
    r"^[ \t]*(?:static\s+|virtual\s+|const\s+)*"
    r"(?:void|int|uint|long|ulong|short|ushort|char|uchar|bool|double|float|string|datetime|color|"
    r"[A-Za-z_]\w*(?:\s*\*)?)\s+&?([A-Za-z_]\w*)\s*\([^;{}]*\)\s*(?:const\s*)?\{",
    re.MULTILINE,
)
_KEYWORDS = {"if", "for", "while", "switch", "return", "else", "do", "catch"}
_INPUT_RE = re.compile(r"^\s*(?:input|sinput)\s+", re.MULTILINE)
_INCLUDE_RE = re.compile(r'^\s*#include\s+[<"]([^>"]+)[>"]', re.MULTILINE)
_PROPERTY_RE = re.compile(r"^\s*#property\s+(\w+)\s*(.*)$", re.MULTILINE)
_CLASS_RE = re.compile(r"^\s*(?:class|struct)\s+([A-Za-z_]\w*)", re.MULTILINE)
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


@dataclass
class SourceStats:
    """Thong ke tinh cua mot file source."""

    lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    functions: int = 0
    inputs: int = 0
    includes: int = 0
    classes: int = 0
    function_names: list[str] = field(default_factory=list)
    include_names: list[str] = field(default_factory=list)
    input_names: list[str] = field(default_factory=list)
    properties: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "lines": self.lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "functions": self.functions,
            "inputs": self.inputs,
            "includes": self.includes,
            "classes": self.classes,
        }


def strip_comments(source: str) -> str:
    """Xoa comment de tranh dem sai (dung cho detector/classifier)."""
    return _COMMENT_RE.sub(" ", source)


def analyze_source(source: str) -> SourceStats:
    """Dem cac thanh phan chinh trong source MQL5."""
    stats = SourceStats()
    lines = source.splitlines()
    stats.lines = len(lines)
    in_block_comment = False
    for raw in lines:
        line = raw.strip()
        if not line:
            stats.blank_lines += 1
            continue
        if in_block_comment:
            stats.comment_lines += 1
            if "*/" in line:
                in_block_comment = False
            continue
        if line.startswith("/*"):
            stats.comment_lines += 1
            if "*/" not in line:
                in_block_comment = True
            continue
        if line.startswith("//"):
            stats.comment_lines += 1
            continue
        stats.code_lines += 1

    clean = strip_comments(source)
    names = [m.group(1) for m in _FUNC_RE.finditer(clean) if m.group(1) not in _KEYWORDS]
    stats.function_names = names
    stats.functions = len(names)

    input_lines = [
        line.strip() for line in clean.splitlines() if _INPUT_RE.match(line)
    ]
    stats.inputs = len(input_lines)
    stats.input_names = [_input_name(line) for line in input_lines]

    stats.include_names = _INCLUDE_RE.findall(clean)
    stats.includes = len(stats.include_names)
    stats.classes = len(_CLASS_RE.findall(clean))
    stats.properties = {m.group(1): m.group(2).strip() for m in _PROPERTY_RE.finditer(source)}
    return stats


def _input_name(line: str) -> str:
    body = line.split("=", 1)[0].rstrip(";").strip()
    return body.split()[-1] if body.split() else ""


def find_matches(source: str, needle: str, case_sensitive: bool = False) -> list[tuple[int, str]]:
    """Tim `needle` trong source, tra ve [(so_dong, noi_dung_dong)]."""
    if not needle:
        return []
    out: list[tuple[int, str]] = []
    target = needle if case_sensitive else needle.lower()
    for idx, line in enumerate(source.splitlines(), 1):
        haystack = line if case_sensitive else line.lower()
        if target in haystack:
            out.append((idx, line))
    return out
