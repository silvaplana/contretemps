"""Découpe des séances de Sparring en clips (spec/modules/video-combats.md
§5 et §11) — un processus SÉPARÉ, dans son propre conteneur
`sparring-worker` (image avec YOLO, voir backend/Dockerfile.sparring),
comme video_compression_worker.py pour le reste.

Une vidéo envoyée à la main est découpée la nuit (« Découpe cette nuit » à
l'écran), pour ne pas prendre le processeur du VPS en journée : heures dans
SPARRING_HOURS (« 0-6 » par défaut, heure de Paris ; « 0-24 » = toute la
journée). Les morceaux de 2 minutes de la caméra de la salle (étape 3), eux,
sont lus dès leur arrivée, à toute heure, pour des clips prêts quelques
minutes après chaque combat.

Usage :
    python -m app.sparring_worker
"""

from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import configure_mappers

import comptes.models  # noqa: F401  (voir video_compression_worker.py)
import cours.models  # noqa: F401
import ecoles.models  # noqa: F401
import messagerie.models  # noqa: F401
import saisons.models  # noqa: F401
from db import SessionLocal
from session_clips.cutting import cut_live, cut_session, live_sessions, sessions_to_cut
from session_clips.detector import detect
from session_clips.service import SessionClips
from session_clips_contretemps.adapter import AnnuaireSparring
from videos import Videos

INTERVALLE_SECONDES = 20


def _heures() -> tuple[int, int]:
    debut, fin = os.environ.get("SPARRING_HOURS", "0-6").split("-")
    return int(debut), int(fin)


def run() -> None:
    configure_mappers()
    clips = SessionClips(videos=Videos(), directory=AnnuaireSparring())
    debut, fin = _heures()
    print(f"Découpe Sparring démarrée (caméra de la salle : en direct ; vidéos envoyées : de {debut} h à {fin} h ; toutes les {INTERVALLE_SECONDES}s).")
    while True:
        db = SessionLocal()
        try:
            for session in live_sessions(db):
                _cut(db, session, lambda: cut_live(db, clips, session, detect))
            if debut <= datetime.now(ZoneInfo("Europe/Paris")).hour < fin:
                for session in sessions_to_cut(db):
                    _cut(db, session, lambda: cut_session(db, clips, session, detect))
        finally:
            db.close()
        time.sleep(INTERVALLE_SECONDES)


def _cut(db, session, action) -> None:
    try:
        n = action()
        if n:
            print(f"Séance {session.id} ({session.title}) : {n} clip(s).")
    except Exception:
        db.rollback()
        session.status = "failed"
        db.commit()
        print(f"Séance {session.id} : découpe impossible.")
        traceback.print_exc()


if __name__ == "__main__":
    run()
