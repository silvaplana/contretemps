"""Profil › Ma barre du bas (spec/core.md §10.4) : chacun range ses onglets."""

import pytest
from conftest import entetes_session
from comptes import Comptes
from ecoles import Ecoles


def test_ranger_ses_onglets_puis_remettre_l_ordre_de_l_ecole(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    assert client.get(f"/comptes/{admin.id}").json()["tab_order"] is None

    reponse = client.put(f"/comptes/{admin.id}/tab-order", json={"tab_order": ["messagerie", "docs", "admin"]})
    assert reponse.status_code == 200
    assert reponse.json()["tab_order"] == ["messagerie", "docs", "admin"]
    assert client.get(f"/comptes/{admin.id}").json()["tab_order"] == ["messagerie", "docs", "admin"]

    # « Remettre l'ordre de l'école ».
    assert client.put(f"/comptes/{admin.id}/tab-order", json={"tab_order": []}).json()["tab_order"] is None
    assert client.put("/comptes/999/tab-order", json={"tab_order": []}).status_code == 404


@pytest.mark.rbac_reel
def test_on_ne_range_pas_les_onglets_d_un_autre(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Ana")

    corps = {"tab_order": ["docs"]}
    assert client.put(f"/comptes/{eleve.id}/tab-order", json=corps, headers=entetes_session(admin)).status_code == 403
    assert client.put(f"/comptes/{eleve.id}/tab-order", json=corps, headers=entetes_session(eleve)).status_code == 200
