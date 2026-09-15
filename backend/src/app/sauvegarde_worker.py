"""Sauvegarde programmée automatique ("Programmer sauvegarde École", Admin
> École) — un processus SÉPARÉ, comme relance_worker.py (voir sa docstring
pour le pourquoi : jamais importé par app.main, pour ne jamais démarrer
une boucle infinie au simple import de l'app — ex. pytest via TestClient).

Filet de sécurité (voir ecoles/stockage.py et la conversation
utilisateur) : génère les 2 fichiers (export humain + sauvegarde
technique) et les garde CÔTÉ SERVEUR, dans le dossier de l'école — jamais
perdu même si personne n'a l'appli ouverte au moment programmé. L'écriture
directe sur le disque LOCAL de l'admin se fait à part, côté navigateur,
quand l'appli est ouverte (voir frontend/src/api/ecoles.js) — ce worker ne
peut techniquement pas y accéder (un serveur ne peut jamais écrire sur le
disque d'un poste client).

EN PLUS (décision utilisateur explicite) : si Google Drive est configuré
(voir ecoles/google_drive.py, GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE/
GOOGLE_DRIVE_DOSSIER_ID dans .env.example), les 2 fichiers y sont AUSSI
envoyés — indépendamment de la sauvegarde serveur ci-dessus (son propre
try/except, voir plus bas) : contrairement à l'écriture locale, Drive est
toujours joignable depuis le serveur, que quelqu'un ait l'appli ouverte
ou non — la vraie solution "fiable à 100%" pour la sauvegarde programmée.

Usage :
    python -m app.sauvegarde_worker
"""

from __future__ import annotations

import datetime as dt
import time

from comptes import Comptes
from cours import CoursService
from db import SessionLocal
from ecoles import Ecoles, GoogleDrive, backup_technique
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
    drive_client = GoogleDrive()

    print(
        f"Sauvegarde programmée démarrée (vérifie toutes les {INTERVALLE_SECONDES}s, "
        f"Google Drive {'activé' if drive_client.est_configure() else 'non configuré'})."
    )
    while True:
        time.sleep(INTERVALLE_SECONDES)
        maintenant = dt.datetime.now()
        db = SessionLocal()
        try:
            for ecole in db.scalars(select(Ecole).where(Ecole.sauvegarde_active.is_(True))):
                if not _est_due(ecole, maintenant):
                    continue
                try:
                    contenu_humain = export_client.generer(db, ecole)
                    contenu_technique = backup_technique.generer(db, ecole)
                    horodatage = maintenant.strftime("%Y%m%d_%H%M%S")
                    nom_humain = f"{horodatage}_humain.xlsx"
                    nom_technique = f"{horodatage}_techBackup.xlsx"

                    dossier = dossier_ecole(ecole.id)
                    (dossier / nom_humain).write_bytes(contenu_humain)
                    (dossier / nom_technique).write_bytes(contenu_technique)
                    ecole.sauvegarde_derniere_execution = maintenant
                    db.commit()
                    print(f"Sauvegarde programmée : école {ecole.id} ({ecole.nom}) OK (serveur).")
                except Exception:
                    db.rollback()
                    print(f"Sauvegarde programmée ÉCHOUÉE pour l'école {ecole.id} ({ecole.nom}).")
                    continue

                # Google Drive : domaine d'échec INDÉPENDANT (voir docstring
                # de tête) — jamais annulé/refait si la sauvegarde serveur
                # ci-dessus a déjà réussi, jamais bloquant non plus si Drive
                # échoue (déjà en sécurité côté serveur de toute façon).
                if drive_client.est_configure():
                    try:
                        drive_client.televerser(nom_humain, contenu_humain)
                        drive_client.televerser(nom_technique, contenu_technique)
                        print(f"Sauvegarde programmée : école {ecole.id} ({ecole.nom}) OK (Drive).")
                    except Exception:
                        print(
                            f"Sauvegarde programmée : envoi Drive ÉCHOUÉ pour l'école "
                            f"{ecole.id} ({ecole.nom}) (sauvegarde serveur déjà en sécurité)."
                        )
        finally:
            db.close()


if __name__ == "__main__":
    run()
