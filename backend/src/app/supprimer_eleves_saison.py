"""Efface les élèves d'une ancienne saison : les fiches qui n'ont que le rôle
élève (profs et administrateurs gardés), avec leurs contacts, leurs cours et
leurs chorégraphies. Écrite pour retirer les 82 élèves fictives de
démonstration restées dans 2025-2026 de la vraie école, avant de réimporter
le vrai fichier d'adhérents (Seb, 9 novembre 2026). Irréversible, mais une
sauvegarde complète de l'école est écrite juste avant (historique des
sauvegardes, Admin > École).

Refusée sur la saison en cours. À lancer sur le serveur :

    docker compose exec backend python -m app.supprimer_eleves_saison --lister
    docker compose exec backend python -m app.supprimer_eleves_saison \\
        --ecole 1 --saison "2025-2026" --nom "Contretemps"
    ... puis, une fois les nombres vérifiés, la même chose avec --pour-de-vrai

Sans --pour-de-vrai, rien n'est effacé : la commande dit seulement combien
de fiches elle effacerait. --nom tient lieu de confirmation.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app import main as _appli  # noqa: F401  (charge tous les modèles)
from comptes import Comptes, roles
from comptes.models import Compte
from db import SessionLocal
from ecoles.models import Ecole
from eleves import Eleves
from saisons import Saison, saison_courante_id
from saisons.gestion import _sauvegarder_avant_suppression
from saisons.portee import toutes_saisons


def _eleves_seules(db, ecole_id: int, saison_id: int) -> list[Compte]:
    fiches = db.scalars(select(Compte).where(Compte.ecole_id == ecole_id, Compte.saison_id == saison_id))
    return [c for c in fiches if roles.noms_roles(c) == [roles.ELEVE]]


def lister(db) -> None:
    with toutes_saisons(db):
        for ecole in db.scalars(select(Ecole).order_by(Ecole.id)):
            print(f"{ecole.id:>3}  {ecole.nom}")
            courante = saison_courante_id(db, ecole.id)
            saisons = db.scalars(select(Saison).where(Saison.ecole_id == ecole.id).order_by(Saison.date_debut))
            for s in saisons:
                n = len(_eleves_seules(db, ecole.id, s.id))
                print(f"       {s.nom}{' (en cours)' if s.id == courante else ''} : {n} fiches seulement élèves")


def executer(db, ecole_id: int, nom_saison: str, nom_ecole: str, pour_de_vrai: bool) -> None:
    ecole = db.get(Ecole, ecole_id)
    if ecole is None or nom_ecole.strip() != ecole.nom:
        sys.exit("École inconnue ou nom différent : rien n'a été effacé.")
    saison = db.scalar(select(Saison).where(Saison.ecole_id == ecole.id, Saison.nom == nom_saison.strip()))
    if saison is None:
        sys.exit(f"Pas de saison « {nom_saison} » dans {ecole.nom} : rien n'a été effacé.")
    if saison.id == saison_courante_id(db, ecole.id):
        sys.exit("C'est la saison en cours : refusé, rien n'a été effacé.")
    with toutes_saisons(db):
        fiches = _eleves_seules(db, ecole.id, saison.id)
        print(f"{ecole.nom}, saison {saison.nom} : {len(fiches)} fiches seulement élèves.")
        if not pour_de_vrai:
            print("Essai à blanc : rien n'a été effacé. Relancez avec --pour-de-vrai pour effacer.")
            return
        _sauvegarder_avant_suppression(db, ecole)
        eleves = Eleves(comptes=Comptes())
        for fiche in fiches:
            eleves.delete(db, fiche.id)
    print(f"{len(fiches)} fiches effacées (sauvegarde de l'école écrite juste avant).")


def main() -> None:
    options = argparse.ArgumentParser(description="Efface les élèves d'une ancienne saison.")
    options.add_argument("--lister", action="store_true", help="écoles, saisons et nombre d'élèves, sans rien effacer")
    options.add_argument("--ecole", type=int, help="numéro de l'école")
    options.add_argument("--saison", help="nom exact de la saison, ex. 2025-2026")
    options.add_argument("--nom", help="nom exact de l'école, en confirmation")
    options.add_argument("--pour-de-vrai", action="store_true", help="effacer (sinon : essai à blanc)")
    arguments = options.parse_args()
    with SessionLocal() as db:
        if arguments.lister or arguments.ecole is None:
            lister(db)
            return
        executer(db, arguments.ecole, arguments.saison or "", arguments.nom or "", arguments.pour_de_vrai)


if __name__ == "__main__":
    main()
