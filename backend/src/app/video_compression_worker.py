"""Compression vidéo a posteriori — un processus SÉPARÉ, comme
sauvegarde_worker.py/relance_worker.py (voir leurs docstrings pour le
pourquoi : jamais importé par app.main, pour ne jamais démarrer une
boucle infinie au simple import de l'app — ex. pytest via TestClient).

Décision utilisateur (upload vidéo façon WhatsApp) : compresser AVANT
l'envoi serait plus rapide sur téléphone (encodeur matériel natif), mais
l'appli est web pour l'instant — pas d'accès à un tel encodeur dans un
navigateur, et compresser en JS (ex. ffmpeg.wasm) serait plus lent que
l'upload lui-même. Le fichier brut est donc envoyé tel quel (voir
videos.py : Televersement), puis compressé ICI, après coup, sans jamais
faire attendre l'utilisateur — voir compression.py pour les réglages.

Usage :
    python -m app.video_compression_worker
"""

from __future__ import annotations

import time

from cours import CoursService
from db import SessionLocal
from videos import Videos

INTERVALLE_SECONDES = 30


def run() -> None:
    videos_client = Videos(cours=CoursService())
    print(f"Compression vidéo démarrée (vérifie toutes les {INTERVALLE_SECONDES}s).")
    while True:
        time.sleep(INTERVALLE_SECONDES)
        db = SessionLocal()
        try:
            for video in videos_client.videos_a_compresser(db):
                try:
                    if videos_client.compresser(db, video):
                        print(f"Vidéo {video.id} ({video.nom}) compressée.")
                    else:
                        print(f"Vidéo {video.id} ({video.nom}) : compression échouée, retentée plus tard.")
                except Exception:
                    db.rollback()
                    print(f"Vidéo {video.id} ({video.nom}) : erreur pendant la compression.")
        finally:
            db.close()


if __name__ == "__main__":
    run()
