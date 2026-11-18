"""Sous-module Mail, étape 1 (spec/modules/mail.md §2-4, §9) : éteint par
défaut, droit « Boîte mail du club », connexion de la boîte Gmail. Aucun
appel réseau : `Connection.check` est remplacé."""

import pytest
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles
from groups import rights

CONNEXION = {"address": " club.sambo@gmail.com ", "code": "abcd efgh ijkl mnop"}


@pytest.fixture()
def ecole(db_session):
    return Ecoles().create(db_session, nom="Sambo La Ciotat", code_postal="13600")


@pytest.fixture()
def gmail(monkeypatch):
    from app import main
    from mail.gmail import REFUSED, MailRefused

    appels = []

    def check(address, password):
        appels.append((address, password))
        if password != "abcdefghijklmnop":
            raise MailRefused(REFUSED)

    monkeypatch.setattr(main.core.mail_connection, "check", check)
    return appels


def test_eteint_par_defaut_et_s_allume_avec_la_messagerie(client, db_session, ecole):
    from app import main
    from registry import activation

    # Une école sans aucun choix : seul Mail est éteint, le reste ne change pas.
    assert activation.disabled(db_session, ecole.id) == {"mail"}
    activation.set_enabled(db_session, ecole.id, main.MODULES, "messaging", False)
    activation.set_enabled(db_session, ecole.id, main.MODULES, "mail", True)
    off = activation.disabled(db_session, ecole.id)
    assert "mail" not in off and "messaging" not in off
    # On n'éteint pas la Messagerie tant que Mail est allumé.
    with pytest.raises(ValueError):
        activation.set_enabled(db_session, ecole.id, main.MODULES, "messaging", False)
    activation.set_enabled(db_session, ecole.id, main.MODULES, "mail", False)
    assert "mail" in activation.disabled(db_session, ecole.id)


def test_connecter_et_deconnecter(client, db_session, ecole, gmail):
    from mail import MailAccount

    url = f"/ecoles/{ecole.id}/mail"
    assert client.get(url).json()["connected"] is False
    refus = client.put(url, json={**CONNEXION, "code": "faux code"})
    assert refus.status_code == 422 and "Google n'a pas accepté ce code" in refus.json()["detail"]
    assert client.get(url).json()["connected"] is False

    etat = client.put(url, json=CONNEXION).json()
    assert (etat["connected"], etat["address"], etat["cut"]) == (True, "club.sambo@gmail.com", False)
    # Code sans espaces, chiffré en base.
    assert gmail[-1] == ("club.sambo@gmail.com", "abcdefghijklmnop")
    ligne = db_session.query(MailAccount).one()
    assert "abcdefghijklmnop" not in ligne.app_password_encrypted

    assert client.delete(url).status_code == 204
    assert client.get(url).json()["connected"] is False
    assert db_session.query(MailAccount).count() == 0


def test_adresse_invalide(client, ecole, gmail):
    reponse = client.put(f"/ecoles/{ecole.id}/mail", json={**CONNEXION, "address": "pas une adresse"})
    assert reponse.status_code == 422 and gmail == []


def test_ecoles_etanches(client, db_session, ecole, gmail):
    client.put(f"/ecoles/{ecole.id}/mail", json=CONNEXION)
    autre = Ecoles().create(db_session, nom="Le Beausset", code_postal="83330")
    assert client.get(f"/ecoles/{autre.id}/mail").json()["connected"] is False


@pytest.mark.rbac_reel
def test_droit_boite_mail_du_club(client, db_session, ecole, gmail):
    from app import main
    from registry import activation

    proprietaire = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Noir", prenom="Léo")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Blanc", prenom="Ima")
    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Lina")
    url = f"/ecoles/{ecole.id}/mail"

    # Éteint par défaut : introuvable, même pour l'Administrateur principal.
    assert client.get(url, headers=entetes_session(proprietaire)).status_code == 404
    activation.set_enabled(db_session, ecole.id, main.MODULES, "mail", True)

    # Sans le droit, personne ne voit la boîte (pas même l'Administrateur principal).
    for qui in (proprietaire, admin, eleve):
        assert client.get(url, headers=entetes_session(qui)).status_code == 403
    assert client.put(url, json=CONNEXION, headers=entetes_session(proprietaire)).status_code == 403

    for qui in (proprietaire, admin):
        rights.add(db_session, qui, "mail.read")
    db_session.commit()
    assert client.get(url, headers=entetes_session(admin)).json()["can_connect"] is False
    assert client.put(url, json=CONNEXION, headers=entetes_session(admin)).status_code == 403
    assert client.get(url, headers=entetes_session(proprietaire)).json()["can_connect"] is True
    assert client.put(url, json=CONNEXION, headers=entetes_session(proprietaire)).status_code == 200
    assert client.get(url, headers=entetes_session(admin)).json()["connected"] is True
    assert client.delete(url, headers=entetes_session(admin)).status_code == 403
    assert client.get(url, headers=entetes_session(eleve)).status_code == 403
