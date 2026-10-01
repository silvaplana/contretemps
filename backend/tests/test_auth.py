"""Connexion par mot de passe, session, bascule de profil, invitation et
mot de passe oublié (voir spec §2.2 et §6.3ter)."""

import re
import time
from datetime import timedelta

import pytest
from acces import Acces, LienAcces, Utilisateur
from acces.models import maintenant
from comptes import Comptes, RoleCompte, roles
from conftest import MOT_DE_PASSE, donner_mot_de_passe, entetes_session
from ecoles import Ecoles
from securite import jetons


@pytest.fixture()
def ecole(db_session):
    """Un parent admin et son enfant (même email, donc une famille et un
    seul mot de passe), un professeur à son propre email, un élève sans
    email."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="j.dho@x.fr")
    enfant = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Dho", prenom="Zélie", email="j.dho@x.fr")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie", email="m.p@x.fr")
    sans_email = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    donner_mot_de_passe(db_session, "j.dho@x.fr")
    donner_mot_de_passe(db_session, "m.p@x.fr")
    return {"ecole": ecole, "admin": admin, "enfant": enfant, "prof": prof, "sans_email": sans_email}


def _login(client, identifiant, mot_de_passe=MOT_DE_PASSE, **plus):
    return client.post("/auth/login", json={"identifiant": identifiant, "mot_de_passe": mot_de_passe, **plus})


def _bearer(jeton):
    return {"Authorization": f"Bearer {jeton}"}


def _jeton_du_mail(mails, page):
    return re.search(rf"/{page}\?jeton=(\S+)", mails[-1][2]).group(1)


# --- Connexion ---


def test_connexion_par_nom_prenom_ou_email(client, ecole):
    par_nom = _login(client, "Marie Pesenti")
    assert par_nom.status_code == 200
    assert par_nom.json()["compte"]["id"] == ecole["prof"].id
    assert par_nom.json()["jeton"]
    assert _login(client, "m.p@x.fr").json()["compte"]["id"] == ecole["prof"].id


def test_identifiant_sans_casse_ni_accents_mais_pas_le_mot_de_passe(client, ecole):
    assert _login(client, "ZELIE dho").json()["compte"]["id"] == ecole["enfant"].id
    assert _login(client, " M.P@X.FR ").json()["compte"]["id"] == ecole["prof"].id
    assert _login(client, "Marie Pesenti", MOT_DE_PASSE.upper()).status_code == 401


def test_refus_sans_reveler_pourquoi(client, ecole):
    refus = [
        _login(client, "Marie Pesenti", "mauvais-mot-de-passe"),
        _login(client, "Personne Inconnue"),
        _login(client, "Léon Perrin"),  # fiche sans email : pas de connexion possible
    ]
    assert {r.status_code for r in refus} == {401}
    assert {r.json()["detail"] for r in refus} == {"Identifiant ou mot de passe incorrect"}


def test_email_sans_mot_de_passe_refuse(client, db_session, ecole):
    Comptes().create(db_session, ecole_id=ecole["ecole"].id, role="eleve", nom="Roux", prenom="Ana", email="a@x.fr")
    assert _login(client, "a@x.fr", "").status_code == 401
    assert _login(client, "a@x.fr").status_code == 401


def test_famille_par_email_ouvre_le_profil_de_plus_haut_rang(client, ecole):
    """Décision du 2026-10-01. Par son nom, chacun arrive sur sa fiche."""
    assert _login(client, "j.dho@x.fr").json()["compte"]["id"] == ecole["admin"].id
    assert _login(client, "Zélie Dho").json()["compte"]["id"] == ecole["enfant"].id


def test_plusieurs_ecoles_demandent_de_choisir(client, db_session, ecole):
    autre = Ecoles().create(db_session, nom="Autre école", code_postal="13000")
    la_bas = Comptes().create(db_session, ecole_id=autre.id, role="professeur", nom="Pesenti", prenom="Marie", email="m.p@x.fr")

    reponse = _login(client, "Marie Pesenti").json()
    assert reponse["compte"] is None and reponse["jeton"] is None
    assert {(c["ecole_nom"], c["compte_id"]) for c in reponse["choix"]} == {
        ("Contretemps", ecole["prof"].id), ("Autre école", la_bas.id),
    }
    choisi = _login(client, "Marie Pesenti", compte_id=la_bas.id).json()
    assert choisi["compte"]["id"] == la_bas.id and choisi["jeton"]
    # Un compte_id qui n'est pas dans les choix ne passe pas.
    assert _login(client, "Marie Pesenti", compte_id=ecole["admin"].id).status_code == 401


def test_cinq_mots_de_passe_faux_bloquent_l_email(client, ecole):
    for _ in range(5):
        assert _login(client, "Marie Pesenti", "faux").status_code == 401
    # Même le bon mot de passe est refusé pendant le blocage, sans le dire.
    assert _login(client, "m.p@x.fr").status_code == 401
    # Les autres adresses ne sont pas touchées.
    assert _login(client, "j.dho@x.fr").status_code == 200


# --- Session : un jeton à chaque requête ---


@pytest.mark.rbac_reel
def test_sans_session_aucune_route_ne_repond(client, ecole):
    route = f"/eleves?ecole_id={ecole['ecole'].id}"
    assert client.get(route).status_code == 401
    # Le numéro de fiche seul ne donne plus aucun droit.
    assert client.get(route, headers={"X-Compte-Id": str(ecole["admin"].id)}).status_code == 401
    assert client.get(route, headers={"Authorization": "Bearer faux.jeton"}).status_code == 401
    assert client.get(route, headers=entetes_session(ecole["admin"])).status_code == 200
    # Routes publiques : toujours ouvertes.
    assert client.get("/health").status_code == 200
    assert client.get("/ecoles").status_code == 200


@pytest.mark.rbac_reel
def test_le_profil_actif_doit_appartenir_a_l_email_connecte(client, ecole):
    session_prof = entetes_session(ecole["prof"])
    usurpation = {**session_prof, "X-Compte-Id": str(ecole["admin"].id)}
    assert client.get(f"/ecoles/{ecole['ecole'].id}", headers=usurpation).status_code == 401


@pytest.mark.rbac_reel
def test_un_profil_de_rang_superieur_redemande_le_mot_de_passe(client, ecole):
    """Un enfant connecté sur sa fiche ne devient pas son parent admin en
    changeant de numéro de fiche (§2.2)."""
    jeton = _login(client, "Zélie Dho").json()["jeton"]
    en_parent = {**_bearer(jeton), "X-Compte-Id": str(ecole["admin"].id)}
    refus = client.get(f"/ecoles/{ecole['ecole'].id}", headers=en_parent)
    assert refus.status_code == 403
    assert refus.json()["detail"]["code"] == "mot_de_passe_requis"


@pytest.mark.rbac_reel
def test_le_jeton_est_prolonge_a_l_usage(client, db_session, ecole):
    utilisateur = Acces().par_email(db_session, "m.p@x.fr")
    ancien = jetons.emettre(
        utilisateur.id, rang=1, empreinte=Acces().empreinte(utilisateur), maintenant=time.time() - 2 * 24 * 3600
    )
    entetes = {**_bearer(ancien), "X-Compte-Id": str(ecole["prof"].id)}
    reponse = client.get(f"/cours/999999/eleves", headers=entetes)
    nouveau = reponse.headers.get("X-Jeton-Renouvele")
    assert nouveau and jetons.lire(nouveau).emis_le > jetons.lire(ancien).emis_le
    # Un jeton récent n'est pas remplacé à chaque requête.
    assert "X-Jeton-Renouvele" not in client.get("/cours/999999/eleves", headers={**entetes, **_bearer(nouveau)}).headers
    # Passé 30 jours sans usage : expiré.
    expire = jetons.emettre(
        utilisateur.id, rang=1, empreinte=Acces().empreinte(utilisateur), maintenant=time.time() - 31 * 24 * 3600
    )
    assert client.get("/cours/999999/eleves", headers={**entetes, **_bearer(expire)}).status_code == 401


# --- Bascule de profil famille ---


def test_bascule_libre_vers_le_bas_mot_de_passe_pour_remonter(client, ecole):
    jeton_admin = _login(client, "j.dho@x.fr").json()["jeton"]
    vers_enfant = client.post("/auth/bascule", json={"vers_compte_id": ecole["enfant"].id}, headers=_bearer(jeton_admin))
    assert vers_enfant.status_code == 200
    assert vers_enfant.json()["compte"]["id"] == ecole["enfant"].id
    jeton_enfant = vers_enfant.json()["jeton"]
    assert jetons.lire(jeton_enfant).rang == roles.RANG["eleve"]

    remonter = {"vers_compte_id": ecole["admin"].id}
    sans = client.post("/auth/bascule", json=remonter, headers=_bearer(jeton_enfant))
    assert sans.status_code == 403 and sans.json()["detail"]["code"] == "mot_de_passe_requis"
    faux = client.post("/auth/bascule", json={**remonter, "mot_de_passe": "faux"}, headers=_bearer(jeton_enfant))
    assert faux.status_code == 401
    bon = client.post("/auth/bascule", json={**remonter, "mot_de_passe": MOT_DE_PASSE}, headers=_bearer(jeton_enfant))
    assert bon.status_code == 200 and bon.json()["compte"]["roles"] == ["admin", "owner"]
    assert jetons.lire(bon.json()["jeton"]).rang == roles.RANG["admin"]


def test_bascule_refusee_vers_un_profil_d_un_autre_email(client, ecole):
    jeton = _login(client, "j.dho@x.fr").json()["jeton"]
    reponse = client.post(
        "/auth/bascule", json={"vers_compte_id": ecole["prof"].id, "mot_de_passe": MOT_DE_PASSE}, headers=_bearer(jeton)
    )
    assert reponse.status_code == 401
    assert client.post("/auth/bascule", json={"vers_compte_id": ecole["enfant"].id}).status_code == 401


def test_un_eleve_promu_admin_a_tous_ses_roles(client, db_session, ecole):
    """Plus de cas particulier (§2.2) : connecté, il a tous ses rôles."""
    ecole["enfant"].roles.append(RoleCompte(role=roles.ADMIN))
    db_session.commit()
    assert _login(client, "Zélie Dho").json()["compte"]["roles"] == ["admin", "eleve"]


# --- Changer son mot de passe (Profil) ---


@pytest.mark.rbac_reel
def test_changer_son_mot_de_passe_deconnecte_les_autres_appareils(client, ecole):
    ici = _login(client, "Marie Pesenti").json()["jeton"]
    ailleurs = _login(client, "Marie Pesenti").json()["jeton"]
    route = f"/cours?ecole_id={ecole['ecole'].id}"  # publique
    protegee = "/cours/999999/eleves"
    profil = {"X-Compte-Id": str(ecole["prof"].id)}
    assert client.get(protegee, headers={**_bearer(ailleurs), **profil}).status_code == 200

    corps = {"ancien": "faux", "nouveau": "nouveau-mot-de-passe"}
    assert client.post("/auth/mot-de-passe", json=corps, headers={**_bearer(ici), **profil}).status_code == 401
    court = {"ancien": MOT_DE_PASSE, "nouveau": "court"}
    assert client.post("/auth/mot-de-passe", json=court, headers={**_bearer(ici), **profil}).status_code == 422
    corps["ancien"] = MOT_DE_PASSE
    change = client.post("/auth/mot-de-passe", json=corps, headers={**_bearer(ici), **profil})
    assert change.status_code == 200

    assert client.get(protegee, headers={**_bearer(change.json()["jeton"]), **profil}).status_code == 200
    assert client.get(protegee, headers={**_bearer(ailleurs), **profil}).status_code == 401
    assert client.get(protegee, headers={**_bearer(ici), **profil}).status_code == 401
    assert _login(client, "Marie Pesenti").status_code == 401
    assert _login(client, "Marie Pesenti", "nouveau-mot-de-passe").status_code == 200
    assert client.get(route).status_code == 200


# --- Invitation et suivi ---


def _statuts(client, ecole):
    return client.get(f"/ecoles/{ecole['ecole'].id}/acces").json()


def test_invitation_de_bout_en_bout(client, db_session, ecole, mails):
    eleve = Comptes().create(db_session, ecole_id=ecole["ecole"].id, role="eleve", nom="Roux", prenom="Ana", email="Parent@X.fr")
    frere = Comptes().create(db_session, ecole_id=ecole["ecole"].id, role="eleve", nom="Roux", prenom="Tom", email="parent@x.fr")
    avant = _statuts(client, ecole)
    assert avant[str(eleve.id)] == {"statut": "pas_invite", "date": None}
    assert avant[str(ecole["sans_email"].id)]["statut"] == "pas_email"

    invitation = client.post(f"/ecoles/{ecole['ecole'].id}/invitations", json={"compte_ids": [eleve.id]})
    assert invitation.json() == {"emails": 1, "en_cours": False}
    # Un seul mail pour l'adresse, qui nomme les deux profils.
    assert len(mails) == 1 and mails[0][0] == "parent@x.fr"
    assert "Contretemps" in mails[0][1] and "Profils : Ana, Tom." in mails[0][2]
    statuts = _statuts(client, ecole)
    assert statuts[str(eleve.id)]["statut"] == statuts[str(frere.id)]["statut"] == "invite"

    jeton = _jeton_du_mail(mails, "activer")
    lien = client.get(f"/auth/liens/{jeton}").json()
    assert lien == {"type": "invitation", "email": "parent@x.fr", "prenoms": ["Ana", "Tom"], "ecole_nom": "Contretemps"}
    assert _statuts(client, ecole)[str(eleve.id)]["statut"] == "consultee"

    assert client.post(f"/auth/liens/{jeton}/mot-de-passe", json={"mot_de_passe": "court"}).status_code == 422
    session = client.post(f"/auth/liens/{jeton}/mot-de-passe", json={"mot_de_passe": "mon-mot-de-passe"}).json()
    # Connectée directement, sans retaper son mot de passe.
    assert session["compte"]["id"] == eleve.id and session["jeton"]
    assert _statuts(client, ecole)[str(frere.id)]["statut"] == "finalise"
    assert _login(client, "Tom Roux", "mon-mot-de-passe").status_code == 200
    # Le lien ne sert qu'une fois.
    assert client.get(f"/auth/liens/{jeton}").status_code == 404
    assert client.post(f"/auth/liens/{jeton}/mot-de-passe", json={"mot_de_passe": "autre-mot-de-passe"}).status_code == 404

    installee = client.post("/auth/appli-installee", headers=_bearer(session["jeton"]))
    assert installee.status_code == 204
    assert _statuts(client, ecole)[str(eleve.id)]["statut"] == "installee"
    # Le premier signal fixe la date.
    premiere = db_session.query(Utilisateur).filter_by(email="parent@x.fr").one().appli_installee_le
    client.post("/auth/appli-installee", headers=_bearer(session["jeton"]))
    db_session.expire_all()
    assert db_session.query(Utilisateur).filter_by(email="parent@x.fr").one().appli_installee_le == premiere


def test_un_nouveau_lien_annule_le_precedent_et_un_lien_expire(client, db_session, ecole, mails):
    route = f"/ecoles/{ecole['ecole'].id}/invitations"
    client.post(route, json={"compte_ids": [ecole["prof"].id]})
    premier = _jeton_du_mail(mails, "activer")
    client.post(route, json={"compte_ids": [ecole["prof"].id]})
    second = _jeton_du_mail(mails, "activer")
    assert client.get(f"/auth/liens/{premier}").status_code == 404
    assert client.get(f"/auth/liens/{second}").status_code == 200

    lien = db_session.query(LienAcces).one()
    assert timedelta(days=6, hours=23) < lien.expire_le - maintenant() <= timedelta(days=7)
    lien.expire_le = maintenant() - timedelta(minutes=1)
    db_session.commit()
    assert client.get(f"/auth/liens/{second}").status_code == 404


def test_inviter_plusieurs_adresses_un_mail_par_adresse(client, ecole, mails):
    tous = [ecole[c].id for c in ("admin", "enfant", "prof", "sans_email")]
    reponse = client.post(f"/ecoles/{ecole['ecole'].id}/invitations", json={"compte_ids": tous})
    assert reponse.json() == {"emails": 2, "en_cours": True}
    assert sorted(m[0] for m in mails) == ["j.dho@x.fr", "m.p@x.fr"]
    statuts = _statuts(client, ecole)
    assert statuts[str(ecole["prof"].id)]["statut"] == "finalise"  # avait déjà un mot de passe
    assert statuts[str(ecole["sans_email"].id)]["statut"] == "pas_email"
    aucune = client.post(f"/ecoles/{ecole['ecole'].id}/invitations", json={"compte_ids": [ecole["sans_email"].id]})
    assert aucune.status_code == 409


def test_sans_smtp_l_invitation_est_refusee(client, ecole, monkeypatch):
    from app.main import invitations_client

    monkeypatch.setattr(invitations_client.mails.envoi, "actif", False)
    monkeypatch.setattr(invitations_client.mails, "dans_les_journaux", False)
    route = f"/ecoles/{ecole['ecole'].id}/invitations"
    assert client.post(route, json={"compte_ids": [ecole["prof"].id]}).status_code == 503
    tous = [ecole["prof"].id, ecole["admin"].id]
    assert client.post(route, json={"compte_ids": tous}).status_code == 503
    # Rien n'est noté "invité" si le mail n'est pas parti.
    assert client.get(f"/ecoles/{ecole['ecole'].id}/acces").json()[str(ecole["prof"].id)]["statut"] == "finalise"


@pytest.mark.rbac_reel
def test_seul_un_admin_invite(client, ecole, mails):
    route = f"/ecoles/{ecole['ecole'].id}/invitations"
    corps = {"compte_ids": [ecole["prof"].id]}
    assert client.post(route, json=corps, headers=entetes_session(ecole["prof"])).status_code == 403
    assert client.post(route, json=corps, headers=entetes_session(ecole["admin"])).status_code == 200
    assert client.get(f"/ecoles/{ecole['ecole'].id}/acces", headers=entetes_session(ecole["prof"])).status_code == 403


# --- Mot de passe oublié ---


def test_mot_de_passe_oublie(client, db_session, ecole, mails):
    jamais_invitee = Comptes().create(
        db_session, ecole_id=ecole["ecole"].id, role="eleve", nom="Roux", prenom="Ana", email="a.roux@x.fr"
    )
    # Toujours la même réponse, qu'un compte existe ou non.
    assert client.post("/auth/mot-de-passe-oublie", json={"identifiant": "Personne Inconnue"}).status_code == 204
    assert client.post("/auth/mot-de-passe-oublie", json={"identifiant": "Léon Perrin"}).status_code == 204
    assert mails == []

    # Une personne jamais invitée reçoit aussi un lien (décision du 2026-10-01).
    assert client.post("/auth/mot-de-passe-oublie", json={"identifiant": "Ana Roux"}).status_code == 204
    assert [m[0] for m in mails] == ["a.roux@x.fr"]
    jeton = _jeton_du_mail(mails, "reinitialiser")
    lien = db_session.query(LienAcces).one()
    assert lien.type == "reinitialisation" and lien.expire_le - maintenant() <= timedelta(hours=1)
    assert client.get(f"/auth/liens/{jeton}").json()["type"] == "reinitialisation"
    # Un lien de réinitialisation ne compte pas comme une invitation consultée.
    assert _statuts(client, ecole)[str(jamais_invitee.id)]["statut"] == "pas_invite"

    session = client.post(f"/auth/liens/{jeton}/mot-de-passe", json={"mot_de_passe": "tout-nouveau-mdp"}).json()
    assert session["compte"]["id"] == jamais_invitee.id
    assert _login(client, "a.roux@x.fr", "tout-nouveau-mdp").status_code == 200


def test_mot_de_passe_oublie_remplace_l_ancien(client, ecole, mails):
    client.post("/auth/mot-de-passe-oublie", json={"identifiant": "m.p@x.fr"})
    jeton = _jeton_du_mail(mails, "reinitialiser")
    client.post(f"/auth/liens/{jeton}/mot-de-passe", json={"mot_de_passe": "tout-nouveau-mdp"})
    assert _login(client, "Marie Pesenti").status_code == 401
    assert _login(client, "Marie Pesenti", "tout-nouveau-mdp").status_code == 200


def test_demandes_de_mot_de_passe_oublie_limitees(client, ecole, mails):
    for _ in range(8):
        assert client.post("/auth/mot-de-passe-oublie", json={"identifiant": "m.p@x.fr"}).status_code == 204
    assert len(mails) == 5


# --- Filet de sécurité : la liste des routes publiques est fermée ---


@pytest.mark.rbac_reel
def test_seules_les_routes_publiques_repondent_sans_session(client):
    """Toute nouvelle route est protégée d'office : pour l'ouvrir sans
    session, il faut l'ajouter à rbac.ROUTES_PUBLIQUES, en connaissance de
    cause."""
    from app.main import app
    from comptes import rbac
    from fastapi.routing import APIRoute

    ouvertes = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        chemin = re.sub(r"\{[^}]+\}", "1", route.path)
        for methode in route.methods - {"HEAD", "OPTIONS"}:
            if client.request(methode, chemin).status_code != 401:
                ouvertes.add((methode, route.path))
    assert ouvertes == rbac.ROUTES_PUBLIQUES


@pytest.mark.rbac_reel
def test_flux_temps_reel_reserve_a_sa_propre_session(client, db_session, ecole):
    """Le jeton voyage dans l'URL (EventSource n'envoie pas d'en-tête) ; on
    n'ouvre que le flux de l'un de ses propres profils."""
    jeton = _login(client, "Marie Pesenti").json()["jeton"]
    autre = f"/comptes/{ecole['admin'].id}/messagerie/evenements?jeton={jeton}&compte={ecole['prof'].id}"
    assert client.get(autre).status_code == 403
    assert client.get(f"/comptes/{ecole['prof'].id}/messagerie/evenements").status_code == 401


# --- Migration ---


def test_migration_deplace_le_mot_de_passe_du_superuser(tmp_path, monkeypatch):
    from pathlib import Path

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "7c3e9a1f2d56")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        c.execute(sa.text(
            "INSERT INTO comptes (id, nom, prenom, email, hashed_password_ou_code, created_at)"
            " VALUES (9, 'S', 'U', ' Proprio@Exemple.fr ', 'scrypt$x', CURRENT_TIMESTAMP)"
        ))
    command.upgrade(config, "9d2f4b6a8c10")
    with moteur.connect() as c:
        lignes = c.execute(sa.text("SELECT email, hashed_password FROM utilisateurs")).all()
    assert lignes == [("proprio@exemple.fr", "scrypt$x")]
    command.downgrade(config, "7c3e9a1f2d56")
    with moteur.connect() as c:
        assert "utilisateurs" not in sa.inspect(c).get_table_names()
    moteur.dispose()
