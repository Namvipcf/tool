"""Phan loai chien luoc cua source MQL5 dua tren dau hieu trong code.

Ket qua chi mang tinh tham khao (static analysis). Neu khong du dau hieu -> Unknown.
Tool khong ket luan ve loi nhuan hay do an toan cua source.
"""

from __future__ import annotations

import re
from enum import Enum

from analyzer.detector import detect_features
from analyzer.mq5_parser import strip_comments


class Strategy(str, Enum):
    TREND_FOLLOWING = "Trend Following"
    SCALPING = "Scalping"
    GRID = "Grid"
    MARTINGALE = "Martingale"
    BREAKOUT = "Breakout"
    MEAN_REVERSION = "Mean Reversion"
    NEWS = "News"
    INDICATOR_BASED = "Indicator Based"
    UNKNOWN = "Unknown"


# Moi chien luoc can it nhat 1 dau hieu ro rang trong source.
STRATEGY_PATTERNS: dict[Strategy, list[str]] = {
    Strategy.TREND_FOLLOWING: [r"\btrend\b", r"\biMA\s*\(", r"\biADX\s*\(", r"\bMODE_EMA\b"],
    Strategy.SCALPING: [r"\bscalp", r"PERIOD_M1\b", r"\btick\s*velocity", r"\bspread\b.*\blimit\b"],
    Strategy.GRID: [r"\bgrid\b", r"GridStep", r"GridSize", r"\bpending\s*grid"],
    Strategy.MARTINGALE: [r"\bmartingale\b", r"LotMultiplier", r"lot\s*\*\s*Multiplier"],
    Strategy.BREAKOUT: [r"\bbreak\s*out\b", r"\bbreakout\b", r"opening\s*range", r"\bORB\b"],
    Strategy.MEAN_REVERSION: [
        r"mean\s*revers",
        r"\biBands\s*\(",
        r"\biRSI\s*\(.*\)\s*[<>]",
        r"overbought",
        r"oversold",
    ],
    Strategy.NEWS: [r"\bnews\b", r"CalendarValueHistory", r"economic\s*calendar"],
}

INDICATOR_CALLS = [
    r"\biMA\s*\(",
    r"\biRSI\s*\(",
    r"\biMACD\s*\(",
    r"\biStochastic\s*\(",
    r"\biBands\s*\(",
    r"\biADX\s*\(",
    r"\biATR\s*\(",
]


def classify(source: str, features: dict[str, bool] | None = None) -> list[Strategy]:
    """Tra ve danh sach chien luoc phat hien duoc; rong -> [Strategy.UNKNOWN]."""
    clean = strip_comments(source)
    features = features or detect_features(source)
    found: list[Strategy] = []
    for strategy, patterns in STRATEGY_PATTERNS.items():
        if any(re.search(p, clean, re.IGNORECASE) for p in patterns):
            found.append(strategy)

    if any(re.search(p, clean, re.IGNORECASE) for p in INDICATOR_CALLS):
        found.append(Strategy.INDICATOR_BASED)

    return found or [Strategy.UNKNOWN]


def classify_names(source: str) -> list[str]:
    return [s.value for s in classify(source)]
