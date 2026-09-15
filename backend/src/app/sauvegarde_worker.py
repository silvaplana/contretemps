"""Sauvegarde programmée automatique ("Programmer sauvegarde École", Admin
> École) — un processus SÉPARÉ, comme relance_worker.py (voir sa docstring
pour le pourquoi : jamais importé par app.main, pour ne jamais démarrer
une boucle infinie au simple import de l'app — ex. pytest via TestClient).

Filet de sécurité UNIQUEMENT (voir ecoles/stockage.py et la conversation
utilisateur) : génère les 2 fichiers (export humain + sauvegarde
technique) et les garde CÔTÉ SERVEUR, dans le dossier de l'école — jamais
perdu même si personne n'a l'appli ouverte au moment programmé. L'écriture
directe sur le disque LOCAL de l'admin (ce que l'utilisateur veut
vraiment) se fait à part, côté navigateur, quand l'appli est ouverte (voir
frontend/src/api/sauvegarde.js) — ce worker ne peut techniquement pas y
accéder (voir la conversation : un serveur ne peut jamais écrire sur le
disque d'un poste client).

Usage :
    python -m app.sauvegarde_worker
"""

from __future__ import annotations

import datetime as dt
import time

from comptes import Comptes
from cours import CoursService
from db import SessionLocal
from ecoles import Ecoles, backup_technique
from ecoles.excel_export import EcoleExport
from ecoles.models import Ecole
from ecoles.stockage import dossier_ecole
from eleves import Eleves
from presence import Presence
from sqlalchemy import select

INTERVALLE_SECONDES = 60


def _est_due(ecole: Ecole, maintenant: dt.datetime) -> bool:
    """Voir modèle Ecole (sauvegarde_*) — 'mois' se cale sur le 1er du
    mois (simplification assumée : pas de champ "jour du mois" séparé
    dans le panneau "Programmer sauvegarde École"), 'semaine' sur
    `sauvegarde_jour_semaine` (0=lundi..6=dimanche), 'jour' tous les
    jours. Dans tous les cas, au plus 1 fois par jour (voir
    `sauvegarde_derniere_execution`) — évite un redéclenchement si le
    worker est relancé (redéploiement) pendant la même minute cible."""
    if not ecole.sauvegarde_active or not ecole.sauvegarde_heure:
        return False
    if (
        ecole.sauvegarde_derniere_execution
        and ecole.sauvegarde_derniere_execution.date() == maintenant.date()
    ):
        return False
    if maintenant.strftime("%H:%M") != ecole.sauvegarde_heure:
        return False
    if ecole.sauvegarde_periodicite == "semaine":
        return (
            ecole.sauvegarde_jour_semaine is not None
            and maintenant.weekday() == ecole.sauvegarde_jour_semaine
        )
    if ecole.sauvegarde_periodicite == "mois":
        return maintenant.day == 1
    return True  # 'jour'


def run() -> None:
    ecoles_client = Ecoles()
    comptes_client = Comptes()
    cours_client = CoursService()
    eleves_client = Eleves(comptes=comptes_client)
    presence_client = Presence(cours=cours_client)
    export_client = EcoleExport(
        comptes=comptes_client, eleves=eleves_client, cours=cours_client, presence=presence_client
    )

    print(f"Sauvegarde programmée démarrée (vérifie toutes les {INTERVALLE_SECONDES}s).")
    while True:
        time.sleep(INTERVALLE_SECONDES)
        maintenant = dt.datetime.now()
        db = SessionLocal()
        try:
            for ecole in db.scalars(select(Ecole).where(Ecole.sauvegarde_active.is_(True))):
                if not _est_due(ecole, maintenant):
                    continue
                try:
                    dossier = dossier_ecole(ecole.id)
                    horodatage = maintenant.strftime("%Y%m%d_%H%M%S")
                    (dossier / f"{horodatage}_humain.xlsx").write_bytes(
                        export_client.generer(db, ecole)
                    )
                    (dossier / f"{horodatage}_techBackup.xlsx").write_bytes(
                        backup_technique.generer(db, ecole)
                    )
                    ecole.sauvegarde_derniere_execution = maintenant
                    db.commit()
                    print(f"Sauvegarde programmée : école {ecole.id} ({ecole.nom}) OK.")
                except Exception:
                    db.rollback()
                    print(f"Sauvegarde programmée ÉCHOUÉE pour l'école {ecole.id} ({ecole.nom}).")
        finally:
            db.close()


if __name__ == "__main__":
    run()
