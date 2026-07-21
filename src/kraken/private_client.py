"""Client per le API PRIVATE di Kraken (saldo, ordini).

Richiede KRAKEN_API_KEY e KRAKEN_API_SECRET.
Le richieste private sono firmate secondo lo schema HMAC-SHA512 di Kraken.
Documentazione: https://docs.kraken.com/rest/#section/Authentication
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time
import urllib.parse
from typing import Dict, Optional

import requests

from .public_client import KrakenError

log = logging.getLogger(__name__)

API_URL = "https://api.kraken.com"


class KrakenPrivateClient:
    def __init__(self, api_key: str, api_secret: str, timeout: int = 20):
        if not api_key or not api_secret:
            raise ValueError("API key/secret Kraken richieste per il client privato.")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "bot-cripto/1.0"})

    # ------------------------------------------------------------------
    def _sign(self, urlpath: str, data: Dict) -> str:
        """Genera la firma API-Sign richiesta da Kraken."""
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(
            base64.b64decode(self.api_secret), message, hashlib.sha512
        )
        return base64.b64encode(signature.digest()).decode()

    def _request(self, method: str, data: Optional[Dict] = None) -> Dict:
        urlpath = f"/0/private/{method}"
        data = dict(data or {})
        data["nonce"] = int(time.time() * 1000)
        headers = {
            "API-Key": self.api_key,
            "API-Sign": self._sign(urlpath, data),
        }
        try:
            resp = self._session.post(
                API_URL + urlpath, data=data, headers=headers, timeout=self.timeout
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise KrakenError(f"Errore di rete verso Kraken: {exc}") from exc

        if payload.get("error"):
            raise KrakenError("; ".join(payload["error"]))
        return payload.get("result", {})

    # ------------------------------------------------------------------
    def get_balance(self) -> Dict[str, float]:
        """Ritorna il saldo dei vari asset (es. {'ZEUR': 100.0, 'XXBT': 0.001})."""
        raw = self._request("Balance")
        return {k: float(v) for k, v in raw.items()}

    def get_eur_balance(self) -> float:
        bal = self.get_balance()
        return bal.get("ZEUR", 0.0)

    def add_order(
        self,
        pair: str,
        side: str,
        volume: float,
        ordertype: str = "market",
        price: Optional[float] = None,
        validate: bool = False,
    ) -> Dict:
        """Piazza un ordine.

        side: 'buy' o 'sell'
        ordertype: 'market' o 'limit'
        validate: se True Kraken valida ma NON esegue (utile per test).
        """
        data: Dict = {
            "pair": pair,
            "type": side,
            "ordertype": ordertype,
            "volume": f"{volume:.8f}",
        }
        if ordertype == "limit" and price is not None:
            data["price"] = f"{price:.2f}"
        if validate:
            data["validate"] = True
        return self._request("AddOrder", data)

    def get_open_orders(self) -> Dict:
        return self._request("OpenOrders")

    def query_order(self, txid: str) -> Dict:
        return self._request("QueryOrders", {"txid": txid})
