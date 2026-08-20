"""Trich xuat thiet lap backtest cho EA tu source .mq5.

Tat ca thong tin o day la **static analysis**: doc input, #property va cac chuoi
trong source. Neu source khong noi ro symbol/timeframe/deposit thi de trong,
khong tu bia gia tri.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from analyzer.mq5_parser import analyze_source, strip_comments

_INPUT_LINE_RE = re.compile(
    r"^\s*(?:input|sinput)\s+(?P<type>[A-Za-z_]\w*(?:\s*\*)?)\s+(?P<name>[A-Za-z_]\w*)"
    r"(?:\s*=\s*(?P<default>[^;]+?))?\s*;\s*(?://\s*(?P<comment>.*))?$",
    re.MULTILINE,
)
_GROUP_RE = re.compile(r'^\s*(?:input|sinput)\s+group\s+"([^"]*)"', re.MULTILINE)
_PERIOD_RE = re.compile(r"\bPERIOD_(MN1|W1|D1|H12|H8|H6|H4|H3|H2|H1|M30|M20|M15|M12|M10|M6|M5|M4|M3|M2|M1)\b")
_CURRENCIES = "USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD|SEK|NOK|SGD|HKD|TRY|ZAR|MXN|PLN"
_SYMBOL_RE = re.compile(
    rf"\b(?:XAU|XAG|XPT|XPD|BTC|ETH|LTC|XRP)(?:{_CURRENCIES})\b"
    rf"|\b(?:{_CURRENCIES})(?:{_CURRENCIES})\b"
    r"|\b(?:US30|US500|USTEC|NAS100|SPX500|GER30|GER40|DAX40|UK100|JP225|WTI|BRENT|NGAS)\b"
)
_DEPOSIT_RE = re.compile(
    r"(?:deposit|balance|capital)\D{0,24}?(\d{2,3}(?:[ ,]\d{3})+|\d{3,7})",
    re.IGNORECASE,
)
_COMMENT_TEXT_RE = re.compile(r"//([^\n]*)|/\*(.*?)\*/", re.DOTALL)
_LEVERAGE_RE = re.compile(r"leverage\D{0,12}1\s*[:/]\s*(\d{1,4})", re.IGNORECASE)
_MAGIC_RE = re.compile(r"magic\w*\s*=\s*(\d{2,12})", re.IGNORECASE)
_NUMBER_RE = re.compile(r"^[-+]?\d+(?:\.\d+)?$")


@dataclass
class InputParam:
    """Mot tham so `input` cua EA (dung cho Strategy Tester)."""

    name: str
    type: str = ""
    default: str = ""
    comment: str = ""
    group: str = ""

    @property
    def is_numeric(self) -> bool:
        return bool(_NUMBER_RE.match(self.default.strip()))

    def set_line(self) -> str:
        """Mot dong trong file .set cua MT5 Strategy Tester."""
        value = self.default.strip().strip('"') or ""
        if not self.is_numeric:
            return f"{self.name}={value}"
        step = "0.01" if "." in value else "1"
        return f"{self.name}={value}||{value}||{step}||{value}||N"


@dataclass
class BacktestSetup:
    """Goi y thiet lap backtest doc ra tu source."""

    program: str = ""
    symbols: list[str] = field(default_factory=list)
    timeframes: list[str] = field(default_factory=list)
    min_deposit: str = ""
    leverage: str = ""
    magic: str = ""
    tick_model: str = ""
    inputs: list[InputParam] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "program": self.program,
            "symbols": ", ".join(self.symbols),
            "timeframes": ", ".join(self.timeframes),
            "min_deposit": self.min_deposit,
            "leverage": self.leverage,
            "magic": self.magic,
            "tick_model": self.tick_model,
            "inputs": len(self.inputs),
        }


def extract_inputs(source: str) -> list[InputParam]:
    """Doc danh sach input (ten, kieu, gia tri mac dinh, comment, group)."""
    groups = [(m.start(), m.group(1)) for m in _GROUP_RE.finditer(source)]
    params: list[InputParam] = []
    for match in _INPUT_LINE_RE.finditer(source):
        name = match.group("name")
        type_ = match.group("type")
        if type_ == "group":
            continue
        current_group = ""
        for pos, label in groups:
            if pos < match.start():
                current_group = label
        params.append(
            InputParam(
                name=name,
                type=type_,
                default=(match.group("default") or "").strip(),
                comment=(match.group("comment") or "").strip(),
                group=current_group,
            )
        )
    return params


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def suggest_setup(source: str, description: str = "") -> BacktestSetup:
    """Tao goi y backtest tu source (+ mo ta bai viet neu co)."""
    clean = strip_comments(source)
    stats = analyze_source(source)
    text = f"{source}\n{description}"

    setup = BacktestSetup()
    if "OnTick" in clean:
        setup.program = "Expert Advisor"
    elif "OnCalculate" in clean:
        setup.program = "Indicator"
    elif "OnStart" in clean:
        setup.program = "Script"
    else:
        setup.program = "Unknown"

    setup.symbols = _unique(_SYMBOL_RE.findall(text))
    setup.timeframes = _unique([f"PERIOD_{m}" for m in _PERIOD_RE.findall(text)])
    # Chi doc deposit tu mo ta bai viet / comment de tranh bat trung so trong code.
    doc_text = "\n".join(
        [
            *((m.group(1) or m.group(2) or "") for m in _COMMENT_TEXT_RE.finditer(source)),
            stats.properties.get("description", ""),
        ]
    )
    deposit = _DEPOSIT_RE.search(description) or _DEPOSIT_RE.search(doc_text)
    if deposit:
        setup.min_deposit = deposit.group(1).replace(" ", ",")
    leverage = _LEVERAGE_RE.search(text)
    if leverage:
        setup.leverage = f"1:{leverage.group(1)}"
    magic = _MAGIC_RE.search(clean)
    if magic:
        setup.magic = magic.group(1)

    if re.search(r"SymbolInfoTick|OnTimer|tick[_ ]?volume", clean, re.IGNORECASE):
        setup.tick_model = "Every tick based on real ticks"
    elif setup.program == "Expert Advisor":
        setup.tick_model = "1 minute OHLC (nhanh) hoac Every tick de kiem tra lai"

    if setup.program == "Expert Advisor" and not setup.symbols:
        setup.notes.append("Source khong ghi ro symbol - chon symbol theo mo ta bai viet.")
    if setup.program == "Expert Advisor" and not setup.timeframes:
        setup.notes.append("Source khong ghi ro timeframe - EA co the dung timeframe cua chart.")
    if re.search(r"\bmartingale\b|Lot\s*\*\s*2|lot\s*\*=\s*2", clean, re.IGNORECASE):
        setup.notes.append("Phat hien tang lot kieu martingale - test voi deposit lon va nhieu giai doan.")
    if re.search(r"\bgrid\b|GridStep", clean, re.IGNORECASE):
        setup.notes.append("Phat hien luoi (grid) - kiem tra drawdown truoc khi dung.")
    if stats.inputs == 0:
        setup.notes.append("Khong co input - khong the toi uu bang Strategy Tester.")
    setup.inputs = extract_inputs(source)
    return setup


def to_set_content(setup: BacktestSetup, title: str = "") -> str:
    """Noi dung file .set nap vao Strategy Tester (Inputs > Load)."""
    lines = [f"; {title}" if title else "; MQL5 Source Crawler"]
    if setup.symbols:
        lines.append(f"; Symbol: {', '.join(setup.symbols)}")
    if setup.timeframes:
        lines.append(f"; Timeframe: {', '.join(setup.timeframes)}")
    if setup.min_deposit:
        lines.append(f"; Deposit: {setup.min_deposit}")
    lines.extend(param.set_line() for param in setup.inputs)
    return "\n".join(lines) + "\n"


def summary_text(setup: BacktestSetup) -> str:
    """Mo ta ngan gon de hien tren GUI."""
    rows = [
        f"Program: {setup.program}",
        f"Symbol: {', '.join(setup.symbols) or '-'}",
        f"Timeframe: {', '.join(setup.timeframes) or '-'}",
        f"Min deposit: {setup.min_deposit or '-'}",
        f"Leverage: {setup.leverage or '-'}",
        f"Magic: {setup.magic or '-'}",
        f"Tick model: {setup.tick_model or '-'}",
        f"Inputs: {len(setup.inputs)}",
    ]
    for param in setup.inputs:
        suffix = f"  // {param.comment}" if param.comment else ""
        rows.append(f"  {param.type} {param.name} = {param.default or '-'}{suffix}")
    rows.extend(f"! {note}" for note in setup.notes)
    return "\n".join(rows)
