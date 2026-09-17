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


def test_renvoi_avec_meme_client_id_ne_cree_pas_de_doublon(client, db_session):
    """Bug signalé : "des fois les messages n'arrivaient pas" — un cas
    réel est la réponse HTTP perdue après que le serveur ait DÉJÀ
    enregistré le message (coupure réseau juste après le commit). Sans
    idempotence, un renvoi crée un doublon ; avec `client_id` (voir
    frontend/src/utils/messageOutbox.js), le 2e envoi renvoie exactement
    le même message, rien n'est recréé."""
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    corps = {"expediteur_id": prof.id, "contenu": "Bonjour !", "client_id": "abc-123"}
    r1 = client.post(f"/conversations/{conversation['id']}/messages", json=corps)
    r2 = client.post(f"/conversations/{conversation['id']}/messages", json=corps)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    messages = client.get(f"/conversations/{conversation['id']}/messages").json()
    assert len(messages) == 1
    assert len(messages[0]["deliveries"]) == 1  # une seule delivery, pas 2


def test_renvoi_avec_meme_client_id_ne_republie_pas_sur_sse(client, db_session):
    """Suite du test précédent : le 2e envoi (idempotent) ne doit RIEN
    republier — sinon un simple retry réseau déclencherait une 2e
    notification pour un message déjà livré la 1re fois."""
    from app.main import evenements_client

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    queue_eleve = evenements_client.abonner(eleve.id)
    try:
        corps = {"expediteur_id": prof.id, "contenu": "Bonjour !", "client_id": "xyz-789"}
        client.post(f"/conversations/{conversation['id']}/messages", json=corps)
        client.post(f"/conversations/{conversation['id']}/messages", json=corps)

        assert queue_eleve.get_nowait()["message"]["contenu"] == "Bonjour !"
        assert queue_eleve.empty()  # rien de plus, le 2e envoi n'a rien republié
    finally:
        evenements_client.desabonner(eleve.id, queue_eleve)


def test_client_id_different_cree_bien_2_messages(client, db_session):
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    r1 = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Un", "client_id": "id-1"},
    )
    r2 = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Deux", "client_id": "id-2"},
    )
    assert r1.json()["id"] != r2.json()["id"]
    assert len(client.get(f"/conversations/{conversation['id']}/messages").json()) == 2


def test_client_id_absent_fonctionne_comme_avant(client, db_session):
    """Rétrocompatibilité : un envoi sans client_id (ancien comportement,
    ou tout appel qui n'en fournit pas) continue de fonctionner
    normalement, sans idempotence — voir models.py: Message.client_id,
    nullable."""
    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    reponse = client.post(
        f"/conversations/{conversation['id']}/messages",
        json={"expediteur_id": prof.id, "contenu": "Bonjour !"},
    )
    assert reponse.status_code == 201
    assert reponse.json()["client_id"] is None


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


def test_conversation_expose_en_ligne_des_membres(client, db_session):
    """Voir messagerie/connexions.py : `en_ligne` reflète le flux SSE
    réellement ouvert au moment de la requête, jamais un flag persisté."""
    from app.main import evenements_client

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()
    membre_eleve = next(m for m in conversation["membres"] if m["id"] == eleve.id)
    assert membre_eleve["en_ligne"] is False

    queue_eleve = evenements_client.abonner(eleve.id)
    try:
        conversation = client.get(f"/conversations/{conversation['id']}").json()
        membre_eleve = next(m for m in conversation["membres"] if m["id"] == eleve.id)
        assert membre_eleve["en_ligne"] is True
    finally:
        evenements_client.desabonner(eleve.id, queue_eleve)


def test_connexions_entree_notifie_les_correspondants(db_session):
    """Voir connexions.py : entrer en ligne prévient tout compte qui
    partage déjà une conversation avec soi (décision utilisateur du
    2026-09-17 : pas restreint à l'équipe pédagogique pour l'instant)."""
    from comptes import Comptes
    from cours import CoursService
    from messagerie import Connexions, Conversations, Evenements

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversations = Conversations(comptes=Comptes(), cours=CoursService())
    conversations.creer_conversation_cours(db_session, ecole.id, cours.id)
    evenements = Evenements()
    connexions = Connexions(comptes=Comptes(), conversations=conversations, evenements=evenements)

    queue_prof = evenements.abonner(prof.id)
    try:
        connexions.entree(db_session, eleve.id)
        assert queue_prof.get_nowait() == {
            "type": "etat_connexion",
            "compte_id": eleve.id,
            "en_ligne": True,
            "derniere_activite_le": None,
        }
    finally:
        evenements.desabonner(prof.id, queue_prof)


def test_connexions_sortie_enregistre_la_derniere_activite_et_notifie(db_session):
    from comptes import Comptes
    from cours import CoursService
    from messagerie import Connexions, Conversations, Evenements

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversations = Conversations(comptes=Comptes(), cours=CoursService())
    conversations.creer_conversation_cours(db_session, ecole.id, cours.id)
    evenements = Evenements()
    connexions = Connexions(comptes=Comptes(), conversations=conversations, evenements=evenements)

    assert eleve.derniere_activite_le is None

    queue_prof = evenements.abonner(prof.id)
    try:
        connexions.sortie(db_session, eleve.id)
        evenement = queue_prof.get_nowait()
        assert evenement["type"] == "etat_connexion"
        assert evenement["en_ligne"] is False
        assert evenement["derniere_activite_le"] is not None
    finally:
        evenements.desabonner(prof.id, queue_prof)

    assert eleve.derniere_activite_le is not None


def test_connexions_ne_notifie_pas_un_compte_sans_conversation_commune(db_session):
    from comptes import Comptes
    from cours import CoursService
    from messagerie import Connexions, Conversations, Evenements

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversations = Conversations(comptes=Comptes(), cours=CoursService())
    conversations.creer_conversation_cours(db_session, ecole.id, cours.id)
    evenements = Evenements()
    connexions = Connexions(comptes=Comptes(), conversations=conversations, evenements=evenements)

    # admin n'est membre d'aucune conversation avec eleve (voir _setup).
    queue_admin = evenements.abonner(admin.id)
    try:
        connexions.entree(db_session, eleve.id)
        assert queue_admin.empty()
    finally:
        evenements.desabonner(admin.id, queue_admin)


def test_frappe_publie_a_tous_les_membres_sauf_lauteur(client, db_session):
    from app.main import evenements_client

    ecole, admin, prof, eleve, cours = _setup(db_session)
    conversation = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"membres": [{"membre_type": "cours", "membre_id": cours.id}]},
    ).json()

    queue_prof = evenements_client.abonner(prof.id)
    queue_eleve = evenements_client.abonner(eleve.id)
    try:
        reponse = client.post(
            f"/conversations/{conversation['id']}/ecrit", json={"compte_id": eleve.id}
        )
        assert reponse.status_code == 204
        assert queue_prof.get_nowait() == {
            "type": "ecrit",
            "conversation_id": conversation["id"],
            "compte_id": eleve.id,
        }
        assert queue_eleve.empty()  # jamais republié à soi-même
    finally:
        evenements_client.desabonner(prof.id, queue_prof)
        evenements_client.desabonner(eleve.id, queue_eleve)


def test_frappe_throttle_les_envois_rapproches():
    from messagerie import Frappe

    frappe = Frappe()
    assert frappe.doit_publier(1, 2) is True
    assert frappe.doit_publier(1, 2) is False  # trop tôt après le précédent
    assert frappe.doit_publier(1, 3) is True  # compte différent : pas throttlé
