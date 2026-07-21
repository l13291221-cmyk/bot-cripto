"""Configurazione centrale del bot.

Legge le variabili d'ambiente (dal file .env se presente) ed espone
un oggetto ``settings`` usato in tutto il progetto.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv opzionale
    pass


def _get_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Kraken
    kraken_api_key: str = os.getenv("KRAKEN_API_KEY", "")
    kraken_api_secret: str = os.getenv("KRAKEN_API_SECRET", "")

    # Trading
    trading_mode: str = os.getenv("TRADING_MODE", "PAPER").upper()
    initial_budget_eur: float = _get_float("INITIAL_BUDGET_EUR", 100.0)
    monthly_target_eur: float = _get_float("MONTHLY_TARGET_EUR", 500.0)
    trading_pairs: List[str] = field(
        default_factory=lambda: _get_list("TRADING_PAIRS", "XBTEUR,ETHEUR,SOLEUR")
    )
    max_position_fraction: float = _get_float("MAX_POSITION_FRACTION", 0.5)
    default_stop_loss: float = _get_float("DEFAULT_STOP_LOSS", 0.05)
    default_take_profit: float = _get_float("DEFAULT_TAKE_PROFIT", 0.10)

    # Scheduler
    analysis_interval_minutes: int = _get_int("ANALYSIS_INTERVAL_MINUTES", 60)

    # News
    news_rss_feeds: List[str] = field(
        default_factory=lambda: _get_list(
            "NEWS_RSS_FEEDS",
            "https://www.coindesk.com/arc/outboundfeeds/rss/,"
            "https://cointelegraph.com/rss,"
            "https://www.investing.com/rss/news_301.rss",
        )
    )

    # Percorsi
    data_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

    @property
    def is_live(self) -> bool:
        return self.trading_mode == "LIVE"

    def validate(self) -> List[str]:
        """Ritorna la lista di problemi di configurazione (vuota = ok)."""
        problems: List[str] = []
        if not self.telegram_bot_token:
            problems.append("TELEGRAM_BOT_TOKEN mancante.")
        if not self.telegram_chat_id:
            problems.append("TELEGRAM_CHAT_ID mancante.")
        if self.is_live and (not self.kraken_api_key or not self.kraken_api_secret):
            problems.append(
                "Modalita' LIVE selezionata ma KRAKEN_API_KEY/SECRET mancanti."
            )
        if not self.trading_pairs:
            problems.append("Nessuna coppia in TRADING_PAIRS.")
        return problems


settings = Settings()
os.makedirs(settings.data_dir, exist_ok=True)
