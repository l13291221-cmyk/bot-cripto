"""Modelli dati condivisi (segnali, ordini, risultati)."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class SentimentLabel(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    RED_ALERT = "RED_ALERT"  # guerra / crollo -> segnali sospesi


@dataclass
class IndicatorSnapshot:
    """Fotografia degli indicatori tecnici per una coppia."""

    pair: str
    price: float
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    volume: Optional[float] = None
    volume_avg: Optional[float] = None
    ema_fast: Optional[float] = None
    ema_slow: Optional[float] = None
    pattern: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SentimentReport:
    label: SentimentLabel
    score: float  # -1 (molto negativo) .. +1 (molto positivo)
    red_alert: bool
    headlines: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["label"] = self.label.value
        return d


@dataclass
class Signal:
    """Un segnale operativo generato dalla strategia."""

    pair: str
    signal_type: SignalType
    price: float
    confidence: float  # 0..1
    reasons: List[str] = field(default_factory=list)
    suggested_stake_eur: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    indicators: Optional[IndicatorSnapshot] = None
    sentiment: Optional[SentimentReport] = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        d = {
            "id": self.id,
            "pair": self.pair,
            "signal_type": self.signal_type.value,
            "price": self.price,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "suggested_stake_eur": self.suggested_stake_eur,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "timestamp": self.timestamp,
        }
        if self.indicators:
            d["indicators"] = self.indicators.to_dict()
        if self.sentiment:
            d["sentiment"] = self.sentiment.to_dict()
        return d

    @property
    def is_actionable(self) -> bool:
        return self.signal_type in (SignalType.BUY, SignalType.SELL)


@dataclass
class OrderResult:
    """Esito di un'esecuzione (paper o live)."""

    success: bool
    pair: str
    side: str
    volume: float
    price: float
    cost_eur: float
    mode: str  # PAPER | LIVE
    order_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)
