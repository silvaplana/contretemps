"""Logique métier des conversations — création, renommage, gestion des
membres (Admin > Conversations). Voir spec/SPEC.md §6.9.

`messages.py` dépend de ce fichier (résolution des membres pour savoir à
qui envoyer) — jamais l'inverse (voir backend-architecture côté mémoire
projet).
"""

from __future__ import annotations

from comptes import Compte, Comptes
from cours import CoursService
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Conversation, ConversationMembre


class Conversations:
    def __init__(self, comptes: Comptes, cours: CoursService) -> None:
        self.comptes = comptes
        self.cours = cours

    def get(self, db: Session, conversation_id: int) -> Conversation | None:
        return db.get(Conversation, conversation_id)

    def lister_ecole(self, db: Session, ecole_id: int) -> list[Conversation]:
        """Admin > Conversations : toutes les conversations de l'école."""
        return list(db.scalars(select(Conversation).where(Conversation.ecole_id == ecole_id)))

    def lister_du_compte(self, db: Session, ecole_id: int, compte_id: int) -> list[Conversation]:
        """Écran Messagerie : seulement les conversations dont ce compte
        est (directement ou via un cours) membre."""
        return [
            c
            for c in self.lister_ecole(db, ecole_id)
            if any(m.id == compte_id for m in self.membres_resolus(db, c.id))
        ]

    def create_groupe(
        self,
        db: Session,
        ecole_id: int,
        nom: str | None,
        membres: list[tuple[str, int]],
    ) -> Conversation:
        conversation = Conversation(ecole_id=ecole_id, nom=nom, type="groupe")
        db.add(conversation)
        db.flush()
        for membre_type, membre_id in membres:
            db.add(
                ConversationMembre(
                    conversation_id=conversation.id, membre_type=membre_type, membre_id=membre_id
                )
            )
        db.commit()
        db.refresh(conversation)
        return conversation

    def creer_conversation_cours(self, db: Session, ecole_id: int, cours_id: int) -> Conversation:
        """✅ Confirmé (§6.9) : chaque cours a sa propre conversation de
        groupe automatique, `membre_type='cours'` pointant sur lui-même —
        composition (élèves + profs) résolue dynamiquement, jamais figée."""
        return self.create_groupe(db, ecole_id, nom=None, membres=[("cours", cours_id)])

    def create_ou_obtenir_dm(
        self, db: Session, ecole_id: int, compte_a_id: int, compte_b_id: int
    ) -> Conversation:
        """Une conversation individuelle est unique par paire de comptes,
        peu importe d'où elle a été initiée (voir §6.9)."""
        candidates = db.scalars(
            select(Conversation).where(
                Conversation.ecole_id == ecole_id, Conversation.type == "individuelle"
            )
        )
        paire = {compte_a_id, compte_b_id}
        for conversation in candidates:
            membres = db.scalars(
                select(ConversationMembre).where(
                    ConversationMembre.conversation_id == conversation.id,
                    ConversationMembre.membre_type == "compte",
                )
            )
            if {m.membre_id for m in membres} == paire:
                return conversation

        conversation = Conversation(ecole_id=ecole_id, nom=None, type="individuelle")
        db.add(conversation)
        db.flush()
        for membre_id in paire:
            db.add(
                ConversationMembre(
                    conversation_id=conversation.id, membre_type="compte", membre_id=membre_id
                )
            )
        db.commit()
        db.refresh(conversation)
        return conversation

    def renommer(self, db: Session, conversation_id: int, nom: str) -> Conversation | None:
        conversation = self.get(db, conversation_id)
        if conversation is None:
            return None
        conversation.nom = nom
        db.commit()
        db.refresh(conversation)
        return conversation

    def delete(self, db: Session, conversation_id: int) -> bool:
        conversation = self.get(db, conversation_id)
        if conversation is None:
            return False
        for membre in self._membres_bruts(db, conversation_id):
            db.delete(membre)
        db.delete(conversation)
        db.commit()
        return True

    # --- Membres ---

    def _membres_bruts(self, db: Session, conversation_id: int) -> list[ConversationMembre]:
        return list(
            db.scalars(
                select(ConversationMembre).where(
                    ConversationMembre.conversation_id == conversation_id
                )
            )
        )

    def ajouter_membre(
        self, db: Session, conversation_id: int, membre_type: str, membre_id: int
    ) -> None:
        """Voir §6.9 : membres "spéciaux" ajoutables en plus de la
        composition automatique d'une conversation de cours."""
        exists = any(
            m.membre_type == membre_type and m.membre_id == membre_id
            for m in self._membres_bruts(db, conversation_id)
        )
        if not exists:
            db.add(
                ConversationMembre(
                    conversation_id=conversation_id, membre_type=membre_type, membre_id=membre_id
                )
            )
            db.commit()

    def retirer_membre(
        self, db: Session, conversation_id: int, membre_type: str, membre_id: int
    ) -> None:
        for membre in self._membres_bruts(db, conversation_id):
            if membre.membre_type == membre_type and membre.membre_id == membre_id:
                db.delete(membre)
        db.commit()

    def membres_resolus(self, db: Session, conversation_id: int) -> list[Compte]:
        """'cours' se résout dynamiquement en tous ses élèves ET son/ses
        professeur(s) — pas de liste figée à maintenir (voir §6.9)."""
        resultat: dict[int, Compte] = {}
        for membre in self._membres_bruts(db, conversation_id):
            if membre.membre_type == "compte":
                compte = self.comptes.get(db, membre.membre_id)
                if compte is not None:
                    resultat[compte.id] = compte
            elif membre.membre_type == "cours":
                for compte in (
                    self.cours.eleves_du_cours(db, membre.membre_id)
                    + self.cours.professeurs_du_cours(db, membre.membre_id)
                ):
                    resultat[compte.id] = compte
        return list(resultat.values())
