"""Tests de l'import Excel des élèves (voir spec/SPEC.md §6.4bis)."""

import io
import os

from cours import CoursService
from ecoles import Ecoles
from openpyxl import Workbook

FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "seed_data", "eleves_demo.xlsx"
)

NOMS_COURS_REELS = [
    "Eveil",
    "Classique initiation",
    "Jazz initiation",
    "Classique moyen",
    "Jazz moyen",
    "Jazz junior",
    "Classique intermédiaire",
    "Jazz intermédiaire",
    "Classique avancé",
    "Jazz avancé",
    "Contemporain",
]


def _creer_ecole_avec_cours(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    cours_service = CoursService()
    for nom in NOMS_COURS_REELS:
        cours_service.create(db_session, ecole_id=ecole.id, nom=nom)
    return ecole


def test_previsualiser_le_fichier_demo(client, db_session):
    """80 élèves fictifs, colonnes de cours abrégées (voir §6.4bis :
    "Class Ini" -> Classique initiation), une colonne volontairement
    absente du mapping statique ("Contempo" -> Contemporain)."""
    ecole = _creer_ecole_avec_cours(db_session)

    with open(FIXTURE, "rb") as f:
        reponse = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        )
    assert reponse.status_code == 200
    apercu = reponse.json()

    assert len(apercu["lignes"]) == 80
    assert apercu["colonnes_non_reconnues_globales"] == ["Contempo"]
    assert all(ligne["action"] == "creer" for ligne in apercu["lignes"])

    # Le 1er élève a un cours reconnu via abréviation, et un cours via la
    # colonne "Contempo" (non reconnue) -> pas ajouté à cours_ids.
    premiere = apercu["lignes"][0]
    assert premiere["nom"] == "Jean"
    assert "Contempo" in premiere["colonnes_non_reconnues"]
    assert len(premiere["cours_ids"]) == 1  # "Jazz Av", "Contempo" exclu

    # Le téléphone du 1er élève a été "cassé" par Excel (voir fixture).
    assert premiere["telephone_suspect"] is True
    assert premiere["telephone"] == "661602371"


def test_colonne_non_reconnue_puis_memorisee(client, db_session):
    """Voir §6.4bis : après résolution manuelle une fois, la colonne est
    reconnue automatiquement aux imports suivants."""
    ecole = _creer_ecole_avec_cours(db_session)
    cours_contemporain = next(
        c for c in CoursService().list(db_session, ecole.id) if c.nom == "Contemporain"
    )

    with open(FIXTURE, "rb") as f:
        premier = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()
    assert premier["colonnes_non_reconnues_globales"] == ["Contempo"]

    reponse = client.post(
        "/eleves/import/mapping-colonne",
        params={"ecole_id": ecole.id},
        json={"en_tete_excel": "Contempo", "cours_id": cours_contemporain.id},
    )
    assert reponse.status_code == 201

    with open(FIXTURE, "rb") as f:
        second = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()
    assert second["colonnes_non_reconnues_globales"] == []
    premiere = second["lignes"][0]
    assert len(premiere["cours_ids"]) == 2  # "Jazz Av" + "Contempo" maintenant résolu


def test_valider_cree_les_eleves_et_les_inscrit_aux_cours(client, db_session):
    ecole = _creer_ecole_avec_cours(db_session)

    with open(FIXTURE, "rb") as f:
        apercu = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()

    reponse = client.post(
        "/eleves/import/valider",
        params={"ecole_id": ecole.id},
        json={"lignes": apercu["lignes"]},
    )
    assert reponse.status_code == 200
    resultat = reponse.json()
    assert resultat == {"crees": 80, "mis_a_jour": 0, "ignores": 0}

    reponse = client.get("/eleves", params={"ecole_id": ecole.id})
    assert len(reponse.json()) == 80
    premier = next(e for e in reponse.json() if e["nom"] == "Jean" and e["prenom"] == "Camille")
    assert premier["telephone"] == "661602371"
    # Contact parent : élève majeur dans la fixture -> pas de contact.
    assert premier["contacts"] == []


def test_reimport_detecte_les_doublons_par_nom_prenom_date_naissance(client, db_session):
    """Voir §6.4bis : détection par (nom, prénom, date_naissance), pas
    par email (frères/sœurs qui le partagent)."""
    ecole = _creer_ecole_avec_cours(db_session)

    with open(FIXTURE, "rb") as f:
        apercu = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()
    client.post(
        "/eleves/import/valider", params={"ecole_id": ecole.id}, json={"lignes": apercu["lignes"]}
    )

    with open(FIXTURE, "rb") as f:
        second_apercu = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()

    assert all(ligne["action"] == "mettre_a_jour" for ligne in second_apercu["lignes"])
    assert all(ligne["eleve_existant_id"] is not None for ligne in second_apercu["lignes"])

    resultat = client.post(
        "/eleves/import/valider",
        params={"ecole_id": ecole.id},
        json={"lignes": second_apercu["lignes"]},
    ).json()
    assert resultat == {"crees": 0, "mis_a_jour": 80, "ignores": 0}
    # Toujours 80 élèves en base, pas de doublon créé.
    assert len(client.get("/eleves", params={"ecole_id": ecole.id}).json()) == 80


def test_ignorer_une_ligne_ne_lecrit_pas(client, db_session):
    ecole = _creer_ecole_avec_cours(db_session)
    with open(FIXTURE, "rb") as f:
        apercu = client.post(
            "/eleves/import/previsualiser",
            params={"ecole_id": ecole.id},
            files={"fichier": ("eleves.xlsx", f, "application/vnd.openxmlformats")},
        ).json()

    lignes = apercu["lignes"]
    lignes[0]["action"] = "ignorer"
    resultat = client.post(
        "/eleves/import/valider", params={"ecole_id": ecole.id}, json={"lignes": lignes}
    ).json()
    assert resultat == {"crees": 79, "mis_a_jour": 0, "ignores": 1}


def test_date_naissance_extraite_de_la_colonne_combinee():
    """Voir §6.4bis : "la partie avant le ' = '", l'âge écrit est ignoré."""
    from eleves.import_excel import _extraire_date_naissance

    assert _extraire_date_naissance("07/01/2006 = 20 ans") == __import__("datetime").date(
        2006, 1, 7
    )
    assert _extraire_date_naissance(None) is None


def test_telephone_texte_detecte_les_nombres_suspects():
    from eleves.import_excel import _telephone_texte

    assert _telephone_texte(661602371) == ("661602371", True)
    assert _telephone_texte("06 61 60 23 71") == ("06 61 60 23 71", False)
    assert _telephone_texte(None) == (None, False)


def test_mapping_colonne_introuvable_avant_memorisation(client, db_session):
    """Sans mapping mémorisé ni abréviation connue, une colonne inconnue
    reste non reconnue — vérifie juste l'absence de faux positif."""
    ecole = _creer_ecole_avec_cours(db_session)
    wb = Workbook()
    ws = wb.active
    ws.append(["Nom", "Prénom", "Colonne Mystere"])
    ws.append(["Dupont", "Marie", "X"])
    tampon = io.BytesIO()
    wb.save(tampon)
    tampon.seek(0)

    reponse = client.post(
        "/eleves/import/previsualiser",
        params={"ecole_id": ecole.id},
        files={"fichier": ("mini.xlsx", tampon, "application/vnd.openxmlformats")},
    )
    assert reponse.status_code == 200
    apercu = reponse.json()
    assert apercu["colonnes_non_reconnues_globales"] == ["Colonne Mystere"]
    assert apercu["lignes"][0]["cours_ids"] == []
