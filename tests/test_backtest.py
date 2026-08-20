"""Test trich xuat thiet lap backtest tu source MQL5."""

from analyzer.backtest import extract_inputs, suggest_setup, summary_text, to_set_content

SOURCE = """
#property description "Gold scalper for XAUUSD on PERIOD_M5, min deposit 1000 USD, leverage 1:500"

input group "Money"
input double Lots = 0.10;          // Lot size
input int    StopLoss = 250;       // SL in points
input string Comment_ = "gold";
sinput bool  UseTrailing = true;
input ENUM_TIMEFRAMES TF = PERIOD_M5;
input int MagicNumber = 20240115;

void OnTick()
{
   double tick = SymbolInfoTick(_Symbol, tick);
}
"""


def test_extract_inputs_reads_name_type_default_comment_group():
    params = extract_inputs(SOURCE)
    names = [p.name for p in params]
    assert names == ["Lots", "StopLoss", "Comment_", "UseTrailing", "TF", "MagicNumber"]
    lots = params[0]
    assert lots.type == "double"
    assert lots.default == "0.10"
    assert lots.comment == "Lot size"
    assert lots.group == "Money"


def test_suggest_setup_detects_symbol_timeframe_deposit():
    setup = suggest_setup(SOURCE)
    assert setup.program == "Expert Advisor"
    assert "XAUUSD" in setup.symbols
    assert "PERIOD_M5" in setup.timeframes
    assert setup.min_deposit == "1000"
    assert setup.leverage == "1:500"
    assert setup.magic == "20240115"
    assert setup.tick_model.startswith("Every tick")
    assert len(setup.inputs) == 6


def test_setup_without_hints_adds_notes():
    setup = suggest_setup("void OnTick() { }")
    assert setup.symbols == []
    assert any("symbol" in note for note in setup.notes)
    assert any("input" in note for note in setup.notes)


def test_set_content_format():
    setup = suggest_setup(SOURCE)
    content = to_set_content(setup, title="Gold EA")
    assert "; Gold EA" in content
    assert "Lots=0.10||0.10||0.01||0.10||N" in content
    assert "StopLoss=250||250||1||250||N" in content
    assert "Comment_=gold" in content
    assert "TF=PERIOD_M5" in content


def test_summary_text_contains_inputs_and_notes():
    text = summary_text(suggest_setup(SOURCE))
    assert "Symbol: XAUUSD" in text
    assert "double Lots = 0.10" in text
