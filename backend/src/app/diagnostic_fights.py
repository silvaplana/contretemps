"""Ce que Fights a vu, en lecture seule, pour un fil Claude (Seb, 13/11/2026 :
« un accès restreint au domaine Fights »). Les mêmes lectures que l'action
« Maintenance du VPS » (lire_seance_fights, lire_essai_labo), sans passer par
GitHub. N'écrit rien.

    GET /diagnostic/fights              les 10 dernières séances et les essais
    GET /diagnostic/fights?seance=12    le détail d'une séance
    GET /diagnostic/fights?essai=4      le détail d'un essai du Labo

Clé dans l'en-tête X-Diag-Key, égale à FIGHTS_DIAG_KEY (backend/.env, au
moins 32 caractères). Sans clé configurée, l'adresse n'existe pas (404).
"""

from __future__ import annotations

import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from db import get_db
from saisons.portee import toutes_saisons

PATH = "/diagnostic/fights"
_db = Depends(get_db)


def install(app: FastAPI) -> None:
    @app.get(PATH, response_class=PlainTextResponse, include_in_schema=False)
    def diagnostic(
        seance: int | None = None,
        essai: int | None = None,
        x_diag_key: str | None = Header(None),
        db: Session = _db,
    ) -> str:
        key = os.environ.get("FIGHTS_DIAG_KEY", "")
        if len(key) < 32 or not x_diag_key or not hmac.compare_digest(key, x_diag_key):
            raise HTTPException(status_code=404, detail="Not Found")
        from app import lire_essai_labo, lire_seance_fights

        lines: list[str] = []
        out = lambda *parts: lines.append(" ".join(str(p) for p in parts))
        with toutes_saisons(db):
            if essai is not None:
                lire_essai_labo.detail(db, essai, out)
            elif seance is not None:
                lire_seance_fights.detail(db, seance, out)
            else:
                lire_seance_fights.lister(db, out)
                out("")
                lire_essai_labo.lister(db, out)
        return "\n".join(lines) + "\n"
