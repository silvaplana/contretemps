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

Fait aussi partir la relance d'une convocation d'AG sept jours avant, aux
membres qui n'ont pas répondu (spec/modules/procurations.md, étape 3) : un
vrai email, celui de Diffuser.

Synchronise aussi, toutes les 5 minutes, les inscrits HelloAsso des écoles
qui ont choisi une campagne (spec/modules/helloasso.md §4).

Relaie aussi, toutes les 5 minutes, les nouveaux posts du compte Instagram
relié aux actualités (spec/modules/actualites.md §6 bis).

Lit aussi les comptes en banque des écoles connectées (financier.md §3.5) :
toutes les 15 minutes il regarde, et relit une école dont la dernière lecture
a plus de 12 h ; prévient les trésoriers une semaine avant la fin de l'accès.
Sans clé Enable Banking sur ce conteneur (voir docker-compose.yml, volume
/run/secrets), rien n'est lu.

Usage :
    python -m app.relance_worker
"""

import time

from comptes import Comptes
from cours import CoursService
from db import SessionLocal
from documents import assembly
from documents_contretemps import AnnuaireContretemps, AssociationContretemps, MessagerieContretemps
from eleves import Eleves
from finances import Finances
from finances.bank import Bank
from finances_contretemps.adapter import prevenir_tresoriers
from finances_contretemps.module import _client_bancaire
from helloasso.module import add_member
from helloasso.sync import Sync, sync_all
from messagerie import Conversations, Messages
from news.instagram import InstagramApp, InstagramRelay
from news.news import News
from news.storage import news_storage
from notifications import Notifications
from securite.chiffrement import chiffrer, dechiffrer
from videos import Videos

INTERVALLE_SECONDES = 60
DELAI_MINUTES = 15
HELLOASSO_TOURS = 5  # une synchronisation HelloAsso tous les 5 tours (5 min)
INSTAGRAM_TOURS = 5  # les posts Instagram tous les 5 tours (5 min)
BANQUE_TOURS = 15  # la banque tous les 15 tours (15 min) ; relue si > 12 h


def run() -> None:
    messages_client = Messages(Conversations(comptes=Comptes(), cours=CoursService()))
    annuaire, mails = AnnuaireContretemps(), MessagerieContretemps()
    # La copie des rappels pour l'adresse de contact de l'association.
    association = AssociationContretemps()
    helloasso = Sync(add_member=add_member(Eleves(comptes=Comptes())))
    # Pas de notification pour un post relayé : `notifications` inutile ici.
    instagram = InstagramRelay(News(notifications=None, storage=news_storage(), videos=Videos()), app=InstagramApp.from_env())
    banque = Bank(client=_client_bancaire(), finances=Finances(), encrypt=chiffrer, decrypt=dechiffrer, warn=prevenir_tresoriers(Notifications()))
    if banque.client is None:
        print("Connexion bancaire non configurée sur ce conteneur : pas de lecture automatique.")
    tour = 0
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
            try:
                envoyes = assembly.remind_due(db, mails, annuaire, association=association)
                if envoyes:
                    print(f"Relance AG : {envoyes} email(s) envoyé(s).")
            except Exception as erreur:  # noqa: BLE001 (la boucle continue)
                db.rollback()
                print(f"Relance AG en échec : {erreur}")
            tour += 1
            if tour % HELLOASSO_TOURS == 0:
                try:
                    for ecole_id, resultat in sync_all(db, helloasso).items():
                        print(f"HelloAsso, école {ecole_id} : {resultat}")
                except Exception as erreur:  # noqa: BLE001 (la boucle continue)
                    db.rollback()
                    print(f"Synchronisation HelloAsso en échec : {erreur}")
            if tour % INSTAGRAM_TOURS == 0:
                try:
                    for ecole_id, relayes in instagram.sync_all(db).items():
                        if relayes:
                            print(f"Instagram, école {ecole_id} : {relayes} post(s) relayé(s).")
                except Exception as erreur:  # noqa: BLE001 (la boucle continue)
                    db.rollback()
                    print(f"Relais Instagram en échec : {erreur}")
            if tour % BANQUE_TOURS == 0 and banque.client is not None:
                try:
                    bilan = banque.automatic(db)
                    if bilan["synced"] or bilan["warned"]:
                        print(f"Banque : {bilan['synced']} école(s) relue(s), {bilan['added']} opération(s), {bilan['warned']} rappel(s) d'expiration.")
                except Exception as erreur:  # noqa: BLE001 (la boucle continue)
                    db.rollback()
                    print(f"Lecture bancaire en échec : {erreur}")
        finally:
            db.close()


if __name__ == "__main__":
    run()
