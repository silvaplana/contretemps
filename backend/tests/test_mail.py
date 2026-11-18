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

    def check(address, password, provider="gmail"):
        appels.append((address, password))
        if password not in ("abcdefghijklmnop", "MotPasseInfomaniak16+"):
            raise MailRefused(REFUSED)

    monkeypatch.setattr(main.core.mail_connection, "check", check)
    return appels


def test_eteint_par_defaut_et_s_allume_avec_la_messagerie(client, db_session, ecole):
    from app import main
    from registry import activation

    # Une école sans aucun choix : Mail est éteint, comme HelloAsso et FFST.
    assert activation.disabled(db_session, ecole.id) == {"mail", "helloasso", "ffst", "trials"}
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

    # Sans le droit, personne ne voit les mails (pas même l'Administrateur
    # principal) ; lui connecte la boîte depuis Fonctionnalités sans le droit.
    for qui in (admin, eleve):
        assert client.get(url, headers=entetes_session(qui)).status_code == 403
    etat = client.get(url, headers=entetes_session(proprietaire)).json()
    assert (etat["can_connect"], etat["can_read"]) == (True, False)  # pas de puce Mail
    assert client.get(f"{url}/messages", headers=entetes_session(proprietaire)).status_code == 403

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
    # Les mails : le droit suffit ; sans lui, rien.
    assert client.get(f"{url}/unread", headers=entetes_session(admin)).status_code == 200
    assert client.get(f"{url}/messages", headers=entetes_session(eleve)).status_code == 403
    assert client.post(f"{url}/send", data={"to": "a@b.fr"}, headers=entetes_session(eleve)).status_code == 403


class FakeWebmail:
    """Une boîte Gmail en mémoire : ce que reçoivent les routes."""

    def __init__(self, address, password):
        self.address, self.password = address, password
        self.sender_name = ""
        self.calls = []
        self.refuse = False

    def _note(self, *call):
        if self.refuse:
            from mail.imap import WebmailRefusedError

            raise WebmailRefusedError("La boîte mail n'est plus connectée")
        self.calls.append(call)

    def folders(self):
        self._note("folders")
        return {"address": self.address, "folders": [{"key": "inbox", "label": "Boîte de réception"}], "unread": 2}

    def unread(self):
        self._note("unread")
        return 2

    def list(self, folder, before, query):
        self._note("list", folder, before, query)
        return {"folder": folder, "messages": [{"uid": 7, "subject": "Cours d'essai"}], "hasMore": False}

    def get(self, folder, uid):
        self._note("get", folder, uid)
        if uid == 404:
            from mail.imap import WebmailNotFoundError

            raise WebmailNotFoundError()
        return {"uid": uid, "folder": folder, "subject": "Cours d'essai", "seen": True}

    def attachment(self, folder, uid, index):
        self._note("attachment", folder, uid, index)
        return b"<script>alert(1)</script>", "page é.html", "text/html"

    def set_flags(self, folder, uid, seen=None, starred=None):
        self._note("flags", folder, uid, seen, starred)
        return {}

    def move(self, folder, uid, to):
        self._note("move", folder, uid, to)
        return {}

    def delete(self, folder, uid):
        self._note("delete", folder, uid)
        return {}

    def send(self, **kwargs):
        self._note("send", self.sender_name, kwargs)
        return {"sent": True}

    def bulk(self, folder, uids, action):
        self._note("bulk", folder, uids, action)
        return {}


@pytest.fixture()
def boite(client, ecole, gmail, monkeypatch):
    from app import main

    boites = []

    def webmail(address, password, provider="gmail"):
        boites.append(FakeWebmail(address, password))
        boites[-1].provider = provider
        return boites[-1]

    monkeypatch.setattr(main.core.mail_connection, "webmail", webmail)
    main.core.mail_connection._clients.clear()
    client.put(f"/ecoles/{ecole.id}/mail", json=CONNEXION)
    return boites


def test_lire_et_ranger_les_mails(client, ecole, boite):
    url = f"/ecoles/{ecole.id}/mail"
    assert client.get(f"{url}/folders").json()["unread"] == 2
    assert client.get(f"{url}/unread").json() == {"unread": 2}
    assert client.get(f"{url}/messages", params={"folder": "inbox", "q": "essai"}).json()["messages"][0]["uid"] == 7
    assert client.get(f"{url}/messages/inbox/7").json()["subject"] == "Cours d'essai"
    assert client.get(f"{url}/messages/inbox/404").status_code == 404
    client.put(f"{url}/messages/inbox/7/flags", json={"starred": True})
    client.post(f"{url}/messages/inbox/7/move", json={"to": "archive"})
    client.delete(f"{url}/messages/trash/9")
    client.post(f"{url}/bulk", json={"folder": "inbox", "uids": [1, 2], "action": "trash"})
    # Un seul client, avec le code déchiffré.
    assert len(boite) == 1 and boite[0].password == "abcdefghijklmnop"
    assert boite[0].calls[-4:] == [
        ("flags", "inbox", 7, None, True),
        ("move", "inbox", 7, "archive"),
        ("delete", "trash", 9),
        ("bulk", "inbox", [1, 2], "trash"),
    ]

    # Pièce jointe toujours téléchargée, jamais interprétée par le navigateur.
    reponse = client.get(f"{url}/messages/inbox/7/attachments/2")
    assert reponse.headers["content-type"] == "application/octet-stream"
    assert reponse.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''page%20%C3%A9.html" in reponse.headers["content-disposition"]
    assert reponse.headers["x-content-type-options"] == "nosniff"


