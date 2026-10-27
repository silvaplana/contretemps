"""« Usage ressources et IA de la saison » (Admin > École, spec §5.1.1) :
place sur le disque par école, coût des opérations d'IA par poste."""

import shutil

import pytest
from app.main import ressources_client
from comptes import Comptes
from documents_contretemps import DOSSIER_DOCUMENTS
from ecoles import Ecoles
from inscriptions.stockage import DOSSIER_INSCRIPTIONS
from videos import dossier_ecole


@pytest.fixture()
def ecole(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    # D'autres tests laissent des fichiers sous le même numéro d'école.
    shutil.rmtree(DOSSIER_INSCRIPTIONS / str(ecole.id), ignore_errors=True)
    shutil.rmtree(dossier_ecole(ecole.id), ignore_errors=True)
    shutil.rmtree(DOSSIER_DOCUMENTS / str(ecole.id), ignore_errors=True)
    yield ecole
    shutil.rmtree(DOSSIER_INSCRIPTIONS / str(ecole.id), ignore_errors=True)
    shutil.rmtree(dossier_ecole(ecole.id), ignore_errors=True)


def test_memoire_et_ia_par_poste(client, db_session, ecole):
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    (dossier_ecole(ecole.id) / "film.mp4").write_bytes(b"x" * 3000)
    documents = DOSSIER_INSCRIPTIONS / str(ecole.id)
    documents.mkdir(parents=True, exist_ok=True)
    (documents / "dossier.pdf").write_bytes(b"x" * 500)

    ressources_client.noter_ia(db_session, ecole.id, "lecture_fiche", 0.03, "2 pages")
    ressources_client.noter_ia(db_session, ecole.id, "lecture_fiche", 0.02)
    ressources_client.noter_ia(db_session, ecole.id, "detourage_logo", 0.0)
    ressources_client.noter_ia(db_session, autre.id, "lecture_fiche", 9.0)

    usage = client.get(f"/ecoles/{ecole.id}/ressources").json()
    assert usage["saison"]
    assert {r["cle"]: r["octets"] for r in usage["memoire"]} == {"videos": 3000, "documents": 500, "personnalisation": 0, "documents_partages": 0, "notes_frais": 0, "messagerie": 0, "membres": 0}
    assert usage["memoire_total_octets"] == 3500
    assert usage["ia"] == [
        {"categorie": "lecture_fiche", "libelle": "Lecture des fiches d'inscription", "nombre": 2, "cout_usd": 0.05},
        {"categorie": "detourage_logo", "libelle": "Personnalisation : détourage du logo", "nombre": 1, "cout_usd": 0.0},
    ]
    assert usage["ia_total_usd"] == usage["ia_total_toutes_saisons_usd"] == 0.05


def test_une_lecture_de_fiche_est_relevee(client, db_session, ecole, monkeypatch):
    from app.main import inscriptions_receiver
    from test_inscriptions_fiches import FausseLecture

    monkeypatch.setattr(inscriptions_receiver.fiches, "lecture", FausseLecture())
    fichiers = [("fichiers", ("p.jpg", b"\xff\xd8\xff\xe0" + b"0" * 64, "image/jpeg"))]
    assert client.post("/inscriptions/fiches", params={"ecole_id": ecole.id}, files=fichiers).status_code == 201
    usage = client.get(f"/ecoles/{ecole.id}/ressources").json()
    assert usage["ia"][0]["categorie"] == "lecture_fiche" and usage["ia"][0]["cout_usd"] == 0.022


@pytest.mark.rbac_reel
def test_reserve_aux_admins(client, db_session, ecole):
    from conftest import entetes_session

    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="M", prenom="Z")
    assert client.get(f"/ecoles/{ecole.id}/ressources", headers=entetes_session(eleve)).status_code == 403
