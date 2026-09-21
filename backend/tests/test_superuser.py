"""Superuser, propriétaire de l'application (spec §2.5). Vérifications de
droits réelles actives (`rbac_reel`, voir conftest.py)."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from comptes import Comptes, RegleRoles, rbac, roles
from ecoles import Ecoles
from securite import jetons, limiteur, mots_de_passe

pytestmark = pytest.mark.rbac_reel

MOT_DE_PASSE = "un-mot-de-passe-de-test"
EMAIL = "proprio@exemple.fr"


@pytest.fixture()
def monde(db_session):
    """Deux écoles, chacune avec son admin (Owner) ; un Superuser dont
    l'email sert AUSSI à un compte admin de l'école A (cohabitation)."""
    comptes = Comptes()
    a = Ecoles().create(db_session, nom="A", code_postal="83000")
    b = Ecoles().create(db_session, nom="B", code_postal="83000")
    admin_a = comptes.create(db_session, ecole_id=a.id, role="admin", nom="Dho", prenom="Julia", email=EMAIL)
    admin_b = comptes.create(db_session, ecole_id=b.id, role="admin", nom="Roux", prenom="Ana")
    su = comptes.enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email=EMAIL,
        mot_de_passe_hache=mots_de_passe.hacher(MOT_DE_PASSE),
    )
    return {"a": a, "b": b, "admin_a": admin_a, "admin_b": admin_b, "su": su}


def _login(client, ecole, identifiant, code):
    return client.post("/auth/login", json={"ecole_id": ecole.id, "identifiant": identifiant, "code": code})


def _jeton(client, monde):
    return _login(client, monde["a"], EMAIL, MOT_DE_PASSE).json()["jeton"]


def _en_superuser(jeton):
    return {"Authorization": f"Bearer {jeton}"}


# --- Briques : mot de passe haché, jeton signé ---


def test_mot_de_passe_jamais_en_clair():
    stocke = mots_de_passe.hacher(MOT_DE_PASSE)
    assert MOT_DE_PASSE not in stocke
    assert mots_de_passe.verifier(MOT_DE_PASSE, stocke)
    assert not mots_de_passe.verifier("autre", stocke)
    # Deux hachages du même mot de passe diffèrent (sel aléatoire).
    assert mots_de_passe.hacher(MOT_DE_PASSE) != stocke


def test_jeton_falsifie_ou_expire_refuse():
    jeton = jetons.emettre(42, maintenant=1_000)
    assert jetons.verifier(jeton, maintenant=1_001) == 42
    assert jetons.verifier(jeton, maintenant=1_000 + jetons.DUREE_SECONDES) is None  # 12 h passées
    charge, signature = jeton.split(".")
    faux = jetons.emettre(1, maintenant=1_000).split(".")[0] + "." + signature  # charge d'un autre
    assert jetons.verifier(faux, maintenant=1_001) is None
    assert jetons.verifier("n'importe quoi", maintenant=1_001) is None


# --- Connexion (§2.5 : même formulaire, mot de passe dans "Code") ---


def test_connexion_superuser_par_email_ou_nom(client, monde):
    for identifiant in [EMAIL, "Sébastien Richard", "sebastien richard"]:
        reponse = _login(client, monde["a"], identifiant, MOT_DE_PASSE)
        assert reponse.status_code == 200, identifiant
        corps = reponse.json()
        assert corps["roles"] == ["superuser"]
        assert corps["ecole_id"] is None
        assert jetons.verifier(corps["jeton"]) == monde["su"].id


def test_cohabitation_avec_un_compte_d_ecole_de_meme_email(client, monde):
    """Code de l'école -> le compte admin de l'école (sans jeton) ; mot de
    passe personnel -> le Superuser."""
    reponse = _login(client, monde["a"], EMAIL, monde["a"].code_acces_admin)
    assert reponse.status_code == 200
    assert reponse.json()["id"] == monde["admin_a"].id
    assert reponse.json()["jeton"] is None


def test_mauvais_mot_de_passe_401(client, monde):
    assert _login(client, monde["a"], EMAIL, "faux").status_code == 401


def test_blocage_apres_5_echecs(client, monde):
    for _ in range(limiteur.ESSAIS_MAX):
        assert _login(client, monde["a"], EMAIL, "faux").status_code == 401
    # Bloqué : même le bon mot de passe est refusé, avec le même message.
    reponse = _login(client, monde["a"], EMAIL, MOT_DE_PASSE)
    assert reponse.status_code == 401
    assert reponse.json()["detail"] == "Identifiant ou code incorrect"
    # Mais la connexion d'école avec le même email marche toujours.
    assert _login(client, monde["a"], EMAIL, monde["a"].code_acces_admin).status_code == 200


def test_les_connexions_d_ecole_ne_comptent_pas_comme_echecs(client, monde):
    for _ in range(limiteur.ESSAIS_MAX + 2):
        assert _login(client, monde["a"], EMAIL, monde["a"].code_acces_admin).status_code == 200
    assert _login(client, monde["a"], EMAIL, MOT_DE_PASSE).status_code == 200


# --- Droits ---


def test_tous_les_droits_dans_toutes_les_ecoles(client, db_session, monde):
    entetes = _en_superuser(_jeton(client, monde))
    for ecole in [monde["a"], monde["b"]]:
        assert client.get(f"/ecoles/{ecole.id}", headers=entetes).status_code == 200
        assert client.get(f"/ecoles/{ecole.id}/administrateurs", headers=entetes).status_code == 200
        reponse = client.post(f"/cours?ecole_id={ecole.id}", json={"nom": "Jazz"}, headers=entetes)
        assert reponse.status_code == 201


def test_numero_de_compte_seul_ne_donne_aucun_droit(client, monde):
    """Le cœur de la sécurité : connaître l'id du Superuser ne suffit pas."""
    entetes = {rbac.ENTETE_COMPTE: str(monde["su"].id)}
    assert client.get(f"/ecoles/{monde['a'].id}", headers=entetes).status_code == 401
    faux_jeton = {"Authorization": "Bearer " + jetons.emettre(monde["su"].id)[:-3] + "abc"}
    assert client.get(f"/ecoles/{monde['a'].id}", headers=faux_jeton).status_code == 401


