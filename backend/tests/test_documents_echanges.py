"""Bacs « Échanges » de l'onglet Docs (spec/modules/documents.md §4.7 ter)."""

from datetime import timedelta

import pytest
from comptes import Comptes, roles
from documents.models import DocNode, utcnow
from test_documents import Docs, _par_nom, _saison, _systeme, ecole, stockage  # noqa: F401

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def profs(db_session, ecole):  # noqa: F811
    comptes = Comptes()
    return {
        "zoe": comptes.create(db_session, ecole_id=ecole["id"], role="professeur", nom="Vidal", prenom="Zoé"),
        "max": comptes.create(db_session, ecole_id=ecole["id"], role="professeur", nom="Petit", prenom="Max"),
    }


def _bac(docs):
    return _systeme(docs, "exchange")["id"]


def test_le_bac_de_prive(client, ecole):  # noqa: F811
    prof, eleve = Docs(client, ecole["id"], ecole["prof"]), Docs(client, ecole["id"], ecole["eleve"])
    bac = _bac(prof)
    # Ni renommé, ni supprimé, pas de dossier dedans ; les élèves ne le voient pas.
    assert prof.modifier(bac, name="Autre").status_code == 409
    assert prof.supprimer(bac).status_code == 409
    assert prof.dossier("Sous-dossier", bac).status_code == 409
    assert eleve.racine().json()["items"] == []

    assert prof.fichier("Planning.xlsx", bac).status_code == 201
    vu = prof.racine(dossier=bac).json()
    assert vu["can_add_folder"] is False
    [ligne] = vu["items"]
    assert ligne["sender"] == "Ima Blanc" and ligne["sent_by_me"] is True
    assert ligne["for_label"] is None and ligne["exchange_until"]
    assert "Planning.xlsx" in _par_nom(Docs(client, ecole["id"], ecole["admin"]).racine(dossier=bac))


def test_glisser_dans_le_bac_copie_et_ranger_le_sort(client, ecole):  # noqa: F811
    prof = Docs(client, ecole["id"], ecole["prof"])
    bac, saison = _bac(prof), _saison(prof)["id"]
    original = prof.fichier("Affiche.png", saison).json()["id"]
    copie = prof.c.post(f"{prof.base}/nodes/{original}/copy", json={"space": "private", "parent_id": bac}, headers=prof.h)
    assert copie.status_code == 201
    assert "Affiche.png" in _par_nom(prof.racine(dossier=saison))
    assert _par_nom(prof.racine(dossier=bac))["Affiche.png"]["exchange_until"]

    # Ranger : il quitte le bac et perd sa date de fin.
    dossier = prof.dossier("Affiches", saison).json()["id"]
    assert prof.modifier(copie.json()["id"], move=True, space="private", parent_id=dossier).status_code == 200
    assert prof.racine(dossier=bac).json()["items"] == []
    assert "exchange_until" not in _par_nom(prof.racine(dossier=dossier))["Affiche.png"]


def test_au_bout_de_30_jours_le_bac_se_vide(client, db_session, ecole):  # noqa: F811
    prof = Docs(client, ecole["id"], ecole["prof"])
    bac = _bac(prof)
    node_id = prof.fichier("Vieux.pdf", bac).json()["id"]
    db_session.get(DocNode, node_id).exchange_until = utcnow() - timedelta(minutes=1)
    db_session.commit()

    assert prof.racine(dossier=bac).json()["items"] == []
    # Dans la corbeille de qui l'a déposé ; restauré, il reste encore 30 jours.
    [jete] = prof.get("/spaces/private/trash").json()
    assert jete["id"] == node_id
    assert prof.c.post(f"{prof.base}/nodes/{node_id}/restore", headers=prof.h).status_code == 200
    assert "Vieux.pdf" in _par_nom(prof.racine(dossier=bac))


def test_pour_une_personne(client, ecole, profs):  # noqa: F811
    ima = Docs(client, ecole["id"], ecole["prof"])
    zoe, max_ = Docs(client, ecole["id"], profs["zoe"]), Docs(client, ecole["id"], profs["max"])
    admin = Docs(client, ecole["id"], ecole["admin"])
    bac = _bac(ima)
    node_id = ima.fichier("Pour Zoé.docx", bac).json()["id"]
    pour = lambda qui, corps: qui.c.put(f"{qui.base}/nodes/{node_id}/recipient", json=corps, headers=qui.h)  # noqa: E731

    # Seule Ima, qui l'a déposé, choisit le destinataire (Max n'a que l'Écriture).
    assert pour(max_, {"type": "member", "id": str(profs["zoe"].id)}).status_code == 403
    assert pour(ima, {"type": "member", "id": "999999"}).status_code == 422
    reponse = pour(ima, {"type": "member", "id": str(profs["zoe"].id)})
    assert reponse.status_code == 200 and reponse.json()["for_label"] == "Zoé Vidal"

    assert max_.racine(dossier=bac).json()["items"] == []
    assert max_.get(f"/nodes/{node_id}/content").status_code == 404
    assert "Pour Zoé.docx" in _par_nom(admin.racine(dossier=bac))
    ligne = _par_nom(zoe.racine(dossier=bac))["Pour Zoé.docx"]
    assert ligne["for_me"] is True and ligne["picked"] is False

    # Zoé l'ouvre : Ima voit « récupéré ».
    assert zoe.get(f"/nodes/{node_id}/content").status_code == 200
    ligne = _par_nom(ima.racine(dossier=bac))["Pour Zoé.docx"]
    assert ligne["picked"] is True and ligne["for_label"] == "Zoé Vidal"

    # De nouveau pour tout le monde.
    assert pour(ima, {}).status_code == 200
    assert "Pour Zoé.docx" in _par_nom(max_.racine(dossier=bac))


def test_le_bac_de_financier(client, db_session, ecole):  # noqa: F811
    comptes = Comptes()
    tresorier = comptes.create(db_session, ecole_id=ecole["id"], role="admin", nom="Roux", prenom="Lou")
    comptes.ajouter_role(db_session, tresorier, roles.TRESORIER)
    tres, admin = Docs(client, ecole["id"], tresorier), Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(tres)["id"]
    financier = _par_nom(tres.racine(dossier=saison))["Financier"]["id"]
    bac = _par_nom(tres.racine(dossier=financier))["Échanges"]
    assert bac["system_kind"] == "exchange"
    assert tres.racine(dossier=financier).json()["items"][0]["id"] == bac["id"]
    assert tres.fichier("Relevé.pdf", bac["id"]).status_code == 201

    # Un admin qui n'est pas trésorier n'y entre pas.
    assert admin.racine(dossier=bac["id"]).status_code == 404
