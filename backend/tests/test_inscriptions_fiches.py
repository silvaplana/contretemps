"""Fiches d'inscription papier lues automatiquement (voir
inscriptions/fiches.py). Le modèle n'est jamais appelé ici : une fausse
lecture renvoie ce qu'il aurait lu."""

import shutil

import pytest
from app.main import inscriptions_receiver
from inscriptions.lecture_fiche import FicheLue, LectureIndisponible, ResultatLecture, cout_usd
from inscriptions.stockage import DOSSIER_INSCRIPTIONS
from test_inscriptions import _creer_ecole_avec_cours, _donnees_formulaire

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


class FausseLecture:
    actif = True

    def __init__(self):
        self.appels = []
        self.fiche = {}
        self.erreur = None

    def lire(self, pages, cours):
        self.appels.append((pages, cours))
        if self.erreur:
            raise self.erreur
        champs = {nom: None for nom in FicheLue.model_fields}
        champs.update(
            cours_ids=[], champs_douteux=[], droit_image_autorise=False, droit_image_site=False,
            droit_image_reseaux=False, droit_image_affiches=False, reglement_signe=True,
        )
        champs.update(self.fiche)
        return ResultatLecture(FicheLue(**champs), "claude-opus-5-5", 3000, 500, cout_usd("claude-opus-5-5", 3000, 500))


@pytest.fixture()
def lecture(monkeypatch):
    fausse = FausseLecture()
    monkeypatch.setattr(inscriptions_receiver.fiches, "lecture", fausse)
    return fausse


@pytest.fixture()
def ecole_et_cours(db_session):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    yield ecole, cours
    shutil.rmtree(DOSSIER_INSCRIPTIONS / str(ecole.id), ignore_errors=True)


def _lire(client, ecole, nb_pages=2):
    fichiers = [("fichiers", (f"page{n}.jpg", JPEG, "image/jpeg")) for n in range(nb_pages)]
    return client.post("/inscriptions/fiches", params={"ecole_id": ecole.id}, files=fichiers)


def test_cout_d_une_lecture():
    assert cout_usd("claude-opus-5-5", 1_000_000, 0) == 4.0
    assert cout_usd("claude-opus-5-5", 3000, 500) == 0.022
    # Modèle inconnu : prix du modèle demandé.
    assert cout_usd("autre", 0, 1_000_000) == 20.0


def test_lecture_puis_brouillon(client, ecole_et_cours, lecture):
    ecole, cours = ecole_et_cours
    lecture.fiche = {
        "eleve_nom": "MARTIN", "eleve_prenom": "Zoé", "eleve_date_naissance": "2017-03-09",
        "cours_ids": [cours["Jazz Ini"].id, 999999], "champs_douteux": ["eleve_email", "inconnu"],
        "eleve_email": "zoe@example.com", "remarques": "Verso flou.",
    }
    reponse = _lire(client, ecole)
    assert reponse.status_code == 201
    lue = reponse.json()
    assert lue["nb_pages"] == 2 and lue["cout_usd"] == 0.022
    # Le modèle reçoit les deux pages et les cours de l'école.
    pages, cours_proposes = lecture.appels[0]
    assert len(pages) == 2 and (cours["Jazz Ini"].id, "Jazz Ini") in cours_proposes

    brouillon = client.get(f"/inscriptions/fiches/{lue['jeton']}").json()
    assert brouillon["donnees"]["eleve_nom"] == "MARTIN"
    # Un cours inconnu est écarté, et les cours sont alors à vérifier.
    assert brouillon["donnees"]["cours_ids"] == [cours["Jazz Ini"].id]
    assert brouillon["champs_douteux"] == ["cours_ids", "eleve_email"]
    assert brouillon["remarques"] == "Verso flou."
    assert brouillon["types_pages"] == ["image/jpeg", "image/jpeg"]

    page = client.get(f"/inscriptions/fiches/{lue['jeton']}/pages/2")
    assert page.status_code == 200 and page.content == JPEG
    assert client.get(f"/inscriptions/fiches/{lue['jeton']}/pages/3").status_code == 404


def test_date_illisible_ecartee(client, ecole_et_cours, lecture):
    ecole, cours = ecole_et_cours
    lecture.fiche = {"eleve_date_naissance": "09/03/2017", "cours_ids": [cours["Éveil"].id]}
    brouillon = client.get(f"/inscriptions/fiches/{_lire(client, ecole).json()['jeton']}").json()
    assert brouillon["donnees"]["eleve_date_naissance"] is None
    assert brouillon["champs_douteux"] == ["eleve_date_naissance"]


