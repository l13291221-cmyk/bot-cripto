"""Client per le API PUBBLICHE di Kraken (dati di mercato).

Documentazione: https://docs.kraken.com/rest/
Non richiede alcuna chiave API.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import requests

log = logging.getLogger(__name__)

API_URL = "https://api.kraken.com/0/public"

# Intervalli OHLC supportati da Kraken (in minuti).
INTERVAL_MAP = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
    "15d": 21600,
}


class KrakenError(Exception):
    pass


class KrakenPublicClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "bot-cripto/1.0"})

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        url = f"{API_URL}/{endpoint}"
        try:
            resp = self._session.get(url, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:  # rete / http
            raise KrakenError(f"Errore di rete verso Kraken: {exc}") from exc

        if data.get("error"):
            raise KrakenError("; ".join(data["error"]))
        return data.get("result", {})

    # ------------------------------------------------------------------
    def get_ticker(self, pair: str) -> Dict:
        """Ritorna il ticker (prezzo, bid/ask, volume) per una coppia."""
        result = self._request("Ticker", {"pair": pair})
        # Kraken puo' restituire una chiave normalizzata (es. XXBTZEUR).
        key = next(iter(result))
        return result[key]

    def get_price(self, pair: str) -> float:
        """Prezzo last-trade corrente."""
        ticker = self.get_ticker(pair)
        return float(ticker["c"][0])

    def get_ohlc(self, pair: str, interval: str = "1d", since: Optional[int] = None) -> List[Dict]:
        """Ritorna candele OHLC.

        Ogni candela: {time, open, high, low, close, vwap, volume, count}.
        """
        minutes = INTERVAL_MAP.get(interval, 1440)
        params = {"pair": pair, "interval": minutes}
        if since is not None:
            params["since"] = since
        result = self._request("OHLC", params)
        # La prima chiave e' la coppia, l'ultima 'last'.
        key = next(k for k in result if k != "last")
        candles = []
        for row in result[key]:
            candles.append(
                {
                    "time": int(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "vwap": float(row[5]),
                    "volume": float(row[6]),
                    "count": int(row[7]),
                }
            )
        return candles

    def get_closes(self, pair: str, interval: str = "1d") -> List[float]:
        return [c["close"] for c in self.get_ohlc(pair, interval)]

    def get_asset_pairs(self) -> Dict:
        """Elenco delle coppie disponibili con i relativi vincoli (min order, decimali)."""
        return self._request("AssetPairs")
