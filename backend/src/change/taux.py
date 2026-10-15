"""Taux de change dollar -> euro, pour afficher en euros les coûts d'IA
(facturés en dollars par Anthropic, et enregistrés en dollars).

Source : le cours de référence publié chaque jour ouvré par la Banque
centrale européenne (gratuit, sans inscription). Lu au plus une fois par
jour, gardé en mémoire et sur disque ; si la BCE ne répond pas, le dernier
taux connu sert, sinon une valeur de secours. Variable TAUX_EUR_PAR_USD :
taux fixe (tests, ou panne durable)."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger(__name__)

URL_BCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
VALIDITE_SECONDES = 24 * 3600
SECOURS_EUR_PAR_USD = 0.9  # tant qu'aucun taux n'a jamais été lu


class TauxChange:
    def __init__(self, fichier: Path | None = None) -> None:
        self.fichier = fichier
        self._verrou = threading.Lock()
        self._taux: dict | None = None
        if fichier is not None and fichier.exists():
            try:
                self._taux = json.loads(fichier.read_text())
            except (OSError, ValueError):
                self._taux = None

    def _lire_bce(self) -> dict | None:
        try:
            with urllib.request.urlopen(URL_BCE, timeout=5) as reponse:
                xml = reponse.read().decode("utf-8", "replace")
        except OSError:
            logger.warning("Taux de change : la BCE ne répond pas, dernier taux connu utilisé")
            return None
        usd = re.search(r"currency=['\"]USD['\"]\s+rate=['\"]([0-9.]+)['\"]", xml)
        date = re.search(r"time=['\"]([0-9-]+)['\"]", xml)
        if not usd:
            return None
        return {"eur_par_usd": round(1 / float(usd.group(1)), 6), "date": date.group(1) if date else None,
                "lu_le": time.time(), "source": "BCE"}

    def taux(self) -> dict:
        """{eur_par_usd, date, source} : 1 $ = eur_par_usd €."""
        fixe = os.environ.get("TAUX_EUR_PAR_USD")
        if fixe:
            return {"eur_par_usd": float(fixe), "date": None, "source": "fixé"}
        with self._verrou:
            if self._taux is None or time.time() - self._taux.get("lu_le", 0) > VALIDITE_SECONDES:
                nouveau = self._lire_bce()
                if nouveau is not None:
                    self._taux = nouveau
                    if self.fichier is not None:
                        try:
                            self.fichier.parent.mkdir(parents=True, exist_ok=True)
                            self.fichier.write_text(json.dumps(nouveau))
                        except OSError:
                            pass
                elif self._taux is not None:
                    # Réessayer dans une heure, pas à chaque demande.
                    self._taux["lu_le"] = time.time() - VALIDITE_SECONDES + 3600
            if self._taux is None:
                return {"eur_par_usd": SECOURS_EUR_PAR_USD, "date": None, "source": "secours"}
            return {k: self._taux[k] for k in ("eur_par_usd", "date", "source")}


class TauxChangeReceiver:
    def __init__(self, client: TauxChange, app: FastAPI) -> None:
        app.get("/taux-change")(lambda: client.taux())