def test_inscription_depuis_une_fiche_sans_email(client, ecole_et_cours, lecture):
    """La fiche papier peut ne pas porter d'email ; ses photos sont
    rattachées à l'inscription et le brouillon disparaît."""
    ecole, cours = ecole_et_cours
    jeton = _lire(client, ecole).json()["jeton"]
    donnees = _donnees_formulaire([cours["Éveil"].id], eleve_email=None)

    reponse = client.post("/inscriptions", params={"ecole_id": ecole.id, "fiche": jeton}, json=donnees)
    assert reponse.status_code == 201
    token = reponse.json()["token_public"]
    dossier = DOSSIER_INSCRIPTIONS / str(ecole.id)
    assert sorted(f.name for f in dossier.glob(f"{token}-fiche-*")) == [
        f"{token}-fiche-1.jpg", f"{token}-fiche-2.jpg",
    ]
    assert not list(dossier.glob("fiche-*"))
    assert client.get(f"/inscriptions/fiches/{jeton}").status_code == 404

    # Paiement par chèque : la finalisation passe, sans mail à envoyer.
    paiement = client.post(
        f"/inscriptions/{token}/paiement/choix", json={"moyen_paiement": "cheque", "paiement_nb_echeances": 1}
    )
    assert paiement.status_code == 200 and paiement.json()["email_envoye"] is False


def test_sans_fiche_l_email_reste_obligatoire(client, ecole_et_cours):
    ecole, cours = ecole_et_cours
    donnees = _donnees_formulaire([cours["Éveil"].id], eleve_email=None)
    assert client.post("/inscriptions", params={"ecole_id": ecole.id}, json=donnees).status_code == 422
    inconnue = {"ecole_id": ecole.id, "fiche": "5b1d0a3e-0000-4000-8000-000000000000"}
    assert client.post("/inscriptions", params=inconnue, json=donnees).status_code == 404


def test_annuler_efface_le_brouillon(client, ecole_et_cours, lecture):
    ecole, _ = ecole_et_cours
    jeton = _lire(client, ecole).json()["jeton"]
    assert client.delete(f"/inscriptions/fiches/{jeton}").status_code == 204
    assert client.get(f"/inscriptions/fiches/{jeton}").status_code == 404
    assert not list((DOSSIER_INSCRIPTIONS / str(ecole.id)).glob("fiche-*"))


def test_jeton_fantaisiste_refuse(client):
    assert client.get("/inscriptions/fiches/..%2F..%2Fetc").status_code == 404
    assert client.get("/inscriptions/fiches/pas-un-jeton").status_code == 404


def test_fichiers_refuses_et_lecture_indisponible(client, ecole_et_cours, lecture):
    ecole, _ = ecole_et_cours
    texte = [("fichiers", ("fiche.txt", b"bonjour", "text/plain"))]
    assert client.post("/inscriptions/fiches", params={"ecole_id": ecole.id}, files=texte).status_code == 400
    assert _lire(client, ecole, nb_pages=5).status_code == 400
    assert lecture.appels == []

    lecture.erreur = LectureIndisponible("Le service de lecture est indisponible.")
    reponse = _lire(client, ecole)
    assert reponse.status_code == 503 and "indisponible" in reponse.json()["detail"]


@pytest.mark.rbac_reel
def test_lire_une_fiche_exige_une_session(client, ecole_et_cours, lecture):
    ecole, _ = ecole_et_cours
    assert _lire(client, ecole).status_code == 401
    assert lecture.appels == []


def test_une_case_cochee_vaut_autorisation_du_droit_a_l_image(client, ecole_et_cours, lecture):
    ecole, cours = ecole_et_cours
    lecture.fiche = {"cours_ids": [cours["Éveil"].id], "droit_image_reseaux": True}
    donnees = client.get(f"/inscriptions/fiches/{_lire(client, ecole).json()['jeton']}").json()["donnees"]
    assert donnees["droit_image_autorise"] is True

    # « J'autorise » rayé et cases cochées : contradictoire, laissé à l'admin.
    lecture.fiche["champs_douteux"] = ["droit_image_autorise"]
    brouillon = client.get(f"/inscriptions/fiches/{_lire(client, ecole).json()['jeton']}").json()
    assert brouillon["donnees"]["droit_image_autorise"] is False
    assert "droit_image_autorise" in brouillon["champs_douteux"]


def test_paiement_en_especes_finalise_tout_de_suite(client, ecole_et_cours):
    ecole, cours = ecole_et_cours
    token = client.post(
        "/inscriptions", params={"ecole_id": ecole.id}, json=_donnees_formulaire([cours["Éveil"].id])
    ).json()["token_public"]
    reponse = client.post(
        f"/inscriptions/{token}/paiement/choix", json={"moyen_paiement": "especes", "paiement_nb_echeances": 3}
    )
    assert reponse.status_code == 200 and reponse.json()["moyen_paiement"] == "especes"
    assert client.get(f"/inscriptions/{token}/facture.pdf").status_code == 200
