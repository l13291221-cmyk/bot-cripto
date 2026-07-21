"""Punto di ingresso del Bot Cripto.

Uso:
    python main.py            # avvia il bot Telegram (modalita' da .env)
    python main.py --once     # esegue un singolo ciclo di analisi e stampa i segnali (no Telegram)
    python main.py --check    # verifica la configurazione ed esce
"""
from __future__ import annotations

import argparse
import logging
import sys

from config import settings
from src.engine import TradingEngine


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Meno rumore dalle librerie HTTP.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def print_config_report() -> int:
    problems = settings.validate()
    print("=== Configurazione Bot Cripto ===")
    print(f"Modalita' trading : {settings.trading_mode}")
    print(f"Budget iniziale   : {settings.initial_budget_eur:.2f} €")
    print(f"Target mensile    : {settings.monthly_target_eur:.2f} €")
    print(f"Coppie            : {', '.join(settings.trading_pairs)}")
    print(f"Intervallo analisi: {settings.analysis_interval_minutes} min")
    print(f"Feed notizie      : {len(settings.news_rss_feeds)} configurati")
    if problems:
        print("\n⚠️  Problemi di configurazione:")
        for p in problems:
            print(f"   - {p}")
        return 1
    print("\n✅ Configurazione valida.")
    return 0


def run_once() -> int:
    """Esegue un ciclo di analisi e stampa i segnali (utile per test/backtest rapido)."""
    engine = TradingEngine(settings)
    print("Esecuzione ciclo di analisi...\n")
    signals = engine.run_cycle()

    sentiment = getattr(engine, "last_sentiment", None)
    if sentiment:
        print(f"Sentiment notizie: {sentiment.label.value} "
              f"(score {sentiment.score:+.2f}, red_alert={sentiment.red_alert})")
        for r in sentiment.reasons:
            print(f"  - {r}")
        print()

    if not signals:
        print("Nessun segnale operativo (BUY/SELL) generato.")
        return 0

    for s in signals:
        print(f"[{s.signal_type.value}] {s.pair} @ {s.price:.2f} "
              f"| confidenza {s.confidence*100:.0f}% "
              f"| stake {s.suggested_stake_eur:.2f} €")
        for r in s.reasons:
            print(f"    • {r}")
        print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot Cripto — trading automatico su Kraken")
    parser.add_argument("--once", action="store_true", help="Esegui un solo ciclo di analisi ed esci")
    parser.add_argument("--check", action="store_true", help="Verifica la configurazione ed esci")
    parser.add_argument("--verbose", action="store_true", help="Log dettagliato (DEBUG)")
    args = parser.parse_args()

    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    if args.check:
        return print_config_report()

    if args.once:
        return run_once()

    # Avvio bot Telegram.
    problems = settings.validate()
    if problems:
        print("⚠️  Impossibile avviare il bot Telegram:")
        for p in problems:
            print(f"   - {p}")
        print("\nSuggerimento: copia .env.example in .env e compila i valori, "
              "oppure usa 'python main.py --once' per provare senza Telegram.")
        return 1

    from src.telegrambot import TradingTelegramBot

    engine = TradingEngine(settings)
    bot = TradingTelegramBot(settings, engine)
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
