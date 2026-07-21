"""App Flask della dashboard.

Espone:
    GET /                      -> pagina dashboard
    GET /api/overview          -> riepilogo, P&L, obiettivo mensile, equity curve
    GET /api/trades            -> storico operazioni
    GET /api/prices/<pair>     -> OHLC per il grafico prezzi (da Kraken)

Legge i dati dal portafoglio Paper Trading (data/paper_portfolio.json).
In modalita' LIVE mostra il saldo Kraken (senza storico locale dettagliato).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from flask import Flask, jsonify, render_template

from config import settings
from ..kraken import KrakenPublicClient
from ..trading.portfolio import Portfolio
from .analytics import PortfolioAnalytics

log = logging.getLogger(__name__)


def _load_portfolio() -> Portfolio:
    path = os.path.join(settings.data_dir, "paper_portfolio.json")
    return Portfolio(path, initial_eur=settings.initial_budget_eur)


def _current_prices(pairs) -> Dict[str, float]:
    """Prova a leggere i prezzi correnti da Kraken; se fallisce ritorna {}."""
    prices: Dict[str, float] = {}
    client = KrakenPublicClient()
    for pair in pairs:
        try:
            prices[pair] = client.get_price(pair)
        except Exception as exc:  # rete bloccata o coppia errata
            log.debug("Prezzo non disponibile per %s: %s", pair, exc)
    return prices


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/api/overview")
    def api_overview():
        portfolio = _load_portfolio()
        analytics = PortfolioAnalytics(portfolio)

        # Coppie da valorizzare: quelle configurate + quelle con posizioni aperte.
        pairs = set(settings.trading_pairs) | set(portfolio.positions.keys())
        prices = _current_prices(pairs)

        data = analytics.overview(
            current_prices=prices, monthly_target=settings.monthly_target_eur
        )
        data["mode"] = settings.trading_mode
        data["prices_available"] = bool(prices)
        return jsonify(data)

    @app.route("/api/trades")
    def api_trades():
        portfolio = _load_portfolio()
        analytics = PortfolioAnalytics(portfolio)
        return jsonify(analytics.recent_trades(limit=100))

    @app.route("/api/prices/<pair>")
    def api_prices(pair: str):
        client = KrakenPublicClient()
        try:
            candles = client.get_ohlc(pair, "1d")
            series = [
                {"t": c["time"] * 1000, "close": c["close"]}
                for c in candles[-120:]
            ]
            return jsonify({"pair": pair, "series": series, "available": True})
        except Exception as exc:
            log.debug("OHLC non disponibile per %s: %s", pair, exc)
            return jsonify({"pair": pair, "series": [], "available": False, "error": str(exc)})

    @app.route("/api/config")
    def api_config():
        return jsonify(
            {
                "mode": settings.trading_mode,
                "initial_budget_eur": settings.initial_budget_eur,
                "monthly_target_eur": settings.monthly_target_eur,
                "pairs": settings.trading_pairs,
            }
        )

    return app
