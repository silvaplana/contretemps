"""Tests bout-en-bout des routes /inscriptions (voir
spec/SPEC-inscription.md). École + 17 cours seedés comme dans
test_import_excel.py:_creer_ecole_avec_cours. Écrit dans le vrai dossier
de stockage par défaut puis nettoie (même patron que
test_videos.py:test_upload_reel — pas de monkeypatch d'env, les chemins
sont résolus au niveau module)."""

import io
import shutil

import pytest
from cours import CoursService
from ecoles import Ecoles
from inscriptions.stockage import DOSSIER_INSCRIPTIONS
from PIL import Image

NOMS_COURS_REELS = [
    "Éveil", "Class Ini", "Jazz Ini", "Class Moy", "Jazz Moy", "Street Moyen",
    "Jazz Junior", "Street Junior Inter", "Class Inter", "Jazz Inter",
    "Pointes inter", "Pointes AV", "Class AV", "Jazz AV", "Contempo Junior",
    "Contempo Inter avance", "Contempo Adulte",
]


def _creer_ecole_avec_cours(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    cours_service = CoursService()
    cours = {}
    for nom in NOMS_COURS_REELS:
        cours[nom] = cours_service.create(db_session, ecole_id=ecole.id, nom=nom)
    return ecole, cours


@pytest.fixture()
def _nettoyage_dossier():
    dossiers = []
    yield dossiers
    for dossier in dossiers:
        shutil.rmtree(dossier, ignore_errors=True)


def _donnees_formulaire(cours_ids, **overrides):
    donnees = {
        "eleve_nom": "Dupont",
        "eleve_prenom": "Marie",
        "eleve_date_naissance": "2018-11-17",
        "eleve_adresse": "1 rue du Test",
        "eleve_telephone": "0600000000",
        "eleve_email": "marie@example.com",
        "cours_ids": cours_ids,
        "allergies": None,
        "traitement_medical": None,
        "informations_importantes": None,
        "contact_urgence_nom": "Dupont",
        "contact_urgence_prenom": "Jean",
        "contact_urgence_lien": "Père",
        "contact_urgence_telephone": "0611111111",
        "droit_image_autorise": True,
        "droit_image_site": True,
        "droit_image_reseaux": False,
        "droit_image_affiches": False,
        "reglement_lu_approuve": True,
        "signataire_nom": "Jean Dupont",
        "moyen_paiement": "cheque",
    }
    donnees.update(overrides)
    return donnees


def test_creer_une_inscription(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    reponse = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id, cours["Jazz Ini"].id]),
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["saison"]
    assert sorted(corps["cours_choisis"]) == ["Class Ini", "Jazz Ini"]
    assert corps["nb_cours_semaine"] == 2
    assert corps["montant_mensuel_septembre"] == 50.0
    assert corps["doublon_possible"] is False
    assert corps["alerte_palier_mixte"] is False
    # SMTP non configuré en test -> email désactivé silencieusement.
    assert corps["email_envoye"] is False

    token = corps["token_public"]
    dossier_pdf = client.get(f"/inscriptions/{token}/dossier.pdf")
    assert dossier_pdf.status_code == 200
    assert dossier_pdf.content.startswith(b"%PDF")

    facture_pdf = client.get(f"/inscriptions/{token}/facture.pdf")
    assert facture_pdf.status_code == 200
    assert facture_pdf.content.startswith(b"%PDF")


def test_doublon_detecte_sur_meme_nom_prenom_meme_saison(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    )
    reponse = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    )
    assert reponse.json()["doublon_possible"] is True


def test_reduction_famille_appliquee_au_2e_enfant_meme_email(
    client, db_session, _nettoyage_dossier
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id], eleve_prenom="Marie"),
    )
    reponse = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id], eleve_prenom="Léo"),
    )
    corps = reponse.json()
    assert corps["reduction_famille_appliquee"] is True
    assert corps["montant_mensuel_septembre"] == 42.0 - 5.0


def test_palier_mixte_detecte_et_alerte(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    reponse = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id, cours["Class Inter"].id]),
    )
    corps = reponse.json()
    assert corps["alerte_palier_mixte"] is True
    assert corps["palier_tarifaire"] == "junior_et_plus"


def test_export_sans_inscription_404(client, db_session):
    ecole = Ecoles().create(db_session, nom="Vide", code_postal="00000")
    reponse = client.get("/inscriptions/export", params={"ecole_id": ecole.id})
    assert reponse.status_code == 404


def test_export_contient_les_inscriptions(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    )
    reponse = client.get("/inscriptions/export", params={"ecole_id": ecole.id})
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_dossier_pdf_token_inconnu_404(client, db_session):
    reponse = client.get("/inscriptions/token-inexistant/dossier.pdf")
    assert reponse.status_code == 404


def _image_test() -> io.BytesIO:
    tampon = io.BytesIO()
    Image.new("RGB", (120, 160), color=(200, 120, 60)).save(tampon, format="JPEG")
    tampon.seek(0)
    return tampon


def test_upload_photo_puis_regeneration_du_dossier_pdf(client, db_session, _nettoyage_dossier):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))

    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Éveil"].id]),
    ).json()
    token = corps["token_public"]
    dossier_avant = client.get(f"/inscriptions/{token}/dossier.pdf").content

    reponse = client.post(
        f"/inscriptions/{token}/photo",
        files={"fichier": ("photo.jpg", _image_test(), "image/jpeg")},
    )
    assert reponse.status_code == 204

    dossier_apres = client.get(f"/inscriptions/{token}/dossier.pdf")
    assert dossier_apres.status_code == 200
    assert dossier_apres.content.startswith(b"%PDF")
    # Le dossier a bien changé (photo incluse) — comparaison grossière,
    # la taille du fichier suffit à vérifier qu'autre chose a été inséré.
    assert dossier_apres.content != dossier_avant


def test_upload_photo_token_inconnu_404(client, db_session):
    reponse = client.post(
        "/inscriptions/token-inexistant/photo",
        files={"fichier": ("photo.jpg", _image_test(), "image/jpeg")},
    )
    assert reponse.status_code == 404
