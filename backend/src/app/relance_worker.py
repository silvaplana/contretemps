"""Relance automatique des messages non lus (voir spec/SPEC.md §5.5) —
un processus SÉPARÉ, à lancer à côté du serveur web (jamais importé par
app.main : on ne veut surtout pas qu'un simple import de l'app FastAPI —
comme le fait pytest via TestClient à chaque test — démarre une boucle
infinie en arrière-plan qui écrirait dans la vraie base).

⚠️ Ne fait QUE basculer le canal en 'email' en base (voir messagerie/
messages.py : relancer_messages_non_lus) — il n'existe encore aucune
vraie infrastructure d'envoi de mail dans ce projet (pas de SMTP ni
d'API tierce), exactement comme le marqueur canal='whatsapp' : une
trace d'intention, pas un vrai envoi.

Usage :
    python -m app.relance_worker
"""

import time

from comptes import Comptes
from cours import CoursService
from db import SessionLocal
from messagerie import Conversations, Messages

INTERVALLE_SECONDES = 60
DELAI_MINUTES = 15


def run() -> None:
    messages_client = Messages(Conversations(comptes=Comptes(), cours=CoursService()))
    print(
        f"Relance auto démarrée (vérifie toutes les {INTERVALLE_SECONDES}s, "
        f"délai {DELAI_MINUTES} min)."
    )
    while True:
        time.sleep(INTERVALLE_SECONDES)
        db = SessionLocal()
        try:
            relancees = messages_client.relancer_messages_non_lus(db, delai_minutes=DELAI_MINUTES)
            if relancees:
                print(f"Relance auto : {len(relancees)} message(s) basculé(s) en 'email'.")
        finally:
            db.close()


if __name__ == "__main__":
    run()
