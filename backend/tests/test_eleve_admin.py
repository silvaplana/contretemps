"""Élève promu administrateur (spec §2.4, décision utilisateur du
2026-09-21) : ses droits d'admin ne sont actifs qu'avec le code ADMIN de
l'école (jeton "admin") — avec le code élève, connu de toutes les familles,
il n'est qu'un élève. Vérifications de droits réelles (`rbac_reel`)."""

import pytest
from comptes import Comptes, rbac, roles
from ecoles import Ecoles
from eleves import Eleves
from securite import jetons

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    eleve, _ = Eleves(comptes=comptes).create(
        db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon", email="leon@x.fr"
    )
    return {"ecole": ecole, "owner": owner, "eleve": eleve}


def _promouvoir(client, ecole, owner=False):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"compte_id": ecole["eleve"].id, "code_recuperation": "rex", "owner": owner},
        headers={rbac.ENTETE_COMPTE: str(ecole["owner"].id)},
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _login(client, ecole, code):
    return client.post(
        "/auth/login", json={"ecole_id": ecole["ecole"].id, "identifiant": "Léon Perrin", "code": code}
    )


def test_un_eleve_peut_etre_promu_administrateur(client, db_session, ecole):
    corps = _promouvoir(client, ecole)
    assert corps["est_eleve"] is True and corps["est_prof"] is False
    db_session.expire_all()
    assert roles.noms_roles(Comptes().get(db_session, ecole["eleve"].id)) == ["admin", "eleve"]


def test_avec_le_code_eleve_il_n_est_qu_un_eleve(client, ecole):
    _promouvoir(client, ecole)
    corps = _login(client, ecole, ecole["ecole"].code_acces_eleve).json()
    assert corps["roles"] == ["eleve"]
    assert corps["role"] == "eleve"
    assert corps["jeton"] is None
    # Et le serveur le traite en élève : pas de route Admin.
    reponse = client.get(
        f"/ecoles/{ecole['ecole'].id}", headers={rbac.ENTETE_COMPTE: str(ecole["eleve"].id)}
    )
    assert reponse.status_code == 403


def test_avec_le_code_admin_ses_droits_sont_actifs(client, ecole):
    _promouvoir(client, ecole)
    corps = _login(client, ecole, ecole["ecole"].code_acces_admin).json()
    assert corps["roles"] == ["admin", "eleve"]
    assert jetons.lire(corps["jeton"]).portee == jetons.ADMIN
    reponse = client.get(
        f"/ecoles/{ecole['ecole'].id}", headers={"Authorization": f"Bearer {corps['jeton']}"}
    )
    assert reponse.status_code == 200


def test_reprise_de_session_selon_le_jeton(client, ecole):
    _promouvoir(client, ecole)
    url = f"/comptes/{ecole['eleve'].id}"
    assert client.get(url).json()["roles"] == ["eleve"]
    jeton = _login(client, ecole, ecole["ecole"].code_acces_admin).json()["jeton"]
    assert client.get(url, headers={"Authorization": f"Bearer {jeton}"}).json()["roles"] == ["admin", "eleve"]


def test_le_jeton_admin_d_un_autre_compte_ne_donne_rien(client, ecole):
    _promouvoir(client, ecole)
    # Jeton "admin" émis pour un compte qui n'est PAS un élève-admin.
    faux = jetons.emettre(ecole["owner"].id, portee=jetons.ADMIN)
    reponse = client.get(f"/ecoles/{ecole['ecole'].id}", headers={"Authorization": f"Bearer {faux}"})
    assert reponse.status_code == 401


def test_le_jeton_admin_n_ouvre_pas_les_droits_superuser(client, ecole):
    _promouvoir(client, ecole)
    jeton = _login(client, ecole, ecole["ecole"].code_acces_admin).json()["jeton"]
    corps = {
        "nom": "X", "code_postal": "1", "code_acces_admin": "a", "code_acces_prof": "b", "code_acces_eleve": "c",
    }
    reponse = client.post("/ecoles", json=corps, headers={"Authorization": f"Bearer {jeton}"})
    assert reponse.status_code == 403


def test_code_oublie_active_ses_droits(client, ecole):
    _promouvoir(client, ecole)
    corps = client.post(
        "/auth/recuperation/repondre",
        json={"ecole_id": ecole["ecole"].id, "identifiant": "Léon Perrin", "reponse": "rex"},
    ).json()
    assert corps["roles"] == ["admin", "eleve"]
    assert jetons.lire(corps["jeton"]).portee == jetons.ADMIN


def test_bascule_avec_le_code_admin_active_ses_droits(client, ecole):
    _promouvoir(client, ecole)
    avec_admin = client.post(
        "/auth/bascule/confirmer",
        json={"vers_compte_id": ecole["eleve"].id, "code": ecole["ecole"].code_acces_admin},
    ).json()
    assert avec_admin["roles"] == ["admin", "eleve"] and avec_admin["jeton"]
    avec_eleve = client.post(
        "/auth/bascule/confirmer",
        json={"vers_compte_id": ecole["eleve"].id, "code": ecole["ecole"].code_acces_eleve},
    ).json()
    assert avec_eleve["roles"] == ["eleve"] and avec_eleve["jeton"] is None


def test_retirer_des_admins_le_laisse_eleve(client, db_session, ecole):
    _promouvoir(client, ecole)
    reponse = client.delete(
        f"/administrateurs/{ecole['eleve'].id}", headers={rbac.ENTETE_COMPTE: str(ecole["owner"].id)}
    )
    assert reponse.status_code == 204
    db_session.expire_all()
    assert roles.noms_roles(Comptes().get(db_session, ecole["eleve"].id)) == ["eleve"]


def test_supprimer_depuis_admin_eleves_le_dernier_principal_refuse(client, db_session, ecole):
    _promouvoir(client, ecole, owner=True)
    # Julia n'est plus principale : l'élève devient le seul.
    Comptes().retirer_role(db_session, ecole["owner"], roles.OWNER, autoriser_sans_owner=True)
    jeton = _login(client, ecole, ecole["ecole"].code_acces_admin).json()["jeton"]
    reponse = client.delete(
        f"/eleves/{ecole['eleve'].id}", headers={"Authorization": f"Bearer {jeton}"}
    )
    assert reponse.status_code == 409
