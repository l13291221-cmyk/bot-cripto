"""Live Trading: ordini REALI su Kraken via API.

ATTENZIONE: usa denaro vero. Attivo solo con TRADING_MODE=LIVE e chiavi
API valide. Piazza ordini a mercato in base al segnale confermato su
Telegram.
"""
from __future__ import annotations

import logging

from ..kraken import KrakenPrivateClient
from ..kraken.public_client import KrakenError
from ..models import OrderResult, Signal, SignalType
from .base import Trader

log = logging.getLogger(__name__)


class LiveTrader(Trader):
    mode = "LIVE"

    def __init__(self, client: KrakenPrivateClient, validate_only: bool = False):
        """validate_only=True chiede a Kraken di validare senza eseguire."""
        self.client = client
        self.validate_only = validate_only

    def execute(self, signal: Signal) -> OrderResult:
        pair = signal.pair
        price = signal.price

        try:
            if signal.signal_type == SignalType.BUY:
                stake = signal.suggested_stake_eur
                if stake <= 0:
                    return self._fail(signal, "Stake suggerito nullo.")
                eur_balance = self.client.get_eur_balance()
                if stake > eur_balance:
                    stake = eur_balance
                if stake < 1:
                    return self._fail(signal, "Saldo EUR insufficiente su Kraken.")
                volume = stake / price
                result = self.client.add_order(
                    pair=pair,
                    side="buy",
                    volume=volume,
                    ordertype="market",
                    validate=self.validate_only,
                )
                return self._success(signal, "buy", volume, price, stake, result)

            if signal.signal_type == SignalType.SELL:
                # Vendi l'intera posizione dell'asset base.
                base_asset = self._base_asset(pair)
                balance = self.client.get_balance()
                volume = balance.get(base_asset, 0.0)
                if volume <= 0:
                    return self._fail(signal, f"Nessuna quantita' di {base_asset} da vendere.")
                result = self.client.add_order(
                    pair=pair,
                    side="sell",
                    volume=volume,
                    ordertype="market",
                    validate=self.validate_only,
                )
                proceeds = volume * price
                return self._success(signal, "sell", volume, price, proceeds, result)

            return self._fail(signal, "Segnale non operativo (HOLD).")

        except KrakenError as exc:
            return self._fail(signal, f"Errore Kraken: {exc}")
        except Exception as exc:  # pragma: no cover
            return self._fail(signal, f"Errore imprevisto: {exc}")

    # ------------------------------------------------------------------
    @staticmethod
    def _base_asset(pair: str) -> str:
        """Estrae l'asset base dal nome coppia (approssimazione).

        Kraken usa ticker come XBTEUR/XXBTZEUR. Per il saldo l'asset base
        del Bitcoin e' 'XXBT'. Qui gestiamo i casi piu' comuni.
        """
        mapping = {"XBT": "XXBT", "BTC": "XXBT", "ETH": "XETH"}
        base = pair.replace("EUR", "").replace("ZEUR", "").replace("Z", "")
        return mapping.get(base, base)

    def _success(self, signal, side, volume, price, cost, result) -> OrderResult:
        txid = None
        if isinstance(result, dict):
            txids = result.get("txid") or []
            txid = txids[0] if txids else None
        log.info("[LIVE] %s %s vol=%.8f @ ~%.2f txid=%s", side.upper(), signal.pair, volume, price, txid)
        return OrderResult(
            success=True,
            pair=signal.pair,
            side=side,
            volume=volume,
            price=price,
            cost_eur=round(cost, 2),
            mode=self.mode,
            order_id=txid,
        )

    def _fail(self, signal: Signal, msg: str) -> OrderResult:
        log.warning("[LIVE] Esecuzione fallita %s: %s", signal.pair, msg)
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
        try:
            balance = self.client.get_balance()
            return {"mode": self.mode, "balance": balance}
        except KrakenError as exc:
            return {"mode": self.mode, "error": str(exc)}
