"""Portafoglio persistente su file JSON (usato dal Paper Trading).

Tiene traccia di:
    - saldo in EUR
    - posizioni aperte per coppia (volume, prezzo medio di carico)
    - storico delle operazioni
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional


class Portfolio:
    def __init__(self, path: str, initial_eur: float = 100.0):
        self.path = path
        self._lock = threading.Lock()
        self.eur: float = initial_eur
        self.initial_eur: float = initial_eur
        self.positions: Dict[str, Dict] = {}  # pair -> {volume, avg_price}
        self.history: List[Dict] = []
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self.eur = data.get("eur", self.eur)
                self.initial_eur = data.get("initial_eur", self.initial_eur)
                self.positions = data.get("positions", {})
                self.history = data.get("history", [])
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self) -> None:
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "eur": self.eur,
                    "initial_eur": self.initial_eur,
                    "positions": self.positions,
                    "history": self.history,
                },
                fh,
                indent=2,
                ensure_ascii=False,
            )
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------
    def record_buy(self, pair: str, volume: float, price: float, cost_eur: float) -> None:
        with self._lock:
            self.eur -= cost_eur
            pos = self.positions.get(pair, {"volume": 0.0, "avg_price": 0.0})
            new_volume = pos["volume"] + volume
            # Prezzo medio ponderato di carico.
            if new_volume > 0:
                pos["avg_price"] = (
                    pos["avg_price"] * pos["volume"] + price * volume
                ) / new_volume
            pos["volume"] = new_volume
            self.positions[pair] = pos
            self.history.append(
                {
                    "ts": time.time(),
                    "side": "buy",
                    "pair": pair,
                    "volume": volume,
                    "price": price,
                    "cost_eur": cost_eur,
                }
            )
            self._save()

    def record_sell(self, pair: str, volume: float, price: float, proceeds_eur: float) -> None:
        with self._lock:
            self.eur += proceeds_eur
            pos = self.positions.get(pair, {"volume": 0.0, "avg_price": 0.0})
            pos["volume"] = max(0.0, pos["volume"] - volume)
            if pos["volume"] <= 1e-12:
                pos = {"volume": 0.0, "avg_price": 0.0}
            self.positions[pair] = pos
            self.history.append(
                {
                    "ts": time.time(),
                    "side": "sell",
                    "pair": pair,
                    "volume": volume,
                    "price": price,
                    "proceeds_eur": proceeds_eur,
                }
            )
            self._save()

    # ------------------------------------------------------------------
    def get_position(self, pair: str) -> Optional[Dict]:
        pos = self.positions.get(pair)
        if pos and pos["volume"] > 0:
            return pos
        return None

    def equity(self, prices: Optional[Dict[str, float]] = None) -> float:
        """Valore totale del portafoglio (EUR + posizioni valorizzate)."""
        prices = prices or {}
        total = self.eur
        for pair, pos in self.positions.items():
            if pos["volume"] > 0:
                px = prices.get(pair, pos["avg_price"])
                total += pos["volume"] * px
        return total

    def summary(self, prices: Optional[Dict[str, float]] = None) -> Dict:
        eq = self.equity(prices)
        return {
            "eur_cash": round(self.eur, 2),
            "equity": round(eq, 2),
            "initial_eur": round(self.initial_eur, 2),
            "pnl_eur": round(eq - self.initial_eur, 2),
            "pnl_pct": round((eq - self.initial_eur) / self.initial_eur * 100, 2)
            if self.initial_eur
            else 0.0,
            "open_positions": {
                p: pos for p, pos in self.positions.items() if pos["volume"] > 0
            },
            "trades": len(self.history),
        }
