"""Superuser, propriétaire de l'application (spec §2.5). Vérifications de
droits réelles actives (`rbac_reel`, voir conftest.py)."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from acces import Acces
from alembic import command
from alembic.config import Config
from comptes import Comptes, RegleRoles, rbac, roles
from conftest import donner_mot_de_passe, entetes_session
from ecoles import Ecoles
from securite import jetons, limiteur, mots_de_passe

pytestmark = pytest.mark.rbac_reel

MOT_DE_PASSE = "un-mot-de-passe-de-test"
EMAIL = "proprio@exemple.fr"


@pytest.fixture()
def monde(db_session):
    """Deux écoles, chacune avec son admin (Owner) ; un Superuser dont
    l'email sert AUSSI à un compte admin de l'école A : même email, donc
    même mot de passe (§2.2), et « Choisissez votre école » à la connexion."""
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


def _login(client, identifiant, mot_de_passe=MOT_DE_PASSE, **plus):
    return client.post("/auth/login", json={"identifiant": identifiant, "mot_de_passe": mot_de_passe, **plus})


def _en_superuser(client, monde):
    """En-têtes d'une session Superuser ouverte par son nom (seule fiche à
    ce nom : pas de choix d'école)."""
    jeton = _login(client, "Sébastien Richard").json()["jeton"]
    return {"Authorization": f"Bearer {jeton}", rbac.ENTETE_COMPTE: str(monde["su"].id)}


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
    assert jetons.lire(jeton, maintenant=1_001).utilisateur_id == 42
    trente_jours = jetons.DUREES_SECONDES[jetons.UTILISATEUR]
    assert jetons.lire(jeton, maintenant=1_000 + trente_jours - 1) is not None
    assert jetons.lire(jeton, maintenant=1_000 + trente_jours) is None
    # Superuser : 12 heures seulement.
    su = jetons.emettre(42, portee=jetons.SUPERUSER, maintenant=1_000)
    assert jetons.lire(su, maintenant=1_000 + 12 * 3600) is None
    charge, signature = jeton.split(".")
    faux = jetons.emettre(1, maintenant=1_000).split(".")[0] + "." + signature  # charge d'un autre
    assert jetons.lire(faux, maintenant=1_001) is None
    assert jetons.lire("n'importe quoi", maintenant=1_001) is None


# --- Connexion (§2.5 : même écran que tout le monde) ---


def test_connexion_superuser_par_son_nom(client, monde):
    for identifiant in ["Sébastien Richard", "sebastien richard"]:
        reponse = _login(client, identifiant)
        assert reponse.status_code == 200, identifiant
        corps = reponse.json()
        assert corps["compte"]["roles"] == ["superuser"]
        assert corps["compte"]["ecole_id"] is None
        jeton = jetons.lire(corps["jeton"])
        assert jeton.portee == jetons.SUPERUSER


def test_meme_email_qu_un_compte_d_ecole_on_choisit(client, monde):
    """Un seul mot de passe par email : la connexion par email propose
    l'accès Superuser (sans école) et le compte admin de l'école A."""
    choix = _login(client, EMAIL).json()["choix"]
    assert {(c["compte_id"], c["ecole_nom"]) for c in choix} == {
        (monde["su"].id, None), (monde["admin_a"].id, "A"),
    }
    en_admin = _login(client, EMAIL, compte_id=monde["admin_a"].id).json()
    assert en_admin["compte"]["roles"] == ["admin", "owner"]
    assert jetons.lire(en_admin["jeton"]).portee == jetons.UTILISATEUR
    en_su = _login(client, EMAIL, compte_id=monde["su"].id).json()
    assert jetons.lire(en_su["jeton"]).portee == jetons.SUPERUSER


def test_mauvais_mot_de_passe_401(client, monde):
    assert _login(client, EMAIL, "faux").status_code == 401


def test_blocage_apres_5_echecs(client, monde):
    for _ in range(limiteur.ESSAIS_MAX):
        assert _login(client, EMAIL, "faux").status_code == 401
    # Bloqué : même le bon mot de passe est refusé, avec le même message.
    reponse = _login(client, EMAIL)
    assert reponse.status_code == 401
    assert reponse.json()["detail"] == "Identifiant ou mot de passe incorrect"


# --- Droits ---


