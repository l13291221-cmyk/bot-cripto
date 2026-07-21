"""Analyzer: scarica i dati di mercato da Kraken e calcola gli indicatori."""
from __future__ import annotations

import logging
from typing import List, Optional

from ..kraken import KrakenPublicClient
from ..models import IndicatorSnapshot
from . import indicators as ind

log = logging.getLogger(__name__)


class MarketAnalyzer:
    """Produce una IndicatorSnapshot per una coppia su un dato timeframe.

    Per una strategia "su scala mensile" usiamo candele giornaliere (1d):
    con ~200 candele giornaliere abbiamo abbastanza storia per RSI/MACD
    e per valutare il trend di fondo del mese.
    """

    def __init__(self, client: Optional[KrakenPublicClient] = None, interval: str = "1d"):
        self.client = client or KrakenPublicClient()
        self.interval = interval

    def analyze(self, pair: str) -> IndicatorSnapshot:
        candles = self.client.get_ohlc(pair, self.interval)
        if not candles:
            raise ValueError(f"Nessun dato OHLC per {pair}")

        closes: List[float] = [c["close"] for c in candles]
        volumes: List[float] = [c["volume"] for c in candles]
        price = closes[-1]

        macd_vals = ind.macd(closes)

        snapshot = IndicatorSnapshot(
            pair=pair,
            price=price,
            rsi=ind.rsi(closes),
            macd=macd_vals["macd"],
            macd_signal=macd_vals["signal"],
            macd_hist=macd_vals["hist"],
            volume=volumes[-1],
            volume_avg=ind.volume_average(volumes),
            ema_fast=ind.ema(closes, 12),
            ema_slow=ind.ema(closes, 26),
            pattern=ind.detect_pattern(candles),
        )
        log.debug("Snapshot %s: %s", pair, snapshot.to_dict())
        return snapshot

    def analyze_all(self, pairs: List[str]) -> List[IndicatorSnapshot]:
        results = []
        for pair in pairs:
            try:
                results.append(self.analyze(pair))
            except Exception as exc:  # non bloccare le altre coppie
                log.warning("Analisi fallita per %s: %s", pair, exc)
        return results
