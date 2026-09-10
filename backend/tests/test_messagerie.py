"""Tests du module messagerie (voir spec/SPEC.md §6.9)."""

import datetime as dt

from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles


def _setup(db_session):
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
    return ecole, admin, prof, eleve, cours


def test_conversation_de_cours_resout_dynamiquement_ses_membres(client, db_session):
    """Voir §6.9 : membre_type='cours' se résout en tous ses élèves ET
    professeur(s), pas de liste figée."""
    ecole, _, prof, eleve, cours = _setup(db_session)
    reponse = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    )
    assert reponse.status_code == 201
    conversation = reponse.json()
    membre_ids = {m["id"] for m in conversation["membres"]}
    assert membre_ids == {prof.id, eleve.id}

    # Un nouvel élève inscrit au cours apparaît automatiquement.
    nouvel_eleve = Comptes().create(
        db_session, ecole_id=ecole.id, role="eleve", nom="Thomas", prenom="Simon"
    )
    CoursService().inscrire_eleve(db_session, cours.id, nouvel_eleve.id)
    reponse = client.get(f"/conversations/{conversation['id']}")
    membre_ids = {m["id"] for m in reponse.json()["membres"]}
    assert nouvel_eleve.id in membre_ids


def test_conversation_introuvable(client):
    assert client.get("/conversations/999").status_code == 404
    assert client.put("/conversations/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/conversations/999").status_code == 404


def test_dm_unique_par_paire(client, db_session):
    """Une conversation individuelle est unique par paire de comptes,
    peu importe d'où elle a été initiée (voir §6.9)."""
    ecole, admin, _, eleve, _ = _setup(db_session)
    r1 = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": admin.id, "compte_b_id": eleve.id}
    )
    r2 = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": eleve.id, "compte_b_id": admin.id}
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["type"] == "individuelle"


def test_ajouter_et_retirer_membre_special(client, db_session):
    """Voir §6.9 : une conversation de cours reste éditable, on peut y
    ajouter des membres spéciaux en plus de sa composition automatique."""
    ecole, admin, _, _, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    assert (
        client.post(
            f"/conversations/{conversation['id']}/membres",
            json={"membre_type": "compte", "membre_id": admin.id},
        ).status_code
        == 204
    )
    membre_ids = {
        m["id"] for m in client.get(f"/conversations/{conversation['id']}").json()["membres"]
    }
    assert admin.id in membre_ids

    assert (
        client.delete(
            f"/conversations/{conversation['id']}/membres/compte/{admin.id}"
        ).status_code
        == 204
    )
    membre_ids = {
        m["id"] for m in client.get(f"/conversations/{conversation['id']}").json()["membres"]
    }
    assert admin.id not in membre_ids


def test_lister_conversations_dun_compte(client, db_session):
    """Écran Messagerie : uniquement les conversations dont ce compte
    est membre (directement ou via un cours)."""
    ecole, admin, prof, eleve, cours = _setup(db_session)
    client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    )
    client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "compte", "membre_id": admin.id}]},
    )

    reponse = client.get("/conversations", params={"ecole_id": ecole.id, "compte_id": prof.id})
    assert len(reponse.json()) == 1  # seulement la conversation du cours

    reponse = client.get("/conversations", params={"ecole_id": ecole.id})
    assert len(reponse.json()) == 2  # Admin > Conversations : toutes


def test_envoyer_message_cree_une_delivery_par_destinataire(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    reponse = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Bonjour à tous !"},
    )
    assert reponse.status_code == 201
    message = reponse.json()
    # L'expéditeur (prof) n'a pas de delivery à lui-même — seul l'élève reste.
    assert [d["destinataire_id"] for d in message["deliveries"]] == [eleve.id]
    assert message["deliveries"][0]["canal"] == "app"
    assert message["deliveries"][0]["statut"] == "envoye"


def test_envoi_volontaire_email_immediat(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": prof.id, "compte_b_id": eleve.id}
    ).json()

    reponse = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Merci de confirmer", "canal": "email"},
    )
    delivery = reponse.json()["deliveries"][0]
    assert delivery["canal"] == "email"
    assert delivery["envoi_volontaire"] is True


def test_marqueur_whatsapp_pas_un_vrai_envoi(client, db_session):
    """Voir spec/SPEC.md §6.9/§8 : canal='whatsapp' n'est qu'un marqueur
    d'intention (case cochée), aucun vrai envoi WhatsApp — juste pour ne
    pas perdre cette intention une fois le message enregistré (signalé :
    rien ne le distinguait avant)."""
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    reponse = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Rappel réunion", "canal": "whatsapp"},
    )
    deliveries = reponse.json()["deliveries"]
    assert deliveries  # au moins l'élève du cours
    for delivery in deliveries:
        assert delivery["canal"] == "whatsapp"
        assert delivery["envoi_volontaire"] is True