def test_tous_les_droits_dans_toutes_les_ecoles(client, db_session, monde):
    entetes = _en_superuser(client, monde)
    for ecole in [monde["a"], monde["b"]]:
        assert client.get(f"/ecoles/{ecole.id}", headers=entetes).status_code == 200
        assert client.get(f"/ecoles/{ecole.id}/administrateurs", headers=entetes).status_code == 200
        reponse = client.post(f"/cours?ecole_id={ecole.id}", json={"nom": "Jazz"}, headers=entetes)
        assert reponse.status_code == 201


def test_numero_de_compte_seul_ne_donne_aucun_droit(client, monde):
    """Le cœur de la sécurité : connaître l'id du Superuser ne suffit pas."""
    entetes = {rbac.ENTETE_COMPTE: str(monde["su"].id)}
    assert client.get(f"/ecoles/{monde['a'].id}", headers=entetes).status_code == 401
    bon = _en_superuser(client, monde)
    faux = {**bon, "Authorization": bon["Authorization"][:-3] + "abc"}
    assert client.get(f"/ecoles/{monde['a'].id}", headers=faux).status_code == 401


def test_une_session_ordinaire_ne_donne_pas_les_droits_superuser(client, db_session, monde):
    """Même email, mais session ouverte sur le compte d'école (30 jours) :
    le profil Superuser exige sa propre session (12 heures)."""
    en_admin = _login(client, EMAIL, compte_id=monde["admin_a"].id).json()["jeton"]
    entetes = {"Authorization": f"Bearer {en_admin}", rbac.ENTETE_COMPTE: str(monde["su"].id)}
    assert client.get(f"/ecoles/{monde['b'].id}", headers=entetes).status_code == 401
    # Et un jeton fabriqué avec le rang maximum ne suffit pas non plus.
    utilisateur = Acces().par_email(db_session, EMAIL)
    force = jetons.emettre(utilisateur.id, rang=99, empreinte=Acces().empreinte(utilisateur))
    entetes["Authorization"] = f"Bearer {force}"
    assert client.get(f"/ecoles/{monde['b'].id}", headers=entetes).status_code == 401
    # L'admin de l'école B n'a aucun droit dans l'école A.
    assert client.get(f"/ecoles/{monde['a'].id}", headers=entetes_session(monde["admin_b"])).status_code == 403


def test_creer_une_ecole_reserve_au_superuser(client, monde):
    corps = {"nom": "Nouvelle", "code_postal": "75000"}
    assert client.post("/ecoles", json=corps, headers=entetes_session(monde["admin_b"])).status_code == 403
    assert client.post("/ecoles", json=corps).status_code == 401
    assert client.post("/ecoles", json=corps, headers=_en_superuser(client, monde)).status_code == 201


def test_relancer_toutes_les_ecoles_reserve_au_superuser(client, monde):
    assert client.post("/messagerie/relancer", json={}, headers=entetes_session(monde["admin_b"])).status_code == 403
    reponse = client.post("/messagerie/relancer", json={}, headers=_en_superuser(client, monde))
    assert reponse.status_code == 200


def test_le_superuser_peut_retirer_le_dernier_owner(client, db_session, monde):
    """Dépannage d'une école (§2.5), interdit à tout le monde sauf lui."""
    admin_b = monde["admin_b"]
    assert roles.is_owner(admin_b)
    reponse = client.put(
        f"/administrateurs/{admin_b.id}", json={"owner": False}, headers=_en_superuser(client, monde)
    )
    assert reponse.status_code == 200
    assert reponse.json()["est_owner"] is False


# --- Invisible pour les écoles ---


def test_invisible_dans_les_listes_des_ecoles(client, monde):
    entetes = _en_superuser(client, monde)
    for ecole in [monde["a"], monde["b"]]:
        admins = client.get(f"/comptes?ecole_id={ecole.id}&role=admin", headers=entetes).json()
        assert monde["su"].id not in [c["id"] for c in admins]
        tableau = client.get(f"/ecoles/{ecole.id}/administrateurs", headers=entetes).json()
        assert monde["su"].id not in [a["id"] for a in tableau]


def test_son_compte_n_est_lisible_que_par_lui(client, monde):
    url = f"/comptes/{monde['su'].id}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=entetes_session(monde["admin_b"])).status_code == 404
    assert client.get(url, headers=_en_superuser(client, monde)).status_code == 200


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
    # Le mot de passe vit sur la ligne de son email (§6.3ter).
    stocke = Acces().par_email(db_session, EMAIL).hashed_password
    assert mots_de_passe.verifier("nouveau-mot-de-passe", stocke)
    assert not mots_de_passe.verifier(MOT_DE_PASSE, stocke)


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
