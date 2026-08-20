"""Static analysis cho source MQL5."""

from analyzer.classifier import Strategy, classify
from analyzer.detector import detect_features
from analyzer.mq5_parser import SourceStats, analyze_source

__all__ = ["SourceStats", "Strategy", "analyze_source", "classify", "detect_features"]
