"""Analytics: ricostruisce dallo storico del portafoglio la curva di equity,
il P&L realizzato (totale e per mese) e il progresso verso l'obiettivo mensile.

Lo storico (Portfolio.history) contiene eventi:
    buy  -> {ts, side:'buy',  pair, volume, price, cost_eur}
    sell -> {ts, side:'sell', pair, volume, price, proceeds_eur}
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

from ..trading.portfolio import Portfolio


def _month_key(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m")


class PortfolioAnalytics:
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio

    # ------------------------------------------------------------------
    def _replay(self, current_prices: Optional[Dict[str, float]] = None) -> Dict:
        """Riproduce lo storico calcolando cassa, posizioni e P&L realizzato.

        Ritorna un dizionario con:
            equity_curve      -> [{ts, equity}]
            realized_total    -> float
            realized_by_month -> {'YYYY-MM': float}
            positions         -> {pair: {volume, avg_cost}}
            cash              -> float finale
        """
        current_prices = current_prices or {}
        cash = self.portfolio.initial_eur
        # pair -> {volume, total_cost}
        positions: Dict[str, Dict[str, float]] = {}
        last_price: Dict[str, float] = {}
        realized_total = 0.0
        realized_by_month: Dict[str, float] = {}
        equity_curve: List[Dict] = []

        history = sorted(self.portfolio.history, key=lambda e: e.get("ts", 0))

        # Punto di partenza (prima di qualsiasi operazione).
        if history:
            start_ts = history[0]["ts"]
            equity_curve.append({"ts": start_ts, "equity": round(cash, 2)})

        for ev in history:
            ts = ev.get("ts", 0)
            pair = ev.get("pair", "")
            price = float(ev.get("price", 0.0))
            volume = float(ev.get("volume", 0.0))
            last_price[pair] = price
            pos = positions.setdefault(pair, {"volume": 0.0, "total_cost": 0.0})

            if ev.get("side") == "buy":
                cost = float(ev.get("cost_eur", volume * price))
                cash -= cost
                pos["volume"] += volume
                pos["total_cost"] += cost
            elif ev.get("side") == "sell":
                proceeds = float(ev.get("proceeds_eur", volume * price))
                avg_cost = pos["total_cost"] / pos["volume"] if pos["volume"] > 0 else 0.0
                cost_removed = avg_cost * volume
                realized = proceeds - cost_removed
                realized_total += realized
                mk = _month_key(ts)
                realized_by_month[mk] = realized_by_month.get(mk, 0.0) + realized
                cash += proceeds
                pos["volume"] = max(0.0, pos["volume"] - volume)
                pos["total_cost"] = max(0.0, pos["total_cost"] - cost_removed)

            # Equity mark-to-market usando l'ultimo prezzo noto per ogni coppia.
            holdings = sum(
                p["volume"] * last_price.get(pr, 0.0) for pr, p in positions.items()
            )
            equity_curve.append({"ts": ts, "equity": round(cash + holdings, 2)})

        # Posizioni finali con prezzo medio di carico.
        final_positions = {}
        for pr, p in positions.items():
            if p["volume"] > 1e-12:
                avg = p["total_cost"] / p["volume"] if p["volume"] > 0 else 0.0
                final_positions[pr] = {
                    "volume": p["volume"],
                    "avg_cost": round(avg, 2),
                }

        return {
            "equity_curve": equity_curve,
            "realized_total": round(realized_total, 2),
            "realized_by_month": {k: round(v, 2) for k, v in realized_by_month.items()},
            "positions": final_positions,
            "cash": round(cash, 2),
        }

    # ------------------------------------------------------------------
    def overview(
        self, current_prices: Optional[Dict[str, float]] = None, monthly_target: float = 500.0
    ) -> Dict:
        current_prices = current_prices or {}
        rep = self._replay(current_prices)

        # Valore corrente delle posizioni aperte (mark-to-market se ho i prezzi).
        holdings_value = 0.0
        unrealized = 0.0
        positions_detail = []
        for pr, p in rep["positions"].items():
            px = current_prices.get(pr, p["avg_cost"])
            value = p["volume"] * px
            cost = p["volume"] * p["avg_cost"]
            holdings_value += value
            unrealized += value - cost
            positions_detail.append(
                {
                    "pair": pr,
                    "volume": round(p["volume"], 8),
                    "avg_cost": p["avg_cost"],
                    "current_price": round(px, 2),
                    "value_eur": round(value, 2),
                    "pnl_eur": round(value - cost, 2),
                    "pnl_pct": round((value - cost) / cost * 100, 2) if cost else 0.0,
                    "priced": pr in current_prices,
                }
            )

        equity = rep["cash"] + holdings_value
        initial = self.portfolio.initial_eur
        total_pnl = equity - initial

        current_month = dt.datetime.now().strftime("%Y-%m")
        realized_this_month = rep["realized_by_month"].get(current_month, 0.0)
        # Progresso verso l'obiettivo: profitto realizzato nel mese corrente.
        progress_pct = (realized_this_month / monthly_target * 100) if monthly_target else 0.0
        remaining = max(0.0, monthly_target - realized_this_month)

        return {
            "mode": "PAPER",
            "initial_eur": round(initial, 2),
            "cash_eur": round(rep["cash"], 2),
            "holdings_value_eur": round(holdings_value, 2),
            "equity_eur": round(equity, 2),
            "total_pnl_eur": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / initial * 100, 2) if initial else 0.0,
            "realized_total_eur": rep["realized_total"],
            "unrealized_eur": round(unrealized, 2),
            "trades_count": len(self.portfolio.history),
            "positions": positions_detail,
            "equity_curve": rep["equity_curve"],
            "realized_by_month": rep["realized_by_month"],
            # Obiettivo mensile
            "monthly_target_eur": round(monthly_target, 2),
            "month": current_month,
            "realized_this_month_eur": round(realized_this_month, 2),
            "target_progress_pct": round(progress_pct, 1),
            "target_remaining_eur": round(remaining, 2),
        }

    def recent_trades(self, limit: int = 50) -> List[Dict]:
        trades = sorted(self.portfolio.history, key=lambda e: e.get("ts", 0), reverse=True)
        out = []
        for ev in trades[:limit]:
            out.append(
                {
                    "ts": ev.get("ts"),
                    "datetime": dt.datetime.fromtimestamp(ev.get("ts", 0)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "side": ev.get("side"),
                    "pair": ev.get("pair"),
                    "volume": round(float(ev.get("volume", 0)), 8),
                    "price": round(float(ev.get("price", 0)), 2),
                    "amount_eur": round(
                        float(ev.get("cost_eur", ev.get("proceeds_eur", 0))), 2
                    ),
                }
            )
        return out
