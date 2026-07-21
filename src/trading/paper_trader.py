"""Paper Trading: simulazione con soldi finti.

Esegue i segnali contro un Portfolio persistente, usando il prezzo di
mercato corrente. Applica una commissione simulata per avvicinarsi
alle condizioni reali di Kraken (taker ~0.26%).
"""
from __future__ import annotations

import logging

from ..models import OrderResult, Signal, SignalType
from .base import Trader
from .portfolio import Portfolio

log = logging.getLogger(__name__)

SIMULATED_FEE = 0.0026  # 0.26% taker


class PaperTrader(Trader):
    mode = "PAPER"

    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    def execute(self, signal: Signal) -> OrderResult:
        price = signal.price
        pair = signal.pair

        if signal.signal_type == SignalType.BUY:
            stake = signal.suggested_stake_eur
            if stake <= 0:
                return self._fail(signal, "Stake suggerito nullo.")
            if stake > self.portfolio.eur:
                stake = self.portfolio.eur  # non andare in negativo
            if stake < 1:
                return self._fail(signal, "Saldo EUR insufficiente per operare.")

            fee = stake * SIMULATED_FEE
            invest = stake - fee
            volume = invest / price
            self.portfolio.record_buy(pair, volume, price, stake)
            log.info("[PAPER] BUY %s vol=%.8f @ %.2f (costo %.2f EUR)", pair, volume, price, stake)
            return OrderResult(
                success=True,
                pair=pair,
                side="buy",
                volume=volume,
                price=price,
                cost_eur=round(stake, 2),
                mode=self.mode,
                order_id="PAPER-" + signal.id,
            )

        if signal.signal_type == SignalType.SELL:
            pos = self.portfolio.get_position(pair)
            if not pos:
                return self._fail(signal, f"Nessuna posizione aperta su {pair} da vendere.")
            volume = pos["volume"]
            gross = volume * price
            fee = gross * SIMULATED_FEE
            proceeds = gross - fee
            self.portfolio.record_sell(pair, volume, price, proceeds)
            log.info("[PAPER] SELL %s vol=%.8f @ %.2f (incasso %.2f EUR)", pair, volume, price, proceeds)
            return OrderResult(
                success=True,
                pair=pair,
                side="sell",
                volume=volume,
                price=price,
                cost_eur=round(proceeds, 2),
                mode=self.mode,
                order_id="PAPER-" + signal.id,
            )

        return self._fail(signal, "Segnale non operativo (HOLD).")

    def _fail(self, signal: Signal, msg: str) -> OrderResult:
        log.warning("[PAPER] Esecuzione fallita %s: %s", signal.pair, msg)
        return OrderResult(
            success=False,
            pair=signal.pair,
            side=signal.signal_type.value.lower(),
            volume=0.0,
            price=signal.price,
            cost_eur=0.0,
            mode=self.mode,
            error=msg,
        )

    def status(self) -> dict:
        s = self.portfolio.summary()
        s["mode"] = self.mode
        return s
