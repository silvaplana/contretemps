"""Découpe des séances de Sparring en clips (spec/modules/video-combats.md
§5 et §11) — un processus SÉPARÉ, dans son propre conteneur
`sparring-worker` (image avec YOLO, voir backend/Dockerfile.sparring),
comme video_compression_worker.py pour le reste.

Une vidéo envoyée à la main est découpée la nuit (« Découpe cette nuit » à
l'écran), pour ne pas prendre le processeur du VPS en journée : heures dans
SPARRING_HOURS (« 0-6 » par défaut, heure de Paris ; « 0-24 » = toute la
journée). Les morceaux de 2 minutes de la caméra de la salle (étape 3), eux,
sont lus dès leur arrivée, à toute heure, pour des clips prêts quelques
minutes après chaque combat. Les essais du Labo (§6.5 bis) aussi.

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
from session_clips.hearing import hear
from session_clips.lab import read_test, tests_to_read
from session_clips.people import Faces, failed, recognize, sessions_to_recognize
from session_clips.service import SessionClips
from session_clips.hearing import _audio, hear_club_without
from session_clips.voice import hear_tests, recover_truths, run_replays
from session_clips_contretemps.adapter import AnnuaireSparring
from videos import Videos

INTERVALLE_SECONDES = 20
TEST_SECONDES = 2  # « Tester » l'écoute (Seb, 14/11) : la réponse en quelques secondes


def _heures() -> tuple[int, int]:
    debut, fin = os.environ.get("SPARRING_HOURS", "0-6").split("-")
    return int(debut), int(fin)


def run() -> None:
    configure_mappers()
    clips = SessionClips(videos=Videos(), directory=AnnuaireSparring())
    debut, fin = _heures()
    print(f"Découpe Sparring démarrée (caméra de la salle : en direct ; vidéos envoyées : de {debut} h à {fin} h ; toutes les {INTERVALLE_SECONDES}s).")
    # Les réponses données avant que la vérité des tests soit gardée (Seb, 14/11).
    try:
        print(f"Réponses d'avant retrouvées : {recover_truths(_audio)}.")
    except Exception:
        traceback.print_exc()
    faces = None  # modèles des visages, chargés à la première séance à relire
    while True:
        db = SessionLocal()
        try:
            for session in live_sessions(db):
                _cut(db, session, lambda: cut_live(db, clips, session, detect, hear))
            for test in tests_to_read(db):
                _cut(db, test, lambda: read_test(db, clips, test, detect, hear))
            if debut <= datetime.now(ZoneInfo("Europe/Paris")).hour < fin:
                for session in sessions_to_cut(db):
                    _cut(db, session, lambda: cut_session(db, clips, session, detect, hear))
            # Qui est qui ? (Seb, 17/11) : les combattants des séances découpées.
            for session in sessions_to_recognize(db)[:1]:  # une par tour : la caméra passe avant
                faces = faces or Faces()
                _recognize(db, clips, session, faces)
        finally:
            db.close()
        for _ in range(INTERVALLE_SECONDES // TEST_SECONDES):
            try:
                hear_tests(hear)
                run_replays(hear_club_without)
            except Exception:
                traceback.print_exc()
            time.sleep(TEST_SECONDES)


def _recognize(db, clips, session, faces) -> None:
    try:
        n = recognize(db, clips.videos, session, faces)
        print(f"Séance {session.id} : {n} personne(s) repérée(s).")
    except Exception:
        db.rollback()
        failed(session, db)
        print(f"Séance {session.id} : repérage des personnes impossible.")
        traceback.print_exc()


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
