"""Engine: orchestra analyzer + sentiment + strategia + trader.

E' il "cervello" richiamato sia dallo scheduler periodico sia dai
comandi manuali del bot Telegram.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from config import Settings
from .analyzer import MarketAnalyzer
from .kraken import KrakenPrivateClient, KrakenPublicClient
from .models import OrderResult, Signal
from .sentiment import NewsSentimentAnalyzer
from .strategy import MonthlyStrategy
from .trading import LiveTrader, PaperTrader, Portfolio

log = logging.getLogger(__name__)


class TradingEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.public = KrakenPublicClient()
        self.analyzer = MarketAnalyzer(self.public, interval="1d")
        self.sentiment_analyzer = NewsSentimentAnalyzer(settings.news_rss_feeds)
        self.strategy = MonthlyStrategy(
            max_position_fraction=settings.max_position_fraction,
            default_stop_loss=settings.default_stop_loss,
            default_take_profit=settings.default_take_profit,
        )

        # Trader: PAPER (default, sicuro) o LIVE.
        if settings.is_live:
            client = KrakenPrivateClient(settings.kraken_api_key, settings.kraken_api_secret)
            self.trader = LiveTrader(client)
            log.warning("MODALITA' LIVE attiva: gli ordini useranno denaro reale.")
        else:
            portfolio_path = os.path.join(settings.data_dir, "paper_portfolio.json")
            portfolio = Portfolio(portfolio_path, initial_eur=settings.initial_budget_eur)
            self.trader = PaperTrader(portfolio)
            log.info("MODALITA' PAPER attiva: simulazione con soldi finti.")

    # ------------------------------------------------------------------
    def available_eur(self) -> float:
        """Capitale EUR disponibile secondo il trader corrente."""
        if isinstance(self.trader, PaperTrader):
            return self.trader.portfolio.eur
        try:
            return self.trader.client.get_eur_balance()
        except Exception:
            return self.settings.initial_budget_eur

    def run_cycle(self) -> List[Signal]:
        """Esegue un ciclo completo di analisi su tutte le coppie.

        Ritorna solo i segnali OPERATIVI (BUY/SELL). Gli HOLD vengono
        scartati (nessuna notifica), tranne quando causati da allerta rossa
        che invece merita di essere segnalata a parte da chi chiama.
        """
        sentiment = self.sentiment_analyzer.analyze()
        log.info("Sentiment: %s (score %.2f, red_alert=%s)",
                 sentiment.label.value, sentiment.score, sentiment.red_alert)

        available = self.available_eur()
        signals: List[Signal] = []

        snapshots = self.analyzer.analyze_all(self.settings.trading_pairs)
        for snap in snapshots:
            signal = self.strategy.generate_signal(snap, sentiment, available)
            if signal.is_actionable:
                signals.append(signal)
            else:
                log.debug("HOLD %s: %s", snap.pair, "; ".join(signal.reasons))

        # Salviamo l'ultimo sentiment per interrogazioni esterne.
        self.last_sentiment = sentiment
        return signals

    def execute_signal(self, signal: Signal) -> OrderResult:
        return self.trader.execute(signal)

    def status(self) -> Dict:
        st = self.trader.status()
        st["target_mensile_eur"] = self.settings.monthly_target_eur
        return st
