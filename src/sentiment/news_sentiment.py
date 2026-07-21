"""Filtro di Sentiment Analysis sulle notizie crypto/finanza.

Legge feed RSS pubblici e valuta il "clima" delle notizie recenti.
Obiettivo principale (come richiesto): rilevare ALLERTE ROSSE
(guerre, crolli di mercato) e sospendere i segnali operativi.

L'approccio e' lessicale (keyword weighting): leggero, senza chiavi API
e senza dipendenze pesanti. E' facilmente sostituibile con un modello
NLP o un'API esterna implementando la stessa interfaccia.
"""
from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Tuple
from xml.etree import ElementTree

import requests

try:  # feedparser e' preferito ma opzionale: c'e' un fallback su stdlib.
    import feedparser
except Exception:  # pragma: no cover
    feedparser = None

from ..models import SentimentLabel, SentimentReport

log = logging.getLogger(__name__)

# Parole che indicano una CRISI GRAVE -> allerta rossa, segnali sospesi.
RED_ALERT_KEYWORDS = [
    # Guerra / geopolitica
    "war", "guerra", "invasion", "invasione", "attack", "attacco",
    "missile", "nuclear", "nucleare", "airstrike", "conflict", "conflitto",
    "military", "militare", "escalation", "sanctions", "sanzioni",
    # Crolli di mercato
    "crash", "crollo", "collapse", "meltdown", "black swan", "cigno nero",
    "liquidation cascade", "bank run", "contagion", "contagio",
    "default", "bankruptcy", "bancarotta", "insolvency", "hack", "exploit",
    "de-peg", "depeg", "circuit breaker", "market panic", "panico",
]

NEGATIVE_KEYWORDS = [
    "fall", "falling", "drop", "plunge", "tumble", "tumbles", "slump",
    "bearish", "sell-off", "selloff", "fear", "fud", "downturn", "loss",
    "losses", "decline", "correction", "dump", "weak", "warning", "risk",
    "cala", "crolla", "perdite", "ribasso", "paura", "rischio",
]

POSITIVE_KEYWORDS = [
    "surge", "rally", "soar", "soars", "bullish", "gain", "gains", "rise",
    "rises", "record", "all-time high", "ath", "breakout", "adoption",
    "approval", "approved", "boom", "strong", "recovery", "optimism",
    "sale", "rialzo", "record", "adozione", "ottimismo", "recupero",
]


class NewsSentimentAnalyzer:
    def __init__(
        self,
        feeds: List[str],
        max_items_per_feed: int = 20,
        max_age_hours: int = 48,
    ):
        self.feeds = feeds
        self.max_items_per_feed = max_items_per_feed
        self.max_age_seconds = max_age_hours * 3600

    # ------------------------------------------------------------------
    def _fetch_headlines(self) -> List[str]:
        headlines: List[str] = []
        for url in self.feeds:
            try:
                if feedparser is not None:
                    headlines.extend(self._parse_with_feedparser(url))
                else:
                    headlines.extend(self._parse_with_stdlib(url))
            except Exception as exc:
                log.warning("Feed non raggiungibile %s: %s", url, exc)
                continue
        return headlines

    def _parse_with_feedparser(self, url: str) -> List[str]:
        parsed = feedparser.parse(url)
        now = time.time()
        out: List[str] = []
        for entry in parsed.entries[: self.max_items_per_feed]:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                age = now - time.mktime(published)
                if age > self.max_age_seconds:
                    continue
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            text = f"{title}. {summary}".strip(" .")
            if text:
                out.append(text)
        return out

    def _parse_with_stdlib(self, url: str) -> List[str]:
        """Parser RSS/Atom minimale basato sulla stdlib (senza feedparser)."""
        resp = requests.get(url, timeout=20, headers={"User-Agent": "bot-cripto/1.0"})
        resp.raise_for_status()
        root = ElementTree.fromstring(resp.content)

        def _localname(tag: str) -> str:
            return tag.rsplit("}", 1)[-1].lower()

        def _find_text(elem, names: Tuple[str, ...]) -> Optional[str]:
            for child in elem:
                if _localname(child.tag) in names and child.text:
                    return child.text.strip()
            return None

        out: List[str] = []
        # RSS: channel/item ; Atom: feed/entry
        items = [e for e in root.iter() if _localname(e.tag) in ("item", "entry")]
        for item in items[: self.max_items_per_feed]:
            title = _find_text(item, ("title",)) or ""
            summary = _find_text(item, ("description", "summary")) or ""
            summary = re.sub(r"<[^>]+>", " ", summary)  # rimuovi eventuale HTML
            text = f"{title}. {summary}".strip(" .")
            if text:
                out.append(text)
        return out

    @staticmethod
    def _count_keywords(text: str, keywords: List[str]) -> int:
        low = text.lower()
        return sum(1 for kw in keywords if kw in low)

    # ------------------------------------------------------------------
    def analyze(self) -> SentimentReport:
        headlines = self._fetch_headlines()

        if not headlines:
            # Nessuna notizia disponibile: neutro, nessuna allerta.
            return SentimentReport(
                label=SentimentLabel.NEUTRAL,
                score=0.0,
                red_alert=False,
                headlines=[],
                reasons=["Nessuna notizia disponibile (feed vuoti o offline)."],
            )

        red_hits: List[str] = []
        pos_total = 0
        neg_total = 0

        for text in headlines:
            if self._count_keywords(text, RED_ALERT_KEYWORDS) > 0:
                red_hits.append(text[:140])
            pos_total += self._count_keywords(text, POSITIVE_KEYWORDS)
            neg_total += self._count_keywords(text, NEGATIVE_KEYWORDS)

        total = pos_total + neg_total
        score = (pos_total - neg_total) / total if total > 0 else 0.0

        # Allerta rossa: almeno 2 titoli distinti con parole di crisi grave,
        # oppure 1 titolo di crisi con clima gia' molto negativo.
        red_alert = len(red_hits) >= 2 or (len(red_hits) >= 1 and score < -0.3)

        if red_alert:
            label = SentimentLabel.RED_ALERT
        elif score >= 0.2:
            label = SentimentLabel.POSITIVE
        elif score <= -0.2:
            label = SentimentLabel.NEGATIVE
        else:
            label = SentimentLabel.NEUTRAL

        reasons = [
            f"Analizzati {len(headlines)} titoli recenti.",
            f"Segnali positivi: {pos_total}, negativi: {neg_total} (score {score:+.2f}).",
        ]
        if red_hits:
            reasons.append(f"Allerte rilevate in {len(red_hits)} titoli.")

        return SentimentReport(
            label=label,
            score=round(score, 3),
            red_alert=red_alert,
            headlines=red_hits[:5] if red_hits else headlines[:3],
            reasons=reasons,
        )
