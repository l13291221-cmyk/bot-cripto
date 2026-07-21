"""Strategia "su scala mensile".

Combina indicatori tecnici (RSI, MACD, volume, pattern) con il filtro
di Sentiment Analysis sulle notizie. Se e' attiva un'ALLERTA ROSSA
(guerra / crollo) i segnali operativi vengono sospessi (HOLD).

Timeframe: candele giornaliere, valutando il quadro del mese in corso.

NOTA REALISTICA sull'obiettivo di 500 EUR/mese su 100 EUR:
    Significherebbe un +500% mensile, un rendimento non realistico e ad
    altissimo rischio di perdita totale del capitale. Il modulo genera
    segnali basati su criteri tecnici prudenti; il "target" mensile e'
    usato solo per il reporting, NON per forzare operazioni azzardate.
    Vedi README per una discussione onesta delle aspettative.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from ..models import (
    IndicatorSnapshot,
    SentimentReport,
    Signal,
    SignalType,
)

log = logging.getLogger(__name__)


class MonthlyStrategy:
    def __init__(
        self,
        max_position_fraction: float = 0.5,
        default_stop_loss: float = 0.05,
        default_take_profit: float = 0.10,
        rsi_oversold: float = 35.0,
        rsi_overbought: float = 70.0,
    ):
        self.max_position_fraction = max_position_fraction
        self.default_stop_loss = default_stop_loss
        self.default_take_profit = default_take_profit
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    # ------------------------------------------------------------------
    def _score_buy_sell(self, snap: IndicatorSnapshot):
        """Ritorna (buy_score, sell_score, reasons) in base agli indicatori."""
        buy = 0.0
        sell = 0.0
        reasons: List[str] = []

        # --- RSI ---
        if snap.rsi is not None:
            if snap.rsi <= self.rsi_oversold:
                buy += 1.0
                reasons.append(f"RSI {snap.rsi:.0f} in ipervenduto (<{self.rsi_oversold:.0f}).")
            elif snap.rsi >= self.rsi_overbought:
                sell += 1.0
                reasons.append(f"RSI {snap.rsi:.0f} in ipercomprato (>{self.rsi_overbought:.0f}).")

        # --- MACD ---
        if snap.macd is not None and snap.macd_signal is not None:
            if snap.macd > snap.macd_signal and (snap.macd_hist or 0) > 0:
                buy += 1.0
                reasons.append("MACD sopra la linea di segnale (momentum rialzista).")
            elif snap.macd < snap.macd_signal and (snap.macd_hist or 0) < 0:
                sell += 1.0
                reasons.append("MACD sotto la linea di segnale (momentum ribassista).")

        # --- Trend EMA ---
        if snap.ema_fast is not None and snap.ema_slow is not None:
            if snap.ema_fast > snap.ema_slow:
                buy += 0.5
                reasons.append("EMA12 sopra EMA26 (trend di fondo rialzista).")
            else:
                sell += 0.5
                reasons.append("EMA12 sotto EMA26 (trend di fondo ribassista).")

        # --- Volume (conferma) ---
        if snap.volume is not None and snap.volume_avg:
            if snap.volume > snap.volume_avg * 1.3:
                reasons.append("Volume superiore alla media: movimento confermato.")
                # Il volume rafforza il lato gia' prevalente.
                if buy >= sell:
                    buy += 0.5
                else:
                    sell += 0.5

        # --- Pattern a candela ---
        bullish_patterns = {"bullish_engulfing", "hammer"}
        bearish_patterns = {"bearish_engulfing", "shooting_star"}
        if snap.pattern in bullish_patterns:
            buy += 0.5
            reasons.append(f"Pattern rialzista: {snap.pattern}.")
        elif snap.pattern in bearish_patterns:
            sell += 0.5
            reasons.append(f"Pattern ribassista: {snap.pattern}.")

        return buy, sell, reasons

    # ------------------------------------------------------------------
    def generate_signal(
        self,
        snap: IndicatorSnapshot,
        sentiment: Optional[SentimentReport],
        available_eur: float,
    ) -> Signal:
        # 1) Filtro Sentiment: allerta rossa -> nessuna operazione.
        if sentiment and sentiment.red_alert:
            return Signal(
                pair=snap.pair,
                signal_type=SignalType.HOLD,
                price=snap.price,
                confidence=0.0,
                reasons=[
                    "ALLERTA ROSSA sulle notizie (guerra/crollo): segnali sospesi.",
                    *sentiment.reasons,
                ],
                indicators=snap,
                sentiment=sentiment,
            )

        buy, sell, reasons = self._score_buy_sell(snap)

        # Soglia minima per emettere un segnale operativo.
        threshold = 2.0
        max_possible = 3.5

        if buy >= threshold and buy > sell:
            signal_type = SignalType.BUY
            confidence = min(buy / max_possible, 1.0)
        elif sell >= threshold and sell > buy:
            signal_type = SignalType.SELL
            confidence = min(sell / max_possible, 1.0)
        else:
            signal_type = SignalType.HOLD
            confidence = 0.0
            reasons = reasons or ["Nessuna condizione operativa chiara: attendere."]

        # 2) Il sentiment negativo (non rosso) riduce la size di un BUY.
        stake = 0.0
        if signal_type == SignalType.BUY:
            fraction = self.max_position_fraction * confidence
            if sentiment and sentiment.score < -0.2:
                fraction *= 0.5
                reasons.append("Clima notizie negativo: size ridotta prudenzialmente.")
            stake = round(available_eur * fraction, 2)

        stop_loss = None
        take_profit = None
        if signal_type == SignalType.BUY:
            stop_loss = round(snap.price * (1 - self.default_stop_loss), 2)
            take_profit = round(snap.price * (1 + self.default_take_profit), 2)

        return Signal(
            pair=snap.pair,
            signal_type=signal_type,
            price=snap.price,
            confidence=round(confidence, 2),
            reasons=reasons,
            suggested_stake_eur=stake,
            stop_loss=stop_loss,
            take_profit=take_profit,
            indicators=snap,
            sentiment=sentiment,
        )
