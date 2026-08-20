"""Phat hien thanh phan ky thuat trong source MQL5 (dua tren noi dung thuc te)."""

from __future__ import annotations

import re

from analyzer.mq5_parser import strip_comments

# Moi feature: ten -> danh sach regex dau hieu.
FEATURE_PATTERNS: dict[str, list[str]] = {
    "Expert Advisor": [r"\bOnTick\s*\(", r"#property\s+.*expert"],
    "Indicator": [r"\bOnCalculate\s*\(", r"#property\s+indicator_"],
    "Script": [r"\bOnStart\s*\("],
    "Library": [r"#property\s+library"],
    "CTrade": [r"\bCTrade\b"],
    "OrderSend": [r"\bOrderSend\s*\(", r"\bOrderSendAsync\s*\("],
    "PositionOpen": [r"\.Buy\s*\(", r"\.Sell\s*\(", r"\bPositionOpen\b"],
    "Buy": [r"\bORDER_TYPE_BUY\b", r"\.Buy\s*\(", r"\bOP_BUY\b"],
    "Sell": [r"\bORDER_TYPE_SELL\b", r"\.Sell\s*\(", r"\bOP_SELL\b"],
    "Moving Average": [r"\biMA\s*\(", r"\bMODE_SMA\b", r"\bMODE_EMA\b", r"MovingAverage"],
    "RSI": [r"\biRSI\s*\(", r"\bRSI\b"],
    "MACD": [r"\biMACD\s*\(", r"\bMACD\b"],
    "Bollinger Bands": [r"\biBands\s*\(", r"Bollinger"],
    "Stochastic": [r"\biStochastic\s*\("],
    "ATR": [r"\biATR\s*\("],
    "ADX": [r"\biADX\s*\("],
    "Grid": [r"\bgrid\b", r"GridStep", r"GridSize"],
    "Martingale": [r"\bmartingale\b", r"Multiplier\s*\*", r"LotMultiplier"],
    "Stop Loss": [r"\bStopLoss\b", r"\bSL\b", r"\bsl\s*="],
    "Take Profit": [r"\bTakeProfit\b", r"\bTP\b", r"\btp\s*="],
    "Trailing Stop": [r"[Tt]railing"],
    "Timer": [r"\bOnTimer\s*\(", r"EventSetTimer"],
    "Trade Events": [r"\bOnTrade(Transaction)?\s*\("],
    "Chart Objects": [r"\bObjectCreate\s*\("],
    "File I/O": [r"\bFileOpen\s*\("],
    "WebRequest": [r"\bWebRequest\s*\("],
    "DLL Import": [r"#import\s"],
    "Machine Learning / AI": [r"\bONNX", r"OnnxRun", r"\bneural", r"\bAI\b"],
    "News Filter": [r"\bnews\b", r"CalendarValue"],
    "Hedging": [r"\bhedg"],
    "Multi Symbol": [r"SymbolsTotal\s*\(", r"SymbolSelect\s*\("],
    "Multi Timeframe": [r"PERIOD_(M5|M15|M30|H1|H4|D1|W1|MN1)"],
    "Risk Management": [r"AccountInfoDouble\s*\(", r"RiskPercent", r"\brisk\b"],
}


def detect_features(source: str) -> dict[str, bool]:
    """Tra ve dict {feature: co/khong} dua tren regex tren source (da bo comment)."""
    clean = strip_comments(source)
    result: dict[str, bool] = {}
    for feature, patterns in FEATURE_PATTERNS.items():
        result[feature] = any(re.search(p, clean, re.IGNORECASE) for p in patterns)
    return result


def detected_list(source: str) -> list[str]:
    """Chi tra ve cac feature duoc phat hien."""
    return [name for name, ok in detect_features(source).items() if ok]


def program_kind(source: str) -> str:
    """Suy ra loai chuong trinh tu entry point (EA / Indicator / Script / Library)."""
    features = detect_features(source)
    if features.get("Expert Advisor"):
        return "EA"
    if features.get("Indicator"):
        return "Indicator"
    if features.get("Script"):
        return "Script"
    if features.get("Library"):
        return "Library"
    return "Unknown"