def test_marquer_lu_et_envoyer_par_mail(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": prof.id, "compte_b_id": eleve.id}
    ).json()
    message = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Salut"},
    ).json()

    assert (
        client.put(
            f"/messages/{message['id']}/deliveries/{eleve.id}", json={"statut": "lu"}
        ).status_code
        == 204
    )
    delivery = client.get(f"/conversations/{conversation['id']}/messages").json()[0]["deliveries"][0]
    assert delivery["statut"] == "lu"

    assert (
        client.put(
            f"/messages/999/deliveries/{eleve.id}", json={"statut": "lu"}
        ).status_code
        == 404
    )

    message2 = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Encore un message"},
    ).json()
    assert (
        client.post(f"/messages/{message2['id']}/deliveries/{eleve.id}/mail").status_code == 204
    )
    delivery = client.get(f"/conversations/{conversation['id']}/messages").json()[1]["deliveries"][0]
    assert delivery["canal"] == "email"
    assert delivery["envoi_volontaire"] is True


def test_groupe_whatsapp_miroir(client, db_session):
    """Voir §6.9 : le "tuyau" WhatsApp — pas de vrai envoi encore (Baileys,
    plus tard), juste le statut stocké sur la conversation."""
    ecole, admin, _, _, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()
    assert conversation["whatsapp_statut"] == "aucun"
    assert conversation["whatsapp_groupe_id"] is None
    assert conversation["blocs"] == [{"membre_type": "cours", "membre_id": cours.id}]

    reponse = client.post(f"/conversations/{conversation['id']}/whatsapp")
    assert reponse.status_code == 200
    miroir = reponse.json()
    assert miroir["whatsapp_statut"] == "cree"
    assert miroir["whatsapp_groupe_id"]

    # Persisté : une relecture le confirme.
    relu = client.get(f"/conversations/{conversation['id']}").json()
    assert relu["whatsapp_statut"] == "cree"

    assert client.post("/conversations/999/whatsapp").status_code == 404


def test_relance_automatique_apres_delai(client, db_session):
    """Voir §5.5 : message non lu après un délai -> email automatique."""
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/dm", params={"ecole_id": ecole.id, "compte_a_id": prof.id, "compte_b_id": eleve.id}
    ).json()
    client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Non lu"},
    )

    # Reconstruit un client Messages directement pour passer un `maintenant`
    # déterministe (pas de scheduler dans ce backend, voir messages.py).
    from comptes import Comptes
    from cours import CoursService
    from messagerie import Conversations, Messages

    messages_client = Messages(Conversations(comptes=Comptes(), cours=CoursService()))
    plus_tard = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=20)
    relancees = messages_client.relancer_messages_non_lus(
        db_session, delai_minutes=15, maintenant=plus_tard
    )
    assert len(relancees) == 1
    assert relancees[0].canal == "email"


def test_envoyer_message_publie_un_evenement_sse_a_chaque_membre(client, db_session):
    """Voir spec/SPEC.md §5.5 et messagerie/evenements.py : un seul flux
    par compte (pas par conversation), qui reçoit tout nouveau message
    le concernant — vérifié ici directement sur le pub/sub (pas la vraie
    connexion HTTP streaming, hors de portée d'un test synchrone)."""
    from app.main import evenements_client

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    queue_eleve = evenements_client.abonner(eleve.id)
    queue_prof = evenements_client.abonner(prof.id)
    queue_admin_non_membre = evenements_client.abonner(admin.id)
    try:
        client.post(
            f"/conversations/{conversation['id']}/messages",
            json={"expediteur_id": prof.id, "contenu": "Bonjour à tous !"},
        )

        evenement = queue_eleve.get_nowait()
        assert evenement["type"] == "message"
        assert evenement["conversation_id"] == conversation["id"]
        assert evenement["message"]["contenu"] == "Bonjour à tous !"

        # L'expéditeur reçoit aussi l'événement (autre onglet/appareil du
        # même compte à resynchroniser).
        assert queue_prof.get_nowait()["message"]["contenu"] == "Bonjour à tous !"

        # L'admin n'est membre d'aucune des deux conversations : rien
        # sur son flux.
        assert queue_admin_non_membre.empty()
    finally:
        evenements_client.desabonner(eleve.id, queue_eleve)
        evenements_client.desabonner(prof.id, queue_prof)
        evenements_client.desabonner(admin.id, queue_admin_non_membre)
