"""Static analysis cho source MQL5."""

from analyzer.backtest import BacktestSetup, InputParam, suggest_setup, to_set_content
from analyzer.classifier import Strategy, classify
from analyzer.detector import detect_features
from analyzer.mq5_parser import SourceStats, analyze_source

__all__ = [
    "BacktestSetup",
    "InputParam",
    "SourceStats",
    "Strategy",
    "analyze_source",
    "classify",
    "detect_features",
    "suggest_setup",
    "to_set_content",
]
