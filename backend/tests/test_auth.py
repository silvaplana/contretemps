"""Tests de connexion et de bascule de profil (voir spec §2.2)."""

from comptes import Comptes
from ecoles import Ecoles


def _creer_ecole_et_comptes(db_session):
    ecoles = Ecoles()
    comptes = Comptes()
    ecole = ecoles.create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(
        db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="j.dho@x.fr"
    )
    eleve = comptes.create(
        db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon"
    )
    return ecole, admin, eleve


def test_login_par_nom_prenom_avec_bon_code(client, db_session):
    ecole, admin, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/login",
        json={"ecole_id": ecole.id, "identifiant": "Julia Dho", "code": ecole.code_acces_admin},
    )
    assert reponse.status_code == 200
    assert reponse.json()["id"] == admin.id


def test_login_par_email(client, db_session):
    ecole, admin, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/login",
        json={"ecole_id": ecole.id, "identifiant": "j.dho@x.fr", "code": ecole.code_acces_admin},
    )
    assert reponse.status_code == 200
    assert reponse.json()["id"] == admin.id


def test_login_mauvais_code_refuse(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/login",
        json={"ecole_id": ecole.id, "identifiant": "Julia Dho", "code": "FAUX"},
    )
    assert reponse.status_code == 401


def test_login_code_admin_pour_un_compte_eleve_refuse(client, db_session):
    """Le code doit correspondre au RÔLE RÉEL du compte trouvé, pas juste
    être un des 3 codes valides de l'école (voir §2.2)."""
    ecole, _, eleve = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/login",
        json={
            "ecole_id": ecole.id,
            "identifiant": "Léon Perrin",
            "code": ecole.code_acces_admin,
        },
    )
    assert reponse.status_code == 401


def test_bascule_vers_role_superieur_demande_le_code(client, db_session):
    ecole, admin, eleve = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/bascule/verifier",
        json={"depuis_compte_id": eleve.id, "vers_compte_id": admin.id},
    )
    assert reponse.json() == {"code_requis": True}


def test_bascule_vers_role_inferieur_libre(client, db_session):
    ecole, admin, eleve = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/bascule/verifier",
        json={"depuis_compte_id": admin.id, "vers_compte_id": eleve.id},
    )
    assert reponse.json() == {"code_requis": False}


def test_confirmer_bascule_bon_code(client, db_session):
    ecole, admin, eleve = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/bascule/confirmer",
        json={"vers_compte_id": admin.id, "code": ecole.code_acces_admin},
    )
    assert reponse.status_code == 200
    assert reponse.json()["id"] == admin.id


def test_confirmer_bascule_mauvais_code(client, db_session):
    ecole, admin, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/bascule/confirmer",
        json={"vers_compte_id": admin.id, "code": "FAUX"},
    )
    assert reponse.status_code == 401
