"""Avvio della dashboard web del Bot Cripto.

Uso:
    python dashboard.py                 # http://127.0.0.1:5000
    python dashboard.py --port 8080
    python dashboard.py --host 0.0.0.0  # accessibile in rete locale

Mostra: valore del portafoglio, investimenti, guadagni/perdite, storico
operazioni, grafici e progresso verso l'obiettivo mensile.
Legge i dati del Paper Trading (o il saldo Kraken in modalita' LIVE).
"""
from __future__ import annotations

import argparse
import logging

from src.web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Dashboard Bot Cripto")
    parser.add_argument("--host", default="127.0.0.1", help="Host di ascolto")
    parser.add_argument("--port", type=int, default=5000, help="Porta")
    parser.add_argument("--debug", action="store_true", help="Modalita' debug Flask")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    app = create_app()
    url = f"http://{args.host}:{args.port}"
    print(f"\n  📊 Dashboard Bot Cripto in ascolto su {url}")
    print("     Premi CTRL+C per uscire.\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
