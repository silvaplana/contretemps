"""Recrée dans la vraie base les données de démo (école, comptes, cours,
élèves, présence, chorégraphies, vidéos), pour que le backend démarre
avec le même état que le frontend actuel (voir
frontend/src/data/mockData.js). Idempotent : relançable sans dupliquer,
vérifie l'existant avant de créer.

École/admin/profs/cours : en dur ici (petite liste stable, infos
publiques dansecontretemps.fr). Élèves : PAS dupliqués en dur une 3e fois
— lus depuis `seed_data/eleves_demo.xlsx` (80 élèves fictifs, mêmes
statistiques agrégées que le vrai fichier, voir spec §6.4bis) et importés
via `eleves.import_excel`, ce qui a l'avantage de tester ce module à
chaque seed. Présence/chorégraphies/vidéos : traduites ici depuis
PRESENCES_DEMO/CHOREGRAPHIES_DEMO, mêmes valeurs que mockData.js
(presencesParCours/choregraphiesParCours/videosParCours) — remplies
seulement pour "Éveil" et "Contempo Junior", comme côté frontend.

Usage :
    python -m app.seed
"""

import datetime as dt
import os
import shutil
from pathlib import Path

from choregraphies import Choregraphies
from comptes import Comptes
from cours import CoursService
from db import Base, SessionLocal, engine
from ecoles import Ecoles
from eleves import Eleves, ImportExcel
from messagerie import Conversations, Messages
from presence import Presence
from videos import (
    DOSSIER_VIDEOS_LIVE,
    DOSSIER_VIDEOS_REFERENCE,
    Videos,
    chemin_relatif,
    dossier_ecole,
    duree_secondes,
)

# Source profs/cours : page publique dansecontretemps.fr/professeurs-danse-beausset
# (pas d'email public -> convention interne, demande) : <1re lettre du
# prénom><1re lettre du nom>@contretemps.fr, en minuscules — même
# principe que jd@contretemps.fr pour l'admin (voir plus bas).
def _email_prof(prenom: str, nom: str) -> str:
    return f"{prenom[0]}{nom[0]}@contretemps.fr".lower()


# Marie-Laure Pesenti est "mère" d'une élève inscrite au cours Eveil (voir
# FAMILLES_DEMO ci-dessous, et _creer_familles_demo) : son email doit
# rester identique aux 2 endroits pour le regroupement familial (§6.2).
#
# Téléphone : désormais obligatoire à la création/modification d'un prof
# (voir AdminProfesseurs.jsx) — numéros ouvertement faux ici (demande),
# jamais de vrai numéro dans le seed de démo.
PROFS_CONTRETEMPS = [
    {
        "nom": "Pesenti", "prenom": "Marie-Laure",
        "email": _email_prof("Marie-Laure", "Pesenti"), "telephone": "06 00 00 00 01",
    },
    {
        "nom": "Jullien", "prenom": "Pascale",
        "email": _email_prof("Pascale", "Jullien"), "telephone": "06 00 00 00 02",
    },
    {
        "nom": "Thomas", "prenom": "Marysa",
        "email": _email_prof("Marysa", "Thomas"), "telephone": "06 00 00 00 03",
    },
    {
        "nom": "Revelles", "prenom": "Stellina",
        "email": _email_prof("Stellina", "Revelles"), "telephone": "06 00 00 00 04",
    },
]

# Démontre le sélecteur de profil famille (§2.1/§6.2 : regroupement par
# email partagé) avec de vraies données backend — même principe que
# mockData.js (familleActuelle). Julia Dho (admin) et Marie-Laure
# Pesenti (professeure) sont chacune "mère" d'élèves inscrites au cours
# Eveil : même nom, prénoms différents, email de la mère (voir
# _creer_familles_demo).
FAMILLES_DEMO = [
    {
        "nom": "Dho",
        "parent_prenom": "Julia",
        "parent_email": "jd@contretemps.fr",
        "parent_telephone": "06 12 34 56 78",
        "adresse": "2 rue des Micocouliers, Le Beausset",
        "enfants": [
            {"prenom": "Alix", "date_naissance": dt.date(2018, 4, 11)},
            {"prenom": "Zélie", "date_naissance": dt.date(2020, 8, 23)},
        ],
    },
    {
        "nom": "Pesenti",
        "parent_prenom": "Marie-Laure",
        "parent_email": _email_prof("Marie-Laure", "Pesenti"),
        "parent_telephone": "06 98 76 54 32",
        "adresse": "14 chemin des Oliviers, Le Beausset",
        "enfants": [
            {"prenom": "Nora", "date_naissance": dt.date(2019, 2, 14)},
        ],
    },
]

