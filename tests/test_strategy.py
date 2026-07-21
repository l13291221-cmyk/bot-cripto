"""Test della strategia e del filtro sentiment (allerta rossa)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import (
    IndicatorSnapshot,
    SentimentLabel,
    SentimentReport,
    SignalType,
)
from src.strategy import MonthlyStrategy


def _bullish_snapshot():
    return IndicatorSnapshot(
        pair="XBTEUR",
        price=100.0,
        rsi=30.0,               # ipervenduto -> buy
        macd=1.0,
        macd_signal=0.5,
        macd_hist=0.5,          # momentum rialzista -> buy
        volume=200.0,
        volume_avg=100.0,       # volume alto -> conferma
        ema_fast=105.0,
        ema_slow=100.0,         # trend rialzista -> buy
        pattern="hammer",       # pattern rialzista -> buy
    )


def _bearish_snapshot():
    return IndicatorSnapshot(
        pair="XBTEUR",
        price=100.0,
        rsi=80.0,               # ipercomprato -> sell
        macd=-1.0,
        macd_signal=-0.5,
        macd_hist=-0.5,         # momentum ribassista -> sell
        volume=200.0,
        volume_avg=100.0,
        ema_fast=95.0,
        ema_slow=100.0,         # trend ribassista -> sell
        pattern="shooting_star",
    )


def test_buy_signal_generated():
    strat = MonthlyStrategy()
    sig = strat.generate_signal(_bullish_snapshot(), sentiment=None, available_eur=100.0)
    assert sig.signal_type == SignalType.BUY
    assert sig.confidence > 0
    assert sig.suggested_stake_eur > 0
    assert sig.stop_loss is not None and sig.stop_loss < sig.price
    assert sig.take_profit is not None and sig.take_profit > sig.price


def test_sell_signal_generated():
    strat = MonthlyStrategy()
    sig = strat.generate_signal(_bearish_snapshot(), sentiment=None, available_eur=100.0)
    assert sig.signal_type == SignalType.SELL


def test_red_alert_suspends_signals():
    strat = MonthlyStrategy()
    red = SentimentReport(
        label=SentimentLabel.RED_ALERT,
        score=-0.8,
        red_alert=True,
        headlines=["War escalates, markets crash"],
        reasons=["Allerta rossa di test"],
    )
    sig = strat.generate_signal(_bullish_snapshot(), sentiment=red, available_eur=100.0)
    assert sig.signal_type == SignalType.HOLD
    assert sig.confidence == 0.0


def test_negative_sentiment_reduces_stake():
    strat = MonthlyStrategy()
    neutral = strat.generate_signal(_bullish_snapshot(), sentiment=None, available_eur=100.0)
    negative_report = SentimentReport(
        label=SentimentLabel.NEGATIVE, score=-0.5, red_alert=False,
    )
    negative = strat.generate_signal(
        _bullish_snapshot(), sentiment=negative_report, available_eur=100.0
    )
    assert negative.suggested_stake_eur < neutral.suggested_stake_eur
