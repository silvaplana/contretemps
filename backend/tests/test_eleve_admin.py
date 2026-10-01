"""Élève promu administrateur (spec §2.4). Depuis le mot de passe personnel
(§2.2, 2026-10-01), plus de cas particulier : connecté, il a tous ses
rôles. Vérifications de droits réelles (`rbac_reel`)."""

import pytest
from comptes import Comptes, roles
from conftest import MOT_DE_PASSE, donner_mot_de_passe, entetes_session
from ecoles import Ecoles
from eleves import Eleves

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    eleve, _ = Eleves(comptes=comptes).create(
        db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon", email="leon@x.fr"
    )
    donner_mot_de_passe(db_session, "leon@x.fr")
    return {"ecole": ecole, "owner": owner, "eleve": eleve}


def _promouvoir(client, ecole, owner=False):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"compte_id": ecole["eleve"].id, "owner": owner},
        headers=entetes_session(ecole["owner"]),
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_un_eleve_peut_etre_promu_administrateur(client, db_session, ecole):
    corps = _promouvoir(client, ecole)
    assert corps["est_eleve"] is True and corps["est_prof"] is False
    db_session.expire_all()
    assert roles.noms_roles(Comptes().get(db_session, ecole["eleve"].id)) == ["admin", "eleve"]


def test_connecte_il_a_tous_ses_roles_et_ses_droits_d_admin(client, db_session, ecole):
    _promouvoir(client, ecole)
    session = client.post("/auth/login", json={"identifiant": "Léon Perrin", "mot_de_passe": MOT_DE_PASSE}).json()
    assert session["compte"]["roles"] == ["admin", "eleve"]
    entetes = {"Authorization": f"Bearer {session['jeton']}", "X-Compte-Id": str(ecole["eleve"].id)}
    assert client.get(f"/ecoles/{ecole['ecole'].id}", headers=entetes).status_code == 200
    # Admin d'école, pas propriétaire de l'application.
    assert client.post("/ecoles", json={"nom": "X", "code_postal": "1"}, headers=entetes).status_code == 403


def test_avant_d_etre_promu_il_n_a_aucun_droit_d_admin(client, db_session, ecole):
    assert client.get(f"/ecoles/{ecole['ecole'].id}", headers=entetes_session(ecole["eleve"])).status_code == 403


def test_retirer_des_admins_le_laisse_eleve(client, db_session, ecole):
    _promouvoir(client, ecole)
    reponse = client.delete(f"/administrateurs/{ecole['eleve'].id}", headers=entetes_session(ecole["owner"]))
    assert reponse.status_code == 204
    db_session.expire_all()
    assert roles.noms_roles(Comptes().get(db_session, ecole["eleve"].id)) == ["eleve"]


def test_supprimer_depuis_admin_eleves_le_dernier_principal_refuse(client, db_session, ecole):
    _promouvoir(client, ecole, owner=True)
    # Julia n'est plus principale : l'élève devient le seul.
    Comptes().retirer_role(db_session, ecole["owner"], roles.OWNER, autoriser_sans_owner=True)
    db_session.refresh(ecole["eleve"])
    reponse = client.delete(f"/eleves/{ecole['eleve'].id}", headers=entetes_session(ecole["eleve"]))
    assert reponse.status_code == 409


def test_dans_la_famille_il_figure_avec_tous_ses_roles(client, db_session, ecole):
    _promouvoir(client, ecole)
    ecole["eleve"].famille_id = ecole["owner"].famille_id
    db_session.commit()
    db_session.refresh(ecole["eleve"])
    membres = client.get(f"/comptes/{ecole['eleve'].id}/famille", headers=entetes_session(ecole["eleve"])).json()
    leon = next(m for m in membres if m["id"] == ecole["eleve"].id)
    assert leon["roles"] == ["admin", "eleve"] and leon["role"] == "admin"
