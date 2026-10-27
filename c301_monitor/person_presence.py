"""Kisi mevcudiyetini karelerden bagimsiz YOLO analizi zamanlarinda izler.

Bu biyometrik kisi tanima DEGiLDIR. Bir veya birden fazla kisi varken
tek bir 'odada kisi var' durumu izlenir. Giris 2 pozitif analizle onaylanir;
cikis 8 saniye surekli negatif analizle onaylanir.
"""
from __future__ import annotations


class PersonPresenceGate:
    def __init__(self, confirmations: int = 2, absence_seconds: float = 8.0):
        if confirmations < 1 or absence_seconds < 0:
            raise ValueError("Gecersiz kisi mevcudiyet esikleri")
        self.confirmations = confirmations
        self.absence_seconds = absence_seconds
        self._present = False
        self._hits = 0
        self._missing_since: float | None = None

    @property
    def present(self) -> bool:
        return self._present

    def observe(self, detected: bool, now: float) -> bool:
        """Yalnizca yeni ve onaylanmis giriste True dondurur."""
        if detected:
            self._missing_since = None
            if self._present:
                return False
            self._hits += 1
            if self._hits >= self.confirmations:
                self._present = True
                self._hits = 0
                return True
            return False

        self._hits = 0
        if self._present:
            if self._missing_since is None:
                self._missing_since = now
            elif now - self._missing_since >= self.absence_seconds:
                self._present = False
                self._missing_since = None
        return False
