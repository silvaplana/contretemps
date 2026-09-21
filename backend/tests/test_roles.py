"""Tests des rôles cumulables (voir spec/SPEC.md §2.1, §2.2 et §6.3bis)."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from comptes import Comptes, RoleCompte, roles
from ecoles import Ecoles


def _ecole(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330")


def _promouvoir_admin(db_session, compte):
    """Pas encore de route pour ça (étape "gestion multi-admin", §2.4) :
    on ajoute la ligne à la main pour tester un professeur-admin."""
    compte.roles.append(RoleCompte(role=roles.ADMIN))
    db_session.commit()
    db_session.refresh(compte)
    return compte


def test_le_premier_admin_d_une_ecole_devient_owner(db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    premier = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    second = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana")

    assert roles.noms_roles(premier) == ["admin", "owner"]
    assert roles.noms_roles(second) == ["admin"]
    assert roles.is_owner(premier) and not roles.is_owner(second)


def test_owner_est_propre_a_chaque_ecole(db_session):
    comptes = Comptes()
    a = Ecoles().create(db_session, nom="A", code_postal="83000")
    b = Ecoles().create(db_session, nom="B", code_postal="83000")
    admin_a = comptes.create(db_session, ecole_id=a.id, role="admin", nom="X", prenom="Y")
    admin_b = comptes.create(db_session, ecole_id=b.id, role="admin", nom="Z", prenom="W")
    assert roles.is_owner(admin_a) and roles.is_owner(admin_b)


def test_owner_ne_se_donne_pas_a_la_creation(db_session):
    ecole = _ecole(db_session)
    with pytest.raises(ValueError):
        Comptes().create(db_session, ecole_id=ecole.id, role="owner", nom="X", prenom="Y")


def test_professeur_admin_cumule_les_deux_roles(db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie")
    _promouvoir_admin(db_session, prof)

    assert roles.is_prof(prof) and roles.is_admin(prof) and not roles.is_eleve(prof)
    assert roles.role_principal(roles.noms_roles(prof)) == "admin"
    # Il sort dans les DEUX listes (Admin > Profs et liste des admins).
    assert prof.id in [c.id for c in comptes.list_par_role(db_session, ecole.id, "professeur")]
    assert prof.id in [c.id for c in comptes.list_par_role(db_session, ecole.id, "admin")]


def test_role_principal_ramene_owner_a_admin():
    assert roles.role_principal(["owner", "admin"]) == "admin"
    assert roles.role_principal(["professeur"]) == "professeur"


def test_api_expose_role_principal_et_liste_des_roles(client, db_session):
    ecole = _ecole(db_session)
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    corps = client.get(f"/comptes/{admin.id}").json()
    assert corps["role"] == "admin"
    assert corps["roles"] == ["admin", "owner"]


def test_supprimer_un_compte_supprime_ses_roles(db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    comptes.delete(db_session, eleve.id)
    assert db_session.query(RoleCompte).filter(RoleCompte.compte_id == eleve.id).count() == 0


# --- Connexion (§2.2) ---


def _ecole_avec_prof_admin(db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie",
        code_recuperation="rex",
    )
    return ecole, _promouvoir_admin(db_session, prof)


@pytest.mark.parametrize("code", ["prof", "admin"])
def test_professeur_admin_se_connecte_avec_le_code_de_l_un_de_ses_roles(client, db_session, code):
    ecole, prof = _ecole_avec_prof_admin(db_session)
    saisi = ecole.code_acces_prof if code == "prof" else ecole.code_acces_admin
    reponse = client.post(
        "/auth/login", json={"ecole_id": ecole.id, "identifiant": "Marie Pesenti", "code": saisi}
    )
    assert reponse.status_code == 200
    # Dans les deux cas il obtient TOUS ses rôles, pas seulement celui du code.
    assert reponse.json()["roles"] == ["admin", "professeur"]


def test_code_d_un_role_que_le_compte_n_a_pas_refuse(client, db_session):
    ecole, _ = _ecole_avec_prof_admin(db_session)
    reponse = client.post(
        "/auth/login",
        json={"ecole_id": ecole.id, "identifiant": "Marie Pesenti", "code": ecole.code_acces_eleve},
    )
    assert reponse.status_code == 401


def test_bascule_vers_un_professeur_admin_est_une_montee_depuis_un_prof(client, db_session):
    """Rang = rôle le plus élevé (§2.2) : un professeur-admin compte comme
    admin, donc y basculer depuis un simple prof redemande un code."""
    ecole, prof_admin = _ecole_avec_prof_admin(db_session)
    simple_prof = Comptes().create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima"
    )
    reponse = client.post(
        "/auth/bascule/verifier",
        json={"depuis_compte_id": simple_prof.id, "vers_compte_id": prof_admin.id},
    )
    assert reponse.json() == {"code_requis": True}


def test_code_oublie_ouvert_au_professeur_admin(client, db_session):
    ecole, prof = _ecole_avec_prof_admin(db_session)
    etape1 = client.post(
        "/auth/recuperation/verifier", json={"ecole_id": ecole.id, "identifiant": "Marie Pesenti"}
    )
    assert etape1.json()["role"] == "admin"
    etape2 = client.post(
        "/auth/recuperation/repondre",
        json={"ecole_id": ecole.id, "identifiant": "Marie Pesenti", "reponse": "rex"},
    )
    assert etape2.status_code == 200
    assert etape2.json()["id"] == prof.id


def test_code_oublie_affiche_le_contact_de_l_owner(client, db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    reponse = client.post(
        "/auth/recuperation/verifier", json={"ecole_id": ecole.id, "identifiant": "Léon Perrin"}
    )
    assert reponse.json()["role"] == "eleve"
    assert reponse.json()["admin_prenom"] == "Julia"


# --- Migration Alembic (données réelles d'avant les rôles cumulables) ---

BACKEND = Path(__file__).resolve().parents[1]


def test_migration_convertit_role_unique_en_roles_cumulables(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))

    command.upgrade(config, "11a534a5cb6f")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        for ecole_id in (1, 2):
            c.execute(sa.text(
                "INSERT INTO ecoles (id, nom, code_postal, code_acces_admin, code_acces_prof,"
                " code_acces_eleve, sauvegarde_active, sauvegarde_periodicite, created_at)"
                f" VALUES ({ecole_id}, 'E{ecole_id}', '83000', 'A', 'P', 'E', 0, 'semaine',"
                " CURRENT_TIMESTAMP)"
            ))
            c.execute(sa.text("INSERT INTO familles (id, ecole_id, created_at)"
                f" VALUES ({ecole_id}, {ecole_id}, CURRENT_TIMESTAMP)"))
        # École 1 : deux admins (le plus ancien, id 3, doit devenir owner),
        # un prof, un élève. École 2 : un seul admin.
        for id_, ecole_id, role in [
            (5, 1, "admin"), (3, 1, "admin"), (4, 1, "professeur"), (6, 1, "eleve"), (7, 2, "admin"),
        ]:
            c.execute(sa.text(
                "INSERT INTO comptes (id, ecole_id, famille_id, role, nom, prenom, created_at)"
                f" VALUES ({id_}, {ecole_id}, {ecole_id}, '{role}', 'N{id_}', 'P{id_}',"
                " CURRENT_TIMESTAMP)"
            ))

    command.upgrade(config, "head")

    with moteur.connect() as c:
        lignes = set(c.execute(sa.text("SELECT compte_id, role FROM roles_compte")).all())
        colonnes = [col["name"] for col in sa.inspect(c).get_columns("comptes")]
    assert lignes == {
        (3, "admin"), (3, "owner"), (5, "admin"), (4, "professeur"), (6, "eleve"),
        (7, "admin"), (7, "owner"),
    }
    assert "role" not in colonnes

    # Et le retour arrière retrouve l'ancien modèle, rôle le plus élevé.
    command.downgrade(config, "11a534a5cb6f")
    with moteur.connect() as c:
        apres = dict(c.execute(sa.text("SELECT id, role FROM comptes")).all())
    assert apres == {3: "admin", 5: "admin", 4: "professeur", 6: "eleve", 7: "admin"}
    moteur.dispose()
