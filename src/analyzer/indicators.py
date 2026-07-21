"""Indicatori tecnici in puro Python (nessuna dipendenza da TA-Lib).

Funzioni:
    - sma / ema
    - rsi
    - macd
    - volume_average
    - detect_pattern (pattern a candela di base)
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence


def sma(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema_series(values: Sequence[float], period: int) -> List[float]:
    """Ritorna l'intera serie EMA (stessa lunghezza dei valori validi)."""
    if not values or period <= 0:
        return []
    k = 2 / (period + 1)
    ema_vals: List[float] = []
    prev = values[0]
    for i, v in enumerate(values):
        if i == 0:
            prev = v
        else:
            prev = v * k + prev * (1 - k)
        ema_vals.append(prev)
    return ema_vals


def ema(values: Sequence[float], period: int) -> Optional[float]:
    series = ema_series(values, period)
    return series[-1] if series else None


def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """RSI di Wilder. Ritorna 0..100."""
    if len(closes) < period + 1:
        return None

    gains = 0.0
    losses = 0.0
    # Prima media su 'period' variazioni.
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period

    # Smoothing di Wilder sui restanti valori.
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Dict[str, Optional[float]]:
    """Ritorna {'macd', 'signal', 'hist'}."""
    if len(closes) < slow + signal:
        return {"macd": None, "signal": None, "hist": None}

    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema_series(macd_line, signal)

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return {
        "macd": macd_val,
        "signal": signal_val,
        "hist": macd_val - signal_val,
    }


def volume_average(volumes: Sequence[float], period: int = 20) -> Optional[float]:
    return sma(volumes, period)


def detect_pattern(candles: Sequence[Dict]) -> Optional[str]:
    """Riconosce alcuni pattern a candela di base sull'ultima candela.

    Ritorna un'etichetta ('bullish_engulfing', 'hammer', ...) o None.
    Ogni candela e' un dict con open/high/low/close.
    """
    if len(candles) < 2:
        return None

    prev = candles[-2]
    cur = candles[-1]

    o, c, h, l = cur["open"], cur["close"], cur["high"], cur["low"]
    po, pc = prev["open"], prev["close"]

    body = abs(c - o)
    rng = h - l if h - l > 0 else 1e-9
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    # Bullish / bearish engulfing
    if pc < po and c > o and c >= po and o <= pc:
        return "bullish_engulfing"
    if pc > po and c < o and o >= pc and c <= po:
        return "bearish_engulfing"

    # Hammer (corpo piccolo in alto, lunga ombra inferiore)
    if lower_wick > 2 * body and upper_wick < body and c >= o:
        return "hammer"

    # Shooting star (corpo piccolo in basso, lunga ombra superiore)
    if upper_wick > 2 * body and lower_wick < body and c <= o:
        return "shooting_star"

    # Doji (corpo minuscolo rispetto al range)
    if body <= 0.1 * rng:
        return "doji"

    return None
