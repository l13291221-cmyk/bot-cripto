"""Test del Paper Trading e del portafoglio persistente."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Signal, SignalType
from src.trading import PaperTrader, Portfolio


def _new_portfolio():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    return Portfolio(tmp.name, initial_eur=100.0)


def test_paper_buy_then_sell_cycle():
    portfolio = _new_portfolio()
    trader = PaperTrader(portfolio)

    buy = Signal(
        pair="XBTEUR", signal_type=SignalType.BUY, price=100.0,
        confidence=1.0, suggested_stake_eur=50.0,
    )
    res = trader.execute(buy)
    assert res.success
    assert res.side == "buy"
    assert portfolio.eur < 100.0            # ha speso EUR
    assert portfolio.get_position("XBTEUR") is not None

    sell = Signal(
        pair="XBTEUR", signal_type=SignalType.SELL, price=110.0, confidence=1.0,
    )
    res2 = trader.execute(sell)
    assert res2.success
    assert res2.side == "sell"
    assert portfolio.get_position("XBTEUR") is None  # posizione chiusa
    # Con prezzo salito da 100 a 110 dovremmo essere sopra il cash iniziale
    # residuo + ricavo (al netto delle fee).
    assert portfolio.eur > 100.0


def test_paper_sell_without_position_fails():
    portfolio = _new_portfolio()
    trader = PaperTrader(portfolio)
    sell = Signal(pair="ETHEUR", signal_type=SignalType.SELL, price=50.0, confidence=1.0)
    res = trader.execute(sell)
    assert not res.success
    assert "posizione" in (res.error or "").lower()


def test_paper_buy_insufficient_balance():
    portfolio = _new_portfolio()
    portfolio.eur = 0.5
    trader = PaperTrader(portfolio)
    buy = Signal(
        pair="XBTEUR", signal_type=SignalType.BUY, price=100.0,
        confidence=1.0, suggested_stake_eur=50.0,
    )
    res = trader.execute(buy)
    assert not res.success


def test_portfolio_persistence():
    portfolio = _new_portfolio()
    path = portfolio.path
    portfolio.record_buy("XBTEUR", 0.5, 100.0, 50.0)
    # Ricarica da disco
    reloaded = Portfolio(path, initial_eur=100.0)
    assert reloaded.eur == 50.0
    assert reloaded.get_position("XBTEUR")["volume"] == 0.5
