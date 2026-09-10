"""Tests du module notifications (Web Push, voir spec/SPEC.md §8).

⚠️ Ne fait JAMAIS de vrai appel réseau vers un service de push (FCM,
Mozilla...) : `webpush` est systématiquement remplacé par un faux (voir
`_webpush_factice` ci-dessous) — un vrai appel échouerait de toute façon
(faux endpoint/clés) et n'a rien à faire dans une suite de tests.
"""

from types import SimpleNamespace

import pytest
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from pywebpush import WebPushException

from notifications import Notifications


def _ecole_et_compte(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    compte = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    return ecole, compte


def test_abonner_puis_lister(db_session):
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    abonnement = client.abonner(db_session, compte.id, "https://push.exemple/1", "p256dh-1", "auth-1")
    assert abonnement.compte_id == compte.id
    assert [a.endpoint for a in client.abonnements_du_compte(db_session, compte.id)] == [
        "https://push.exemple/1"
    ]


def test_reabonnement_meme_endpoint_met_a_jour_sans_doublon(db_session):
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    client.abonner(db_session, compte.id, "https://push.exemple/1", "ancienne", "auth")
    client.abonner(db_session, compte.id, "https://push.exemple/1", "nouvelle", "auth")
    abonnements = client.abonnements_du_compte(db_session, compte.id)
    assert len(abonnements) == 1
    assert abonnements[0].cle_p256dh == "nouvelle"


def test_desabonner(db_session):
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    client.abonner(db_session, compte.id, "https://push.exemple/1", "p256dh", "auth")
    assert client.desabonner(db_session, "https://push.exemple/1") is True
    assert client.abonnements_du_compte(db_session, compte.id) == []
    # Un endpoint déjà retiré (ou jamais connu) : pas d'erreur, juste False.
    assert client.desabonner(db_session, "https://push.exemple/1") is False


def test_route_abonnement(client, db_session):
    _, compte = _ecole_et_compte(db_session)
    reponse = client.post(
        f"/comptes/{compte.id}/push/abonnement",
        json={"endpoint": "https://push.exemple/1", "keys": {"p256dh": "p", "auth": "a"}},
    )
    assert reponse.status_code == 204

    reponse = client.delete("/push/abonnement", params={"endpoint": "https://push.exemple/1"})
    assert reponse.status_code == 204


def test_route_cle_publique(client):
    from app.main import notifications_client

    reponse = client.get("/push/cle-publique")
    assert reponse.status_code == 200
    attendu = notifications_client.cle_publique if notifications_client.actif else None
    assert reponse.json() == {"cle_publique": attendu}


def test_envoyer_a_compte_appelle_webpush_par_abonnement(db_session, monkeypatch):
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    client.cle_privee = "cle-privee-factice"
    client.cle_publique = "cle-publique-factice"
    client.actif = True
    client.abonner(db_session, compte.id, "https://push.exemple/1", "p256dh-1", "auth-1")
    client.abonner(db_session, compte.id, "https://push.exemple/2", "p256dh-2", "auth-2")

    appels = []
    monkeypatch.setattr(
        "notifications.notifications.webpush",
        lambda **kwargs: appels.append(kwargs),
    )

    client.envoyer_a_compte(db_session, compte.id, "Julia Dho", "Bonjour !")

    assert len(appels) == 2
    endpoints_appeles = {a["subscription_info"]["endpoint"] for a in appels}
    assert endpoints_appeles == {"https://push.exemple/1", "https://push.exemple/2"}
    assert '"title": "Julia Dho"' in appels[0]["data"]
    assert '"body": "Bonjour !"' in appels[0]["data"]


def test_envoyer_a_compte_supprime_abonnement_expire(db_session, monkeypatch):
    """410 Gone (ou 404) : l'abonné a désactivé les notifications côté
    navigateur, ou changé d'appareil — l'abonnement ne servira plus jamais,
    on le retire plutôt que de continuer à réessayer à chaque message."""
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    client.cle_privee = "cle-privee-factice"
    client.actif = True
    client.abonner(db_session, compte.id, "https://push.exemple/perime", "p", "a")

    def _webpush_perime(**kwargs):
        raise WebPushException("Gone", response=SimpleNamespace(status_code=410))

    monkeypatch.setattr("notifications.notifications.webpush", _webpush_perime)

    client.envoyer_a_compte(db_session, compte.id, "Titre", "Corps")

    assert client.abonnements_du_compte(db_session, compte.id) == []


def test_envoyer_a_compte_ne_leve_pas_si_echec_non_expire(db_session, monkeypatch):
    """Un échec qui n'est ni 404 ni 410 (ex. service de push temporairement
    en panne) : journalisé, jamais remonté à l'appelant — envoyer un
    message ne doit jamais planter parce qu'une notification échoue."""
    _, compte = _ecole_et_compte(db_session)
    client = Notifications()
    client.cle_privee = "cle-privee-factice"
    client.actif = True
    client.abonner(db_session, compte.id, "https://push.exemple/1", "p", "a")

    def _webpush_en_panne(**kwargs):
        raise WebPushException("Erreur serveur", response=SimpleNamespace(status_code=503))

    monkeypatch.setattr("notifications.notifications.webpush", _webpush_en_panne)

    client.envoyer_a_compte(db_session, compte.id, "Titre", "Corps")  # ne doit pas lever

    # Pas 410/404 : l'abonnement reste (on retentera au prochain message).
    assert len(client.abonnements_du_compte(db_session, compte.id)) == 1


def test_envoyer_message_notifie_les_autres_membres_pas_l_expediteur(client, db_session, monkeypatch):
    from app.main import notifications_client

    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie-Laure"
    )
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Eveil")
    CoursService().inscrire_eleve(db_session, cours.id, eleve.id)
    CoursService().ajouter_professeur(db_session, cours.id, prof.id)

    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    appels = []
    monkeypatch.setattr(
        notifications_client, "envoyer_a_compte", lambda db, compte_id, titre, corps: appels.append(compte_id)
    )

    client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Bonjour à tous !"},
    )

    assert appels == [eleve.id]  # ni l'admin (pas membre), ni le prof (expéditeur)
