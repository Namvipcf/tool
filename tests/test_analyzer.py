"""Test static analysis: parser, detector, classifier."""

from __future__ import annotations

import os

from analyzer.classifier import Strategy, classify
from analyzer.detector import detect_features, program_kind
from analyzer.mq5_parser import analyze_source, find_matches, strip_comments

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ea.mq5")


def _source() -> str:
    with open(FIXTURE, encoding="utf-8") as fh:
        return fh.read()


def test_analyze_source_counts():
    stats = analyze_source(_source())
    assert stats.lines > 40
    assert stats.inputs == 5
    assert stats.includes == 2
    assert "Trade/Trade.mqh" in stats.include_names
    assert {"OnInit", "OnTick", "OnDeinit", "MaValue"} <= set(stats.function_names)
    assert stats.functions == len(stats.function_names)
    assert stats.properties["version"].strip('"') == "1.00"
    assert "Lots" in stats.input_names


def test_strip_comments():
    clean = strip_comments("int a; // comment\n/* block */ int b;")
    assert "comment" not in clean
    assert "block" not in clean
    assert "int b;" in clean


def test_detect_features():
    features = detect_features(_source())
    assert features["Expert Advisor"]
    assert features["CTrade"]
    assert features["Moving Average"]
    assert features["RSI"]
    assert features["Buy"] and features["Sell"]
    assert not features["MACD"]
    assert program_kind(_source()) == "EA"


def test_classify():
    strategies = classify(_source())
    assert Strategy.GRID in strategies
    assert Strategy.TREND_FOLLOWING in strategies
    assert Strategy.INDICATOR_BASED in strategies
    assert Strategy.UNKNOWN not in strategies


def test_classify_unknown():
    assert classify("void OnStart(){ Print(\"hello\"); }") == [Strategy.UNKNOWN]


def test_find_matches():
    matches = find_matches(_source(), "OnTick")
    assert len(matches) == 1
    assert matches[0][0] > 0
    assert find_matches(_source(), "") == []
    assert len(find_matches(_source(), "ontick", case_sensitive=True)) == 0
