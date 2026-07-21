"""Test dell'analytics della dashboard (equity curve, P&L, obiettivo mensile)."""
import datetime as dt
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.trading import Portfolio
from src.web.analytics import PortfolioAnalytics


def _seeded_portfolio():
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.close()
    p = Portfolio(tmp.name, initial_eur=100.0)
    now = time.time()
    # Acquisto e vendita in profitto questo mese.
    p.record_buy("XBTEUR", 0.001, 50000, 50.0)
    p.history[-1]["ts"] = now - 3 * 86400
    p.record_sell("XBTEUR", 0.001, 60000, 55.0)
    p.history[-1]["ts"] = now - 1 * 86400
    # Posizione ancora aperta.
    p.record_buy("ETHEUR", 0.02, 2500, 50.0)
    p.history[-1]["ts"] = now - 12 * 3600
    p._save()
    return p


def test_overview_realized_and_equity():
    p = _seeded_portfolio()
    a = PortfolioAnalytics(p)
    ov = a.overview(current_prices={"ETHEUR": 2500.0}, monthly_target=500.0)

    # Profitto realizzato = 55 (incasso) - 50 (costo) = 5.
    assert ov["realized_total_eur"] == 5.0
    # Una posizione ETH aperta.
    assert len(ov["positions"]) == 1
    assert ov["positions"][0]["pair"] == "ETHEUR"
    # Equity = cassa + valore posizioni.
    assert ov["equity_eur"] > 100.0
    # La curva di equity ha piu' punti.
    assert len(ov["equity_curve"]) >= 3


def test_monthly_target_progress():
    p = _seeded_portfolio()
    a = PortfolioAnalytics(p)
    ov = a.overview(current_prices={}, monthly_target=500.0)

    current_month = dt.datetime.now().strftime("%Y-%m")
    assert ov["month"] == current_month
    # 5 EUR realizzati questo mese su target 500 -> 1%.
    assert ov["realized_this_month_eur"] == 5.0
    assert ov["target_progress_pct"] == 1.0
    assert ov["target_remaining_eur"] == 495.0


def test_recent_trades_sorted_desc():
    p = _seeded_portfolio()
    a = PortfolioAnalytics(p)
    trades = a.recent_trades()
    assert len(trades) == 3
    # Ordine decrescente per timestamp.
    assert trades[0]["ts"] >= trades[-1]["ts"]


def test_unpriced_position_flag():
    p = _seeded_portfolio()
    a = PortfolioAnalytics(p)
    ov = a.overview(current_prices={}, monthly_target=500.0)
    # Senza prezzo corrente la posizione e' valorizzata al costo medio.
    pos = ov["positions"][0]
    assert pos["priced"] is False
    assert pos["current_price"] == pos["avg_cost"]
