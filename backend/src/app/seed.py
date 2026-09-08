"""Recrée dans la vraie base les données de démo actuellement en dur dans
le frontend (voir frontend/src/data/mockData.js), pour que le jour où le
frontend se branche sur l'API, il retrouve exactement le même état.

⚠️ Partiel pour l'instant : seuls les modules ecoles/comptes existent côté
backend ce soir (voir spec §8, [[backend-architecture]]) — l'école, l'admin
de démo et les 4 vraies profs. Cours/élèves suivront quand les modules
cours/eleves/profs existeront.

Usage :
    python -m app.seed
"""

from comptes import Comptes
from db import Base, SessionLocal, engine
from ecoles import Ecoles

# Source : page publique dansecontretemps.fr/professeurs-danse-beausset
# (pas d'email public -> laissé vide, à compléter par l'admin).
PROFS_CONTRETEMPS = [
    {"nom": "Pesenti", "prenom": "Marie-Laure"},
    {"nom": "Jullien", "prenom": "Pascale"},
    {"nom": "Thomas", "prenom": "Marysa"},
    {"nom": "Revelles", "prenom": "Stellina"},
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ecoles = Ecoles()
    comptes = Comptes()

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

        for p in PROFS_CONTRETEMPS:
            deja = comptes.trouver_par_nom_prenom(db, ecole.id, p["nom"], p["prenom"], role="professeur")
            if deja:
                print(f"Prof {p['prenom']} {p['nom']} déjà présente, ignorée.")
                continue
            prof = comptes.create(db, ecole_id=ecole.id, role="professeur", **p)
            print(f"Prof {p['prenom']} {p['nom']} créée (id={prof.id}).")

        print("Seed terminé.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
