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


def test_enregistrer_l_eleve_dans_la_liste_officielle(client, db_session, ecole_et_cours, lecture, monkeypatch):
    """Pas d'inscription en attente : un élève de la liste officielle, avec
    ses cours et son contact, et un mail à l'admin avec les photos."""
    from inscriptions.models import Inscription
    from sqlalchemy import select

    ecole, cours = ecole_et_cours
    fiches = inscriptions_receiver.fiches
    mails = []
    monkeypatch.setattr(fiches.email, "actif", True)
    monkeypatch.setattr(fiches.email, "adresse_admin", "admin@example.com")
    monkeypatch.setattr(fiches.email, "envoyer_confirmation", lambda *a, **k: mails.append(a))
    jeton = _lire(client, ecole).json()["jeton"]
    donnees = _donnees_formulaire([cours["Class Ini"].id, cours["Jazz Ini"].id], eleve_email=None)

    reponse = client.post(f"/inscriptions/fiches/{jeton}/eleve", json=donnees)
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["mail_envoye"] is True and corps["mail_adresse"] == "admin@example.com"
    assert corps["cout_usd"] == 0.022

    eleve = next(e for e in client.get("/eleves", params={"ecole_id": ecole.id}).json() if e["id"] == corps["eleve_id"])
    assert (eleve["nom"], eleve["prenom"], eleve["date_naissance"]) == ("Dupont", "Marie", "2018-11-17")
    assert eleve["contacts"][0]["prenom"] == "Jean" and eleve["contacts"][0]["lien"] == "Père"
    assert "Droit à l'image : oui (site internet)" in eleve["commentaire_admin"]
    assert "Règlement signé par Jean Dupont" in eleve["commentaire_admin"]
    assert eleve["montant_total_annee"] == 40 + 3 * 150
    assert sorted(c.nom for c in fiches.cours.cours_de_leleve(db_session, eleve["id"])) == ["Class Ini", "Jazz Ini"]
    assert db_session.scalars(select(Inscription).where(Inscription.ecole_id == ecole.id)).all() == []

    destinataire, sujet, texte, pieces = mails[0]
    assert destinataire == "admin@example.com"
    assert sujet == f"Inscription papier validée de Marie Dupont à l'école {ecole.nom} pour la saison {corps['saison']}"
    # Le dossier rempli (même PDF que l'inscription en ligne), puis les photos.
    assert [nom for nom, _ in pieces] == [
        f"dossier_marie_dupont_{corps['saison'].replace('-', '')}.pdf", "fiche-1.jpg", "fiche-2.jpg",
    ]
    assert pieces[0][1].startswith(b"%PDF") and pieces[1][1] == JPEG

    # Le brouillon et ses photos sont effacés ; il ne sert qu'une fois.
    assert not list((DOSSIER_INSCRIPTIONS / str(ecole.id)).glob("fiche-*"))
    assert client.post(f"/inscriptions/fiches/{jeton}/eleve", json=donnees).status_code == 404


def test_homonyme_signale_avant_d_enregistrer(client, ecole_et_cours, lecture):
    ecole, cours = ecole_et_cours
    donnees = _donnees_formulaire([cours["Éveil"].id])
    jeton = _lire(client, ecole).json()["jeton"]
    assert client.post(f"/inscriptions/fiches/{jeton}/eleve", json=donnees).status_code == 201

    jeton = _lire(client, ecole).json()["jeton"]
    refus = client.post(f"/inscriptions/fiches/{jeton}/eleve", json=donnees)
    assert refus.status_code == 409 and "existe déjà" in refus.json()["detail"]
    # Le brouillon est toujours là : l'admin peut confirmer.
    force = client.post(f"/inscriptions/fiches/{jeton}/eleve", params={"malgre_homonyme": True}, json=donnees)
    assert force.status_code == 201 and force.json()["mail_envoye"] is False


def test_sans_fiche_l_email_reste_obligatoire(client, ecole_et_cours):
    ecole, cours = ecole_et_cours
    donnees = _donnees_formulaire([cours["Éveil"].id], eleve_email=None)
    assert client.post("/inscriptions", params={"ecole_id": ecole.id}, json=donnees).status_code == 422
    inconnu = "5b1d0a3e-0000-4000-8000-000000000000"
    assert client.post(f"/inscriptions/fiches/{inconnu}/eleve", json=donnees).status_code == 404


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
