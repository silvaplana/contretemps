"""Tests de connexion et de bascule de profil (voir spec §2.2)."""

from comptes import Comptes
from ecoles import Ecoles


def _creer_ecole_et_comptes(db_session, code_recuperation="coocky"):
    ecoles = Ecoles()
    comptes = Comptes()
    ecole = ecoles.create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(
        db_session,
        ecole_id=ecole.id,
        role="admin",
        nom="Dho",
        prenom="Julia",
        email="j.dho@x.fr",
        code_recuperation=code_recuperation,
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


def test_recuperation_admin_bonne_reponse_connecte(client, db_session):
    """Voir "Code oublié ?" (§2.2/§2.3) : bonne réponse -> connecté direct,
    insensible à la casse/aux espaces."""
    ecole, admin, _ = _creer_ecole_et_comptes(db_session)
    verif = client.post(
        "/auth/recuperation/verifier",
        json={"ecole_id": ecole.id, "identifiant": "Julia Dho"},
    )
    assert verif.status_code == 200
    assert verif.json() == {
        "role": "admin", "admin_nom": None, "admin_prenom": None, "admin_email": None, "ecole_nom": None,
    }

    reponse = client.post(
        "/auth/recuperation/repondre",
        json={"ecole_id": ecole.id, "identifiant": "Julia Dho", "reponse": "  Coocky  "},
    )
    assert reponse.status_code == 200
    assert reponse.json()["id"] == admin.id


def test_recuperation_admin_mauvaise_reponse(client, db_session):
    ecole, admin, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/recuperation/repondre",
        json={"ecole_id": ecole.id, "identifiant": "Julia Dho", "reponse": "Rex"},
    )
    assert reponse.status_code == 401


def test_recuperation_eleve_renvoie_le_contact_admin(client, db_session):
    """Un prof/élève n'a pas de récupération en libre-service : juste le
    contact de l'admin à qui demander directement (§2.2/§2.3)."""
    ecole, admin, eleve = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/recuperation/verifier",
        json={"ecole_id": ecole.id, "identifiant": "Léon Perrin"},
    )
    assert reponse.status_code == 200
    assert reponse.json() == {
        "role": "eleve",
        "admin_nom": "Dho",
        "admin_prenom": "Julia",
        "admin_email": "j.dho@x.fr",
        "ecole_nom": "Contretemps",
    }


def test_recuperation_identifiant_introuvable(client, db_session):
    ecole, _, _ = _creer_ecole_et_comptes(db_session)
    reponse = client.post(
        "/auth/recuperation/verifier",
        json={"ecole_id": ecole.id, "identifiant": "Personne Inconnue"},
    )
    assert reponse.status_code == 404
