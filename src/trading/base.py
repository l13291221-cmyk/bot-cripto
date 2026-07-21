"""Interfaccia comune ai trader (paper e live)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import OrderResult, Signal


class Trader(ABC):
    mode: str = "BASE"

    @abstractmethod
    def execute(self, signal: Signal) -> OrderResult:
        """Esegue un segnale operativo e ritorna l'esito."""

    @abstractmethod
    def status(self) -> dict:
        """Ritorna lo stato del conto/portafoglio."""
