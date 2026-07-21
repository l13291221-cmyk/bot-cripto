"""Test degli indicatori tecnici (nessuna rete)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzer import indicators as ind


def test_sma_basic():
    assert ind.sma([1, 2, 3, 4], 2) == 3.5
    assert ind.sma([1, 2], 5) is None


def test_ema_len():
    series = ind.ema_series([1, 2, 3, 4, 5], 3)
    assert len(series) == 5
    assert series[-1] > series[0]


def test_rsi_all_gains_is_100():
    closes = list(range(1, 30))  # sempre in salita
    assert ind.rsi(closes) == 100.0


def test_rsi_all_losses_low():
    closes = list(range(30, 1, -1))  # sempre in discesa
    val = ind.rsi(closes)
    assert val is not None and val < 5


def test_rsi_none_when_short():
    assert ind.rsi([1, 2, 3]) is None


def test_macd_structure():
    closes = [float(i) for i in range(1, 60)]
    m = ind.macd(closes)
    assert set(m.keys()) == {"macd", "signal", "hist"}
    assert m["macd"] is not None


def test_detect_bullish_engulfing():
    candles = [
        {"open": 10, "high": 10.5, "low": 8.5, "close": 9},   # rossa
        {"open": 8.9, "high": 11, "low": 8.8, "close": 10.5}, # verde che ingloba
    ]
    assert ind.detect_pattern(candles) == "bullish_engulfing"


def test_detect_doji():
    candles = [
        {"open": 10, "high": 10.5, "low": 9.5, "close": 9.8},
        {"open": 10, "high": 11, "low": 9, "close": 10.02},
    ]
    assert ind.detect_pattern(candles) == "doji"
