"""Recrée dans la vraie base les données de démo (école, comptes, cours,
élèves), pour que le backend démarre avec le même état que le frontend
actuel (voir frontend/src/data/mockData.js). Idempotent : relançable sans
dupliquer, vérifie l'existant avant de créer.

École/admin/profs/cours : en dur ici (petite liste stable, infos
publiques dansecontretemps.fr). Élèves : PAS dupliqués en dur une 3e fois
— lus depuis `seed_data/eleves_demo.xlsx` (80 élèves fictifs, mêmes
statistiques agrégées que le vrai fichier, voir spec §6.4bis) et importés
via `eleves.import_excel`, ce qui a l'avantage de tester ce module à
chaque seed.

Usage :
    python -m app.seed
"""

import os
from pathlib import Path

from comptes import Comptes
from cours import CoursService
from db import Base, SessionLocal, engine
from ecoles import Ecoles
from eleves import Eleves, ImportExcel

# Source profs/cours : page publique dansecontretemps.fr/professeurs-danse-beausset
# (pas d'email public pour les profs -> laissé vide, à compléter par l'admin).
PROFS_CONTRETEMPS = [
    {"nom": "Pesenti", "prenom": "Marie-Laure"},
    {"nom": "Jullien", "prenom": "Pascale"},
    {"nom": "Thomas", "prenom": "Marysa"},
    {"nom": "Revelles", "prenom": "Stellina"},
]

# heure_debut/heure_fin au format "HH:MM" (zéro-paddé, comparé
# lexicalement ailleurs — voir presence.statut_prof) : convention de
# STOCKAGE, différente de l'affichage "17h00" du frontend.
COURS_CONTRETEMPS = [
    {"nom": "Eveil", "jour": "Mercredi", "heure_debut": "17:00", "heure_fin": "17:45", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Classique initiation", "jour": "Mercredi", "heure_debut": "17:45", "heure_fin": "18:30", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Jazz initiation", "jour": "Lundi", "heure_debut": "17:00", "heure_fin": "17:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Classique moyen", "jour": "Mercredi", "heure_debut": "18:30", "heure_fin": "19:30", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Jazz moyen", "jour": "Lundi", "heure_debut": "17:45", "heure_fin": "18:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Jazz junior", "jour": "Lundi", "heure_debut": "18:45", "heure_fin": "19:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Classique intermédiaire", "jour": "Jeudi", "heure_debut": "18:00", "heure_fin": "19:00", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Jazz intermédiaire", "jour": "Mardi", "heure_debut": "18:00", "heure_fin": "19:15", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Classique avancé", "jour": "Jeudi", "heure_debut": "19:00", "heure_fin": "20:30", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Jazz avancé", "jour": "Vendredi", "heure_debut": "18:30", "heure_fin": "20:00", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
    {"nom": "Contemporain", "jour": "Vendredi", "heure_debut": "20:00", "heure_fin": "21:30", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
]

# SEED_DATA_DIR (voir Dockerfile, même pattern que DATABASE_URL/VIDEOS_DIR) :
# une fois `pip install .`, ce fichier tourne depuis site-packages, pas
# depuis l'arborescence source — `parents[2]` (qui marche en dev, lancé
# depuis backend/src/app/seed.py) ne pointe plus vers backend/seed_data/
# dans ce cas. Le fallback reste utile pour `python -m app.seed` en dev,
# sans venv installé en mode editable.
_SEED_DATA_DIR = os.environ.get("SEED_DATA_DIR")
FICHIER_ELEVES_DEMO = (
    Path(_SEED_DATA_DIR) / "eleves_demo.xlsx"
    if _SEED_DATA_DIR
    else Path(__file__).resolve().parents[2] / "seed_data" / "eleves_demo.xlsx"
)


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ecoles = Ecoles()
    comptes = Comptes()
    cours_service = CoursService()
    eleves_service = Eleves(comptes=comptes)
    import_excel = ImportExcel(eleves=eleves_service, cours=cours_service)

    try:
        ecole = ecoles.find_by_nom_code_postal(db, "Contretemps", "83330")
        if ecole:
            print(f"École 'Contretemps' déjà présente (id={ecole.id}).")
        else:
            # Codes simplifiés (voir mockData.js : ADMIN/PROF/ELEVE), pas
            # les valeurs par défaut ADMIN_CONTRETEMPS_2026 générées par
            # ecoles.create — l'admin peut les changer ensuite (§6.1).
            ecole = ecoles.create(
                db,
                nom="Contretemps",
                code_postal="83330",
                code_acces_admin="ADMIN",
                code_acces_prof="PROF",
                code_acces_eleve="ELEVE",
            )
            print(f"École 'Contretemps' créée (id={ecole.id}).")

        admins_existants = comptes.list_par_role(db, ecole.id, "admin")
        if admins_existants:
            print("Admin de démo déjà présent, ignoré.")
        else:
            admin = comptes.create(
                db,
                ecole_id=ecole.id,
                role="admin",
                nom="Dho",
                prenom="Julia",
                email="j.dho@contretemps.fr",
            )
            print(f"Admin 'Julia Dho' créée (id={admin.id}).")

        profs_par_nom_prenom = {}
        for p in PROFS_CONTRETEMPS:
            existantes = comptes.trouver_par_nom_prenom(
                db, ecole.id, p["nom"], p["prenom"], role="professeur"
            )
            if existantes:
                prof = existantes[0]
                print(f"Prof {p['prenom']} {p['nom']} déjà présente, ignorée.")
            else:
                prof = comptes.create(db, ecole_id=ecole.id, role="professeur", **p)
                print(f"Prof {p['prenom']} {p['nom']} créée (id={prof.id}).")
            profs_par_nom_prenom[(p["nom"], p["prenom"])] = prof

        cours_existants = {c.nom for c in cours_service.list(db, ecole.id)}
        for c in COURS_CONTRETEMPS:
            if c["nom"] in cours_existants:
                print(f"Cours '{c['nom']}' déjà présent, ignoré.")
                continue
            cours = cours_service.create(
                db,
                ecole_id=ecole.id,
                nom=c["nom"],
                jour=c["jour"],
                heure_debut=c["heure_debut"],
                heure_fin=c["heure_fin"],
                salle=c["salle"],
            )
            cours_service.ajouter_professeur(db, cours.id, profs_par_nom_prenom[c["prof"]].id)
            print(f"Cours '{c['nom']}' créé (id={cours.id}).")

        eleves_existants = comptes.list_par_role(db, ecole.id, "eleve")
        if eleves_existants:
            print(f"{len(eleves_existants)} élève(s) déjà présent(s), import ignoré.")
        elif not FICHIER_ELEVES_DEMO.exists():
            print(f"Fichier de démo introuvable ({FICHIER_ELEVES_DEMO}), élèves non importés.")
        else:
            with open(FICHIER_ELEVES_DEMO, "rb") as f:
                apercu = import_excel.previsualiser(db, ecole.id, f)
            resultat = import_excel.valider(db, ecole.id, apercu.lignes)
            print(f"Élèves importés depuis eleves_demo.xlsx : {resultat}")

        print("Seed terminé.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