def test_google_coupe_l_acces(client, ecole, boite):
    url = f"/ecoles/{ecole.id}/mail"
    assert client.get(f"{url}/folders").status_code == 200
    boite[0].refuse = True
    reponse = client.get(f"{url}/messages")
    assert reponse.status_code == 409 and reponse.json()["detail"] == "La boîte mail n'est plus connectée"
    assert client.get(url).json()["cut"] is True
    # Plus de connexion à Gmail tant que la boîte est coupée ; pastille à 0.
    assert client.get(f"{url}/unread").json() == {"unread": 0}
    assert client.get(f"{url}/folders").status_code == 409
    # Reconnecter efface le bandeau.
    client.put(url, json=CONNEXION)
    assert client.get(url).json()["cut"] is False
    assert client.get(f"{url}/folders").status_code == 200


def test_pas_de_boite_pas_de_mails(client, ecole):
    assert client.get(f"/ecoles/{ecole.id}/mail/messages").status_code == 409
    assert client.get(f"/ecoles/{ecole.id}/mail/unread").json() == {"unread": 0}


def test_boite_infomaniak(client, db_session, ecole, gmail, monkeypatch):
    """Seb, 18 novembre : une boîte Infomaniak (ik.me) se connecte aussi,
    sur le serveur d'Infomaniak."""
    from app import main
    from mail import MailAccount
    from mail.gmail import PROVIDERS

    clients = []
    monkeypatch.setattr(
        main.core.mail_connection, "webmail", lambda a, p, provider: clients.append((a, p, provider)) or FakeWebmail(a, p)
    )
    url = f"/ecoles/{ecole.id}/mail"
    infomaniak = {"address": "club@ik.me", "code": " MotPasseInfomaniak16+ ", "provider": "infomaniak"}
    etat = client.put(url, json=infomaniak).json()
    assert (etat["address"], etat["provider"]) == ("club@ik.me", "infomaniak")
    assert gmail[-1] == ("club@ik.me", "MotPasseInfomaniak16+")
    assert db_session.query(MailAccount).one().provider == "infomaniak"
    client.get(f"{url}/unread")
    assert clients == [("club@ik.me", "MotPasseInfomaniak16+", "infomaniak")]
    assert PROVIDERS["infomaniak"].imap_host == PROVIDERS["infomaniak"].smtp_host == "mail.infomaniak.com"
    assert client.put(url, json={**infomaniak, "provider": "orange"}).status_code == 422
    # Sans fournisseur : Gmail, comme avant.
    assert client.put(url, json=CONNEXION).json()["provider"] == "gmail"


def test_envoyer_repondre_transferer(client, ecole, boite):
    """Étape 3 (spec §7) : envoi au nom du club, pièces jointes, réponse
    marquée « répondu », transfert avec les pièces jointes du mail."""
    url = f"/ecoles/{ecole.id}/mail/send"
    reponse = client.post(
        url,
        data={
            "to": "a@b.fr", "cc": "c@d.fr", "bcc": "e@f.fr", "subject": "Re: Cours", "body": "Merci",
            "inReplyTo": "<x@y>", "references": "<w@y>", "answeredFolder": "inbox", "answeredUid": "7",
        },
        files=[("files", ("note.txt", b"hello", "text/plain"))],
    )
    assert reponse.json() == {"sent": True}
    _send, nom, envoi = boite[0].calls[-1]
    assert nom == "Sambo La Ciotat"  # « De : » le nom de l'école
    assert envoi["attachments"] == [("note.txt", "text/plain", b"hello")]
    assert (envoi["to"], envoi["cc"], envoi["bcc"]) == ("a@b.fr", "c@d.fr", "e@f.fr")
    assert (envoi["in_reply_to"], envoi["references"]) == ("<x@y>", "<w@y>")
    assert envoi["answered"] == ("inbox", 7) and envoi["forward"] is None

    client.post(url, data={"to": "a@b.fr", "subject": "Fwd: x", "forwardFolder": "inbox", "forwardUid": "7"})
    envoi = boite[0].calls[-1][2]
    assert envoi["forward"] == ("inbox", 7) and envoi["answered"] is None and envoi["attachments"] == []

    gros = b"x" * (18 * 1024 * 1024 + 1)
    reponse = client.post(url, data={"to": "a@b.fr"}, files=[("files", ("gros.bin", gros, "application/octet-stream"))])
    assert reponse.status_code == 400 and "18 Mo" in reponse.json()["detail"]
