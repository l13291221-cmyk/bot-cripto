"""Test del filtro sentiment/allerta rossa (senza rete, headline iniettate)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import SentimentLabel
from src.sentiment import NewsSentimentAnalyzer


def _analyzer_with(headlines):
    a = NewsSentimentAnalyzer(feeds=[])
    a._fetch_headlines = lambda: headlines  # type: ignore
    return a


def test_red_alert_on_war_and_crash():
    headlines = [
        "War escalates as missiles hit the capital",
        "Crypto market crash: massive liquidation cascade",
    ]
    report = _analyzer_with(headlines).analyze()
    assert report.red_alert is True
    assert report.label == SentimentLabel.RED_ALERT


def test_positive_climate():
    headlines = [
        "Bitcoin surges to record high amid strong adoption",
        "Ethereum rally continues, bullish optimism grows",
    ]
    report = _analyzer_with(headlines).analyze()
    assert report.red_alert is False
    assert report.label == SentimentLabel.POSITIVE
    assert report.score > 0


def test_no_news_is_neutral():
    report = _analyzer_with([]).analyze()
    assert report.label == SentimentLabel.NEUTRAL
    assert report.red_alert is False


def test_single_crisis_word_not_enough_alone():
    # Un solo titolo di crisi con clima non troppo negativo non scatena l'allerta.
    headlines = ["A single article mentions a possible war risk but markets stay calm and strong"]
    report = _analyzer_with(headlines).analyze()
    assert report.red_alert is False