def test_jeton_d_un_compte_non_superuser_refuse(client, monde):
    """Un jeton n'ouvre des droits que s'il désigne un Superuser."""
    entetes = _en_superuser(jetons.emettre(monde["admin_b"].id))
    assert client.get(f"/ecoles/{monde['a'].id}", headers=entetes).status_code == 401


def test_creer_une_ecole_reserve_au_superuser(client, monde):
    corps = {
        "nom": "Nouvelle", "code_postal": "75000",
        "code_acces_admin": "A", "code_acces_prof": "P", "code_acces_eleve": "E",
    }
    admin = {rbac.ENTETE_COMPTE: str(monde["admin_a"].id)}
    assert client.post("/ecoles", json=corps, headers=admin).status_code == 403
    assert client.post("/ecoles", json=corps).status_code == 401
    assert client.post("/ecoles", json=corps, headers=_en_superuser(_jeton(client, monde))).status_code == 201


def test_relancer_toutes_les_ecoles_reserve_au_superuser(client, monde):
    admin = {rbac.ENTETE_COMPTE: str(monde["admin_a"].id)}
    assert client.post("/messagerie/relancer", json={}, headers=admin).status_code == 403
    reponse = client.post("/messagerie/relancer", json={}, headers=_en_superuser(_jeton(client, monde)))
    assert reponse.status_code == 200


def test_le_superuser_peut_retirer_le_dernier_owner(client, db_session, monde):
    """Dépannage d'une école (§2.5), interdit à tout le monde sauf lui."""
    admin_b = monde["admin_b"]
    assert roles.is_owner(admin_b)
    reponse = client.put(
        f"/administrateurs/{admin_b.id}", json={"owner": False}, headers=_en_superuser(_jeton(client, monde))
    )
    assert reponse.status_code == 200
    assert reponse.json()["est_owner"] is False


# --- Invisible pour les écoles ---


def test_invisible_dans_les_listes_des_ecoles(client, monde):
    entetes = _en_superuser(_jeton(client, monde))
    for ecole in [monde["a"], monde["b"]]:
        admins = client.get(f"/comptes?ecole_id={ecole.id}&role=admin").json()
        assert monde["su"].id not in [c["id"] for c in admins]
        tableau = client.get(f"/ecoles/{ecole.id}/administrateurs", headers=entetes).json()
        assert monde["su"].id not in [a["id"] for a in tableau]


def test_son_compte_n_est_lisible_qu_avec_son_jeton(client, monde):
    url = f"/comptes/{monde['su'].id}"
    assert client.get(url).status_code == 404
    assert client.get(url, headers={rbac.ENTETE_COMPTE: str(monde["admin_a"].id)}).status_code == 404
    assert client.get(url, headers=_en_superuser(_jeton(client, monde))).status_code == 200


# --- Création : seulement par la commande serveur ---


def test_le_role_superuser_ne_s_attribue_pas_depuis_l_appli(db_session, monde):
    with pytest.raises(ValueError):
        Comptes().create(db_session, ecole_id=monde["a"].id, role="superuser", nom="X", prenom="Y")
    with pytest.raises(RegleRoles):
        Comptes().ajouter_role(db_session, monde["admin_a"], roles.SUPERUSER)


def test_enregistrer_superuser_met_a_jour_le_meme_email(db_session, monde):
    comptes = Comptes()
    compte = comptes.enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email=EMAIL,
        mot_de_passe_hache=mots_de_passe.hacher("nouveau-mot-de-passe"),
    )
    assert compte.id == monde["su"].id
    assert mots_de_passe.verifier("nouveau-mot-de-passe", compte.hashed_password_ou_code)
    assert not mots_de_passe.verifier(MOT_DE_PASSE, compte.hashed_password_ou_code)


# --- Migration ---

BACKEND = Path(__file__).resolve().parents[1]


def test_migration_autorise_un_compte_sans_ecole(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'base.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(config, "head")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        c.execute(sa.text(
            "INSERT INTO comptes (id, ecole_id, famille_id, nom, prenom, created_at)"
            " VALUES (1, NULL, NULL, 'Richard', 'Sébastien', CURRENT_TIMESTAMP)"
        ))
        c.execute(sa.text("INSERT INTO roles_compte (compte_id, role) VALUES (1, 'superuser')"))
    command.downgrade(config, "e08ed3a9ccbe")
    with moteur.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM comptes")).scalar() == 0
    moteur.dispose()
