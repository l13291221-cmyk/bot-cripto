"""Backtest semplice della strategia su dati storici Kraken.

Scorre le candele giornaliere storiche di una coppia e simula
l'applicazione della strategia (senza filtro notizie, non disponibile
sullo storico) per dare un'idea del comportamento passato.

ATTENZIONE: il passato non predice il futuro. Serve solo a farsi un'idea
della logica, NON e' una garanzia di rendimento.

Uso:
    python backtest.py XBTEUR
    python backtest.py ETHEUR --budget 100
"""
from __future__ import annotations

import argparse

from src.analyzer import indicators as ind
from src.kraken import KrakenPublicClient
from src.models import IndicatorSnapshot
from src.strategy import MonthlyStrategy


def run_backtest(pair: str, budget: float, warmup: int = 60) -> None:
    client = KrakenPublicClient()
    candles = client.get_ohlc(pair, "1d")
    if len(candles) < warmup + 5:
        print(f"Dati insufficienti per {pair} ({len(candles)} candele).")
        return

    strategy = MonthlyStrategy()
    cash = budget
    position_volume = 0.0
    trades = 0

    for i in range(warmup, len(candles)):
        window = candles[: i + 1]
        closes = [c["close"] for c in window]
        volumes = [c["volume"] for c in window]
        price = closes[-1]
        macd_vals = ind.macd(closes)

        snap = IndicatorSnapshot(
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
            pattern=ind.detect_pattern(window),
        )

        # Nessun filtro sentiment sullo storico.
        available = cash
        signal = strategy.generate_signal(snap, sentiment=None, available_eur=available)

        if signal.signal_type.value == "BUY" and position_volume == 0 and signal.suggested_stake_eur >= 1:
            stake = min(signal.suggested_stake_eur, cash)
            fee = stake * 0.0026
            position_volume = (stake - fee) / price
            cash -= stake
            trades += 1
        elif signal.signal_type.value == "SELL" and position_volume > 0:
            gross = position_volume * price
            cash += gross - gross * 0.0026
            position_volume = 0.0
            trades += 1

    final_price = candles[-1]["close"]
    equity = cash + position_volume * final_price
    pnl = equity - budget
    print(f"=== Backtest {pair} ({len(candles)} giorni) ===")
    print(f"Budget iniziale : {budget:.2f} €")
    print(f"Valore finale   : {equity:.2f} €")
    print(f"P&L             : {pnl:+.2f} € ({pnl/budget*100:+.1f}%)")
    print(f"Operazioni      : {trades}")
    print("\nNota: risultato puramente indicativo, senza filtro notizie.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest strategia Bot Cripto")
    parser.add_argument("pair", nargs="?", default="XBTEUR", help="Coppia Kraken (es. XBTEUR)")
    parser.add_argument("--budget", type=float, default=100.0, help="Budget iniziale EUR")
    args = parser.parse_args()
    run_backtest(args.pair, args.budget)


if __name__ == "__main__":
    main()