# heure_debut/heure_fin au format "HH:MM" (zéro-paddé, comparé
# lexicalement ailleurs — voir presence.statut_prof) : convention de
# STOCKAGE, différente de l'affichage "17h00" du frontend.
COURS_CONTRETEMPS = [
    {"nom": "Éveil", "jour": "Mercredi", "heure_debut": "17:00", "heure_fin": "17:45", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Class Ini", "jour": "Mercredi", "heure_debut": "17:45", "heure_fin": "18:30", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Jazz Ini", "jour": "Lundi", "heure_debut": "17:00", "heure_fin": "17:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Class Moy", "jour": "Mercredi", "heure_debut": "18:30", "heure_fin": "19:30", "salle": "Salle 1", "prof": ("Pesenti", "Marie-Laure")},
    {"nom": "Jazz Moy", "jour": "Lundi", "heure_debut": "17:45", "heure_fin": "18:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Street Moyen", "jour": "Mardi", "heure_debut": "17:00", "heure_fin": "17:45", "salle": "Salle 1", "prof": ("Thomas", "Marysa")},
    {"nom": "Jazz Junior", "jour": "Lundi", "heure_debut": "18:45", "heure_fin": "19:45", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Street Junior Inter", "jour": "Jeudi", "heure_debut": "18:00", "heure_fin": "19:00", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Class Inter", "jour": "Jeudi", "heure_debut": "18:00", "heure_fin": "19:00", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Jazz Inter", "jour": "Mardi", "heure_debut": "18:00", "heure_fin": "19:15", "salle": "Salle 2", "prof": ("Thomas", "Marysa")},
    {"nom": "Pointes inter", "jour": "Mercredi", "heure_debut": "19:30", "heure_fin": "20:15", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Pointes AV", "jour": "Jeudi", "heure_debut": "20:30", "heure_fin": "21:15", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Class AV", "jour": "Jeudi", "heure_debut": "19:00", "heure_fin": "20:30", "salle": "Salle 1", "prof": ("Jullien", "Pascale")},
    {"nom": "Jazz AV", "jour": "Vendredi", "heure_debut": "18:30", "heure_fin": "20:00", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
    {"nom": "Contempo Junior", "jour": "Mercredi", "heure_debut": "20:00", "heure_fin": "20:45", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
    {"nom": "Contempo Inter avance", "jour": "Jeudi", "heure_debut": "20:00", "heure_fin": "21:15", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
    {"nom": "Contempo Adulte", "jour": "Vendredi", "heure_debut": "20:00", "heure_fin": "21:30", "salle": "Salle 2", "prof": ("Revelles", "Stellina")},
]

# Voir mockData.js : presencesParCours ne remplit que "Éveil" (c1) et
# "Contempo Junior" (c11), à titre de démo — même chose ici. `None` dans
# "profs" = case vide (voir HEURES_VIDES côté frontend, "–" affiché).
PRESENCES_DEMO = {
    "Éveil": {
        "dates": [dt.date(2026, 9, 1), dt.date(2026, 9, 3), dt.date(2026, 9, 8)],
        "eleves": {
            ("Perrin", "Charlotte"): ["present", "present", "retard"],
            ("Thomas", "Coline"): ["present", "absent", "present"],
            ("Legrand", "Chloé"): ["present", "present", "present"],
        },
        "profs": {
            ("Pesenti", "Marie-Laure"): [
                {"heure_debut_reelle": "17:00", "heure_fin_reelle": "17:45", "depassement_minutes": 0},
                {"heure_debut_reelle": "17:03", "heure_fin_reelle": "17:50", "depassement_minutes": 5},
                None,
            ],
        },
    },
    "Contempo Junior": {
        "dates": [dt.date(2026, 9, 4), dt.date(2026, 9, 6)],
        "eleves": {
            ("Jean", "Camille"): ["present", "present"],
            ("Legrand", "Emma"): ["present", "retard"],
            ("Mercier", "Garance"): ["absent", "present"],
            ("Michel", "Nina"): ["present", "present"],
        },
        "profs": {
            ("Revelles", "Stellina"): [
                {"heure_debut_reelle": "20:00", "heure_fin_reelle": "21:30", "depassement_minutes": 0},
                None,
            ],
        },
    },
}

# Voir mockData.js : choregraphiesParCours/videosParCours, même limite
# (seulement "Éveil"/"Contempo Junior"). "fichier" fait référence à un mp4
# dans backend/videos_reference/<ecole_id>/ (voir videos/stockage.py) —
# `None` = vidéo sans fichier réel (juste une entrée, comme côté mock).
CHOREGRAPHIES_DEMO = {
    "Éveil": [
        {
            "nom": "Comme un garçon",
            "eleves": [("Perrin", "Charlotte"), ("Thomas", "Coline"), ("Legrand", "Chloé")],
            "costume": "Justaucorps noir, legging pailleté argent",
            "horaire_repetition": "Mercredi 17h00 - 17h45, salle 1",
            "videos": [
                {"nom": "Comme un garçon : détail début", "fichier": "comme-un-garcon-detail-debut.mp4"},
            ],
        },
        {
            "nom": "Bang bang",
            "eleves": [("Perrin", "Charlotte"), ("Thomas", "Coline")],
            "costume": "Combinaison rouge",
            "horaire_repetition": "Vendredi 18h00 - 19h00, salle 1",
            "videos": [
                {
                    "nom": "Bang bang (lent)",
                    "fichier": "bang-bang-lent.mp4",
                    "description": "Passage à retravailler : le déplacement diagonal.",
                },
            ],
        },
    ],
    "Contempo Junior": [
        {
            "nom": "Silhouettes",
            "eleves": [("Jean", "Camille"), ("Legrand", "Emma"), ("Mercier", "Garance")],
            "costume": "Body noir uni",
            "horaire_repetition": "Vendredi 20h00 - 21h30, salle 2",
            "videos": [{"nom": "Silhouettes — filage", "fichier": None}],
        },
    ],
}

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


def _copier_fichier_demo(ecole_id: int, nom_fichier: str) -> str:
    """Copie depuis la référence figée dans l'image (voir
    videos/stockage.py) vers le dossier "live" — sinon la ligne DB
    pointerait sur un fichier absent tant qu'un reset_demo (qui recopie
    tout) n'est pas lancé. Renvoie le chemin relatif à stocker en base
    (voir videos.chemin_relatif) que le fichier existe ou non côté
    référence (comportement identique pour lien_fichier/poster)."""
    cible = dossier_ecole(ecole_id) / nom_fichier
    if not cible.exists():
        source = DOSSIER_VIDEOS_REFERENCE / str(ecole_id) / nom_fichier
        if source.exists():
            shutil.copy(source, cible)
    return chemin_relatif(ecole_id, nom_fichier)


def _creer_familles_demo(db, ecole, comptes, eleves_service, cours_service) -> None:
    """Voir FAMILLES_DEMO ci-dessus. Idempotent (vérifie par nom+prénom
    avant de créer, comme le reste de ce fichier)."""
    cours_eveil = next((c for c in cours_service.list(db, ecole.id) if c.nom == "Éveil"), None)
    if cours_eveil is None:
        return
    for famille in FAMILLES_DEMO:
        for enfant in famille["enfants"]:
            if comptes.trouver_par_nom_prenom(
                db, ecole.id, famille["nom"], enfant["prenom"], role="eleve"
            ):
                print(f"Élève '{enfant['prenom']} {famille['nom']}' déjà présente, ignorée.")
                continue
            compte, _ = eleves_service.create(
                db,
                ecole_id=ecole.id,
                nom=famille["nom"],
                prenom=enfant["prenom"],
                email=famille["parent_email"],
                telephone=famille["parent_telephone"],
                date_naissance=enfant["date_naissance"],
                adresse=famille["adresse"],
                statut_paiement="paye",
                montant_total_annee=270,
                montant_paye=270,
            )
            eleves_service.ajouter_contact(
                db,
                eleve_id=compte.id,
                nom=famille["nom"],
                prenom=famille["parent_prenom"],
                lien="Mère",
                telephone=famille["parent_telephone"],
                email=famille["parent_email"],
            )
            cours_service.inscrire_eleve(db, cours_eveil.id, compte.id)
            print(
                f"Élève '{enfant['prenom']} {famille['nom']}' créée "
                f"(famille de {famille['parent_prenom']} {famille['nom']})."
            )


def _peupler_presence_choregraphies_videos(db, ecole, comptes, cours_service, profs_par_nom_prenom, admin) -> None:
    """Voir PRESENCES_DEMO/CHOREGRAPHIES_DEMO ci-dessus. Inscrit aussi les
    élèves concernés au cours si besoin (l'import Excel n'inscrit que les
    colonnes reconnues, voir eleves/import_excel.py — "Contempo" ne l'est
    pas par défaut, exprès, pour exercer ce flux)."""

    def trouver_eleve(nom, prenom):
        resultats = comptes.trouver_par_nom_prenom(db, ecole.id, nom, prenom, role="eleve")
        return resultats[0] if resultats else None

    presence = Presence(cours=cours_service)
    choregraphies_service = Choregraphies(cours=cours_service)
    videos_service = Videos(cours=cours_service)
    cours_par_nom = {c.nom: c for c in cours_service.list(db, ecole.id)}

    for nom_cours, donnees in PRESENCES_DEMO.items():
        cours = cours_par_nom.get(nom_cours)
        if cours is None or presence.lister_seances(db, cours.id):
            continue  # cours absent, ou déjà peuplé (idempotent)
        seances = [presence.creer_seance(db, cours.id, date) for date in donnees["dates"]]
        for (nom, prenom), statuts in donnees["eleves"].items():
            eleve = trouver_eleve(nom, prenom)
            if eleve is None:
                continue
            cours_service.inscrire_eleve(db, cours.id, eleve.id)
            for seance, statut in zip(seances, statuts):
                presence.set_presence_eleve(db, seance.id, eleve.id, statut)
        for (nom, prenom), heures_par_seance in donnees["profs"].items():
            prof = profs_par_nom_prenom.get((nom, prenom))
            if prof is None:
                continue
            for seance, heures in zip(seances, heures_par_seance):
                if heures is not None:
                    presence.set_presence_prof(db, seance.id, prof.id, **heures)
        print(f"Présence de démo créée pour '{nom_cours}' ({len(seances)} séance(s)).")

    for nom_cours, choregraphies_liste in CHOREGRAPHIES_DEMO.items():
        cours = cours_par_nom.get(nom_cours)
        if cours is None or choregraphies_service.list(db, cours.id):
            continue  # cours absent, ou déjà peuplé (idempotent)
        for ch_donnees in choregraphies_liste:
            choregraphie = choregraphies_service.create(
                db,
                cours.id,
                nom=ch_donnees["nom"],
                costume=ch_donnees["costume"],
                horaire_repetition=ch_donnees["horaire_repetition"],
            )
            for nom, prenom in ch_donnees["eleves"]:
                eleve = trouver_eleve(nom, prenom)
                if eleve is None:
                    continue
                cours_service.inscrire_eleve(db, cours.id, eleve.id)
                choregraphies_service.ajouter_eleve(db, choregraphie.id, eleve.id)
            for v in ch_donnees["videos"]:
                lien_fichier = ""
                poster = None
                duree = None
                if v["fichier"]:
                    lien_fichier = _copier_fichier_demo(ecole.id, v["fichier"])
                    # Vignette dérivée du même nom (voir génération des
                    # .jpg — même base, extension différente) : "voir un
                    # rapidement la photo de la vidéo" sans lancer le
                    # lecteur, et surtout affiche QUELQUE CHOSE sur mobile
                    # (Chrome/Brave/Samsung Internet Android n'affichent
                    # pas la 1re image automatiquement, contrairement à
                    # Chrome desktop — sans poster, écran Vidéo "cassé").
                    nom_poster = Path(v["fichier"]).with_suffix(".jpg").name
                    poster = _copier_fichier_demo(ecole.id, nom_poster)
                    # Mesurée une fois ici (voir videos/duree.py) — le vrai
                    # upload (chantier suivant) fera pareil à la volée.
                    duree = duree_secondes(DOSSIER_VIDEOS_LIVE / lien_fichier)
                videos_service.create(
                    db,
                    cours_id=cours.id,
                    nom=v["nom"],
                    lien_fichier=lien_fichier,
                    poster=poster,
                    duree_secondes=duree,
                    description=v.get("description", ""),
                    choregraphie_id=choregraphie.id,
                    uploaded_by=admin.id,
                )
            print(f"Chorégraphie '{ch_donnees['nom']}' créée pour '{nom_cours}'.")


def _creer_conversations_demo(db, ecole, comptes, cours_service, profs_par_nom_prenom, admin) -> None:
    """Conversations de démo (voir spec/SPEC.md §6.9, et l'ancien
    frontend/src/data/mockData.js: groupes/conversations, pas encore
    supprimé — voir api/conversations.js) : un groupe automatique de
    cours (Éveil), l'équipe pédagogique, et un DM avec une élève — pour
    ne pas atterrir sur un écran Messagerie/Admin > Conversations vide
    après un reset_demo."""
    conversations = Conversations(comptes=comptes, cours=cours_service)
    messages = Messages(conversations=conversations)

    if conversations.lister_ecole(db, ecole.id):
        print("Conversations de démo déjà présentes, ignorées.")
        return

    cours_eveil = next((c for c in cours_service.list(db, ecole.id) if c.nom == "Éveil"), None)
    charlotte_resultats = comptes.trouver_par_nom_prenom(db, ecole.id, "Perrin", "Charlotte", role="eleve")
    charlotte = charlotte_resultats[0] if charlotte_resultats else None

    if cours_eveil:
        groupe_eveil = conversations.creer_conversation_cours(db, ecole.id, cours_eveil.id)
        prof_eveil = profs_par_nom_prenom.get(("Pesenti", "Marie-Laure"))
        if prof_eveil:
            messages.envoyer(
                db, groupe_eveil.id, prof_eveil.id,
                "Petit filage supplémentaire mercredi prochain, 17h15.",
            )
        if charlotte:
            messages.envoyer(db, groupe_eveil.id, charlotte.id, "Confirmez par mail ?")

    membres_equipe = [("compte", p.id) for p in profs_par_nom_prenom.values()] + [("compte", admin.id)]
    equipe = conversations.create_groupe(db, ecole.id, "Equipe pédagogique", membres_equipe)
    prof_jullien = profs_par_nom_prenom.get(("Jullien", "Pascale"))
    if prof_jullien:
        messages.envoyer(db, equipe.id, prof_jullien.id, "Réunion planning la semaine prochaine ?")

    if charlotte:
        dm = conversations.create_ou_obtenir_dm(db, ecole.id, admin.id, charlotte.id)
        messages.envoyer(db, dm.id, charlotte.id, "A quelle heure le cours de mercredi ?")
        messages.envoyer(
            db, dm.id, admin.id, "17h00 - 17h45, salle 1", envoi_volontaire_email=True
        )

    print("Conversations de démo créées (Eveil, Equipe pédagogique, DM avec Charlotte).")


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
                email="jd@contretemps.fr",
                # Ouvertement faux (demande) — jamais de vrai numéro dans
                # le seed de démo.
                telephone="06 00 00 00 00",
                # "Nom de votre 1er animal de compagnie" (voir "Code
                # oublié ?" à l'écran de connexion, et NouvelleEcoleModal).
                code_recuperation="coocky",
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

        _creer_familles_demo(db, ecole, comptes, eleves_service, cours_service)

        # `admin` n'existe que dans la branche "nouvellement créé"
        # ci-dessus — le récupérer dans tous les cas (uploaded_by des
        # vidéos de démo, voir _peupler_presence_choregraphies_videos).
        admin = comptes.list_par_role(db, ecole.id, "admin")[0]
        _peupler_presence_choregraphies_videos(
            db, ecole, comptes, cours_service, profs_par_nom_prenom, admin
        )
        _creer_conversations_demo(db, ecole, comptes, cours_service, profs_par_nom_prenom, admin)

        print("Seed terminé.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
