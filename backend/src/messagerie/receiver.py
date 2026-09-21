"""Routes REST de la messagerie — reçoit les requêtes HTTP, délègue tout
à Conversations/Messages (voir conversations.py/messages.py), ne fait
aucun calcul métier ici à part fusionner les sorties JSON.
"""

import asyncio
import json

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from notifications import Notifications

from .connexions import Connexions
from .conversations import Conversations
from .evenements import Evenements
from .frappe import Frappe
from .messages import Messages
from .schemas import (
    ConversationCreation,
    ConversationModification,
    ConversationSortie,
    FrappeEntree,
    MembreEntree,
    MessageCreation,
    MessageSortie,
    RelanceDemande,
    StatutModification,
)

# Entre deux vrais événements, un commentaire SSE (ligne commençant par
# ":", ignorée par EventSource côté navigateur) toutes les 20s — sans ça,
# une connexion "silencieuse" trop longtemps peut être coupée par un
# proxy intermédiaire (Caddy, voir frontend/Caddyfile) qui la croit mort,
# et le navigateur ne détecterait la coupure qu'au prochain vrai essai.
DELAI_PING_SECONDES = 20


class MessagerieReceiver:
    def __init__(
        self,
        conversations: Conversations,
        messages: Messages,
        evenements: Evenements,
        connexions: Connexions,
        frappe: Frappe,
        notifications: Notifications,
        app: FastAPI,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.evenements = evenements
        self.connexions = connexions
        self.frappe = frappe
        self.notifications = notifications
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/conversations", response_model=list[ConversationSortie])(self.lister)
        self.app.post(
            "/conversations",
            response_model=ConversationSortie,
            status_code=201,
            dependencies=[Depends(self._admin_ecole)],
        )(self.creer)
        self.app.post("/dm", response_model=ConversationSortie, status_code=201)(
            self.creer_ou_obtenir_dm
        )
        self.app.get("/conversations/{conversation_id}", response_model=ConversationSortie)(
            self.obtenir
        )
        self.app.put(
            "/conversations/{conversation_id}", response_model=ConversationSortie, dependencies=[Depends(self._admin_de_la_conversation)]
        )(self.renommer)
        self.app.delete("/conversations/{conversation_id}", status_code=204, dependencies=[Depends(self._admin_de_la_conversation)])(
            self.supprimer
        )

        self.app.post("/conversations/{conversation_id}/membres", status_code=204, dependencies=[Depends(self._admin_de_la_conversation)])(
            self.ajouter_membre
        )
        self.app.delete(
            "/conversations/{conversation_id}/membres/{membre_type}/{membre_id}",
            status_code=204,
            dependencies=[Depends(self._admin_de_la_conversation)],
        )(self.retirer_membre)

        self.app.get(
            "/conversations/{conversation_id}/messages", response_model=list[MessageSortie]
        )(self.lister_messages)
        self.app.post(
            "/conversations/{conversation_id}/messages",
            response_model=MessageSortie,
            status_code=201,
        )(self.envoyer_message)

        self.app.put(
            "/messages/{message_id}/deliveries/{destinataire_id}", status_code=204
        )(self.modifier_statut)
        self.app.post(
            "/messages/{message_id}/deliveries/{destinataire_id}/mail", status_code=204
        )(self.envoyer_par_mail)
        self.app.post("/messagerie/relancer", status_code=200)(self.relancer)

        # "En train d'écrire" (§5.5) : signalé par le client toutes les
        # ~3s pendant la frappe (voir ConversationThreadScreen.jsx), pas
        # de réponse à attendre.
        self.app.post("/conversations/{conversation_id}/ecrit", status_code=204)(
            self.signaler_frappe
        )

        self.app.post(
            "/conversations/{conversation_id}/whatsapp", response_model=ConversationSortie, dependencies=[Depends(self._admin_de_la_conversation)]
        )(self.creer_groupe_whatsapp)

        # SSE (§5.5) : un flux par compte connecté, ouvert dès le login
        # (voir App.jsx) — pas de response_model (StreamingResponse, pas
        # du JSON classique).
        self.app.get("/comptes/{compte_id}/messagerie/evenements")(self.flux_evenements)

    def _sortie_conversation(self, db: Session, conversation) -> dict:
        membres = self.conversations.membres_resolus(db, conversation.id)
        # `en_ligne` n'est pas une colonne (voir schemas.py: CompteResume)
        # — posé à la volée sur chaque objet ORM, lu par la sérialisation
        # Pydantic (from_attributes) juste après.
        for membre in membres:
            membre.en_ligne = self.evenements.est_en_ligne(membre.id)
        return {
            "id": conversation.id,
            "ecole_id": conversation.ecole_id,
            "nom": conversation.nom,
            "nom_affiche": (
                self.conversations.nom_groupe_affiche(db, conversation)
                if conversation.type == "groupe"
                else None
            ),
            "type": conversation.type,
            "membres": membres,
            "blocs": self.conversations.blocs(db, conversation.id),
            "whatsapp_statut": conversation.whatsapp_statut,
            "whatsapp_groupe_id": conversation.whatsapp_groupe_id,
        }

    def signaler_frappe(
        self, conversation_id: int, donnees: FrappeEntree, db: Session = Depends(get_db)
    ):
        if not self.frappe.doit_publier(conversation_id, donnees.compte_id):
            return
        for membre in self.conversations.membres_resolus(db, conversation_id):
            if membre.id != donnees.compte_id:
                self.evenements.publier(
                    membre.id,
                    {
                        "type": "ecrit",
                        "conversation_id": conversation_id,
                        "compte_id": donnees.compte_id,
                    },
                )

    def lister(self, ecole_id: int, compte_id: int | None = None, db: Session = Depends(get_db)):
        if compte_id is not None:
            convs = self.conversations.lister_du_compte(db, ecole_id, compte_id)
        else:
            convs = self.conversations.lister_ecole(db, ecole_id)
        return [self._sortie_conversation(db, c) for c in convs]


    # --- RBAC (spec §2.4) : l'école que touche chaque route protégée, la
    # règle elle-même étant dans comptes/rbac.py. ---

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _admin_de_la_conversation(
        self,
        conversation_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ) -> None:
        conversation = self.conversations.get(db, conversation_id)
        rbac.require_admin(appelant, conversation.ecole_id if conversation else None)

    def creer(self, ecole_id: int, donnees: ConversationCreation, db: Session = Depends(get_db)):
        membres = [(m.membre_type, m.membre_id) for m in donnees.membres]
        conversation = self.conversations.create_groupe(db, ecole_id, donnees.nom, membres)
        if membres:
            self._publier_conversation_maj(db, conversation.id)
        return self._sortie_conversation(db, conversation)

    def creer_ou_obtenir_dm(
        self, ecole_id: int, compte_a_id: int, compte_b_id: int, db: Session = Depends(get_db)
    ):
        conversation = self.conversations.create_ou_obtenir_dm(
            db, ecole_id, compte_a_id, compte_b_id
        )
        return self._sortie_conversation(db, conversation)

    def obtenir(self, conversation_id: int, db: Session = Depends(get_db)):
        conversation = self.conversations.get(db, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return self._sortie_conversation(db, conversation)

    def renommer(
        self,
        conversation_id: int,
        donnees: ConversationModification,
        db: Session = Depends(get_db),
    ):
        conversation = self.conversations.renommer(db, conversation_id, donnees.nom)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        self._publier_conversation_maj(db, conversation_id)
        return self._sortie_conversation(db, conversation)

    def supprimer(self, conversation_id: int, db: Session = Depends(get_db)):
        # Capturé AVANT suppression : après coup, plus moyen de savoir qui
        # prévenir (voir _publier_conversation_supprimee ci-dessous).
        membres = self.conversations.membres_resolus(db, conversation_id)
        if not self.conversations.delete(db, conversation_id):
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        self._publier_conversation_supprimee([m.id for m in membres], conversation_id)

    def ajouter_membre(
        self, conversation_id: int, donnees: MembreEntree, db: Session = Depends(get_db)
    ):
        self.conversations.ajouter_membre(
            db, conversation_id, donnees.membre_type, donnees.membre_id
        )
        self._publier_conversation_maj(db, conversation_id)

    def retirer_membre(
        self, conversation_id: int, membre_type: str, membre_id: int, db: Session = Depends(get_db)
    ):
        # Capturé AVANT retrait : un membre retiré (directement, ou via
        # un bloc "cours" qui le couvrait) n'apparaît plus dans
        # membres_resolus APRÈS — plus moyen de le retrouver pour le
        # prévenir que CETTE conversation a disparu de chez lui (voir
        # _publier_conversation_supprimee), distinct des membres qui
        # restent (eux reçoivent _publier_conversation_maj, leur liste de
        # personnes a juste changé).
        avant = {m.id for m in self.conversations.membres_resolus(db, conversation_id)}
        self.conversations.retirer_membre(db, conversation_id, membre_type, membre_id)
        apres = {m.id for m in self.conversations.membres_resolus(db, conversation_id)}
        self._publier_conversation_supprimee(list(avant - apres), conversation_id)
        self._publier_conversation_maj(db, conversation_id)

    def _publier_conversation_maj(self, db: Session, conversation_id: int) -> None:
        """Prévient CHAQUE membre ACTUEL de la conversation (SSE) que sa
        composition/son nom a changé — surtout utile pour celui/ceux qui
        vien(nen)t d'être ajouté(s) : sans ça, un groupe tout juste créé
        (voir Messagerie : "Nouveau groupe") n'apparaissait chez eux
        qu'au prochain rechargement complet — même bug de fond que pour
        un DM tout juste créé (voir frontend/src/App.jsx : onMessage,
        obtenirConversation). Le client re-télécharge la conversation en
        entier (voir obtenirConversation) au lieu d'essayer de
        reconstruire la différence lui-même à partir de cet événement."""
        for membre in self.conversations.membres_resolus(db, conversation_id):
            self.evenements.publier(
                membre.id, {"type": "conversation_maj", "conversation_id": conversation_id}
            )

    def _publier_conversation_supprimee(self, compte_ids: list[int], conversation_id: int) -> None:
        """Distinct de _publier_conversation_maj ci-dessus : ici, le
        compte visé n'est PLUS membre (conversation supprimée pour de
        bon, ou lui spécifiquement retiré) — le client doit la retirer
        de sa liste locale, pas essayer de la re-télécharger (il n'y a
        plus accès, voir api/messages.js: obtenirConversation → 404)."""
        for compte_id in compte_ids:
            self.evenements.publier(
                compte_id, {"type": "conversation_supprimee", "conversation_id": conversation_id}
            )

    def lister_messages(self, conversation_id: int, db: Session = Depends(get_db)):
        return [
            self._sortie_message(db, m)
            for m in self.messages.messages_de_la_conversation(db, conversation_id)
        ]

    def _sortie_message(self, db: Session, message) -> dict:
        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "expediteur_id": message.expediteur_id,
            "contenu": message.contenu,
            "created_at": message.created_at,
            "client_id": message.client_id,
            "deliveries": self.messages.deliveries_du_message(db, message.id),
        }

    def envoyer_message(
        self, conversation_id: int, donnees: MessageCreation, db: Session = Depends(get_db)
    ):
        message, nouveau = self.messages.envoyer(
            db,
            conversation_id,
            donnees.expediteur_id,
            donnees.contenu,
            donnees.canal,
            donnees.client_id,
        )
        sortie = self._sortie_message(db, message)
        # Un renvoi idempotent (`nouveau=False`, voir messages.py: envoyer)
        # ne republie RIEN — sinon un simple retry réseau côté client
        # déclencherait une 2e notification push/SSE pour un message déjà
        # livré la 1re fois.
        if nouveau:
            self._publier_message(db, conversation_id, sortie)
        return sortie

    def _publier_message(self, db: Session, conversation_id: int, sortie: dict) -> None:
        """Pousse le nouveau message sur le flux SSE de CHAQUE membre de
        la conversation (voir evenements.py) — y compris l'expéditeur
        (pour qu'un autre onglet/appareil du même compte se resynchronise
        aussi) — ET une vraie notification push (voir notifications.py) à
        chaque AUTRE membre (jamais à l'expéditeur : il sait déjà qu'il
        vient d'envoyer ce message), qui elle atteint même un appareil
        dont l'appli/l'onglet est fermé (ce que le SSE ne peut pas faire)."""
        membres = self.conversations.membres_resolus(db, conversation_id)
        # `mode="json"` : sérialise created_at (datetime) en texte —
        # sinon json.dumps plus bas plante (TypeError: not serializable).
        evenement_message = MessageSortie.model_validate(sortie).model_dump(mode="json")
        expediteur = next((m for m in membres if m.id == sortie["expediteur_id"]), None)
        titre = f"{expediteur.prenom} {expediteur.nom}" if expediteur else "Nouveau message"
        for membre in membres:
            self.evenements.publier(
                membre.id,
                {"type": "message", "conversation_id": conversation_id, "message": evenement_message},
            )
            if membre.id != sortie["expediteur_id"]:
                self.notifications.envoyer_a_compte(db, membre.id, titre, sortie["contenu"])

    def modifier_statut(
        self,
        message_id: int,
        destinataire_id: int,
        donnees: StatutModification,
        db: Session = Depends(get_db),
    ):
        if donnees.statut == "lu":
            delivery = self.messages.marquer_lu(db, message_id, destinataire_id)
        else:
            delivery = self.messages.marquer_recu(db, message_id, destinataire_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Livraison introuvable")
        self._publier_statut_message(db, message_id)

    def _publier_statut_message(self, db: Session, message_id: int) -> None:
        """Prévient l'EXPÉDITEUR (SSE) qu'une livraison de ce message a
        changé (reçu/lu) — bug signalé : sans ça, la coche ne passait au
        bleu ("lu") que si l'expéditeur fermait et rouvrait le fil (le
        seul moment où listerAvecMessages le refetch vraiment), jamais en
        direct pendant que le destinataire lisait le message."""
        message = self.messages.get(db, message_id)
        if message is None:
            return
        sortie = self._sortie_message(db, message)
        evenement_message = MessageSortie.model_validate(sortie).model_dump(mode="json")
        self.evenements.publier(
            message.expediteur_id,
            {
                "type": "message_statut",
                "conversation_id": message.conversation_id,
                "message": evenement_message,
            },
        )

    def envoyer_par_mail(self, message_id: int, destinataire_id: int, db: Session = Depends(get_db)):
        delivery = self.messages.envoyer_par_mail(db, message_id, destinataire_id)
        if delivery is None:
            raise HTTPException(status_code=404, detail="Livraison introuvable")

    def relancer(self, donnees: RelanceDemande, db: Session = Depends(get_db)):
        relancees = self.messages.relancer_messages_non_lus(db, donnees.delai_minutes)
        return {"relancees": len(relancees)}

    def creer_groupe_whatsapp(self, conversation_id: int, db: Session = Depends(get_db)):
        conversation = self.conversations.creer_groupe_whatsapp(db, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        return self._sortie_conversation(db, conversation)

    def flux_evenements(self, compte_id: int) -> StreamingResponse:
        return StreamingResponse(
            self._generateur_evenements(compte_id), media_type="text/event-stream"
        )

    async def _generateur_evenements(self, compte_id: int):
        # "1re connexion" = ce compte n'avait encore AUCUN flux ouvert —
        # sert à ne prévenir ses correspondants qu'une fois, pas à chaque
        # onglet/appareil supplémentaire connecté en même temps (voir
        # connexions.py).
        premiere_connexion = not self.evenements.est_en_ligne(compte_id)
        queue = self.evenements.abonner(compte_id)
        if premiere_connexion:
            self._avec_session(self.connexions.entree, compte_id)
        try:
            # Un premier commentaire tout de suite : certains proxies/
            # navigateurs attendent le premier octet avant de considérer
            # la connexion "ouverte" (voir EventSource : onopen).
            yield ": connecte\n\n"
            while True:
                try:
                    evenement = await asyncio.wait_for(queue.get(), timeout=DELAI_PING_SECONDES)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(evenement)}\n\n"
        finally:
            # Atteint quand le client ferme la connexion (l'ASGI annule
            # ce générateur, voir Starlette : StreamingResponse) — sans
            # ce désabonnement, `Evenements` garderait une queue morte
            # pour toujours (fuite mémoire lente à chaque reconnexion).
            self.evenements.desabonner(compte_id, queue)
            if not self.evenements.est_en_ligne(compte_id):
                self._avec_session(self.connexions.sortie, compte_id)

    def _avec_session(self, methode, compte_id: int) -> None:
        """`entree`/`sortie` ci-dessus ont besoin d'une session DB, mais
        ce générateur (async, tourne DIRECTEMENT sur la boucle asyncio —
        pas dans un threadpool comme les routes sync du reste de ce
        fichier, voir evenements.py) n'en reçoit pas via Depends(get_db) :
        en tenir une ouverte pour toute la durée d'un flux SSE qui peut
        vivre des heures serait pire (connexion SQLite bloquée). Une
        session courte, ouverte puis refermée juste pour cet appel."""
        db = SessionLocal()
        try:
            methode(db, compte_id)
        finally:
            db.close()
