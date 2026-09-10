"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

import datetime as dt

from pydantic import BaseModel


class MembreEntree(BaseModel):
    membre_type: str  # 'compte' | 'cours'
    membre_id: int

    # Aussi utilisé en sortie (ConversationSortie.blocs, depuis des
    # ConversationMembre ORM — voir receiver.py: blocs()), en plus de
    # l'entrée JSON classique (dict) — les deux marchent avec ce réglage.
    model_config = {"from_attributes": True}


class ConversationCreation(BaseModel):
    nom: str | None = None
    membres: list[MembreEntree] = []


class ConversationModification(BaseModel):
    nom: str


class CompteResume(BaseModel):
    id: int
    nom: str
    prenom: str
    role: str

    model_config = {"from_attributes": True}


class ConversationSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str | None = None
    type: str
    membres: list[CompteResume] = []
    # Composition brute (pas résolue) — pour l'édition côté Admin >
    # Conversations, voir conversations.py: blocs().
    blocs: list[MembreEntree] = []
    # Groupe WhatsApp miroir (voir §6.9) : 'aucun' | 'cree'.
    whatsapp_statut: str = "aucun"
    whatsapp_groupe_id: str | None = None


class MessageCreation(BaseModel):
    expediteur_id: int
    contenu: str
    envoi_volontaire_email: bool = False


class DeliverySortie(BaseModel):
    id: int
    message_id: int
    destinataire_id: int
    canal: str
    statut: str
    envoi_volontaire: bool

    model_config = {"from_attributes": True}


class MessageSortie(BaseModel):
    id: int
    conversation_id: int
    expediteur_id: int
    contenu: str
    created_at: dt.datetime
    deliveries: list[DeliverySortie] = []


class StatutModification(BaseModel):
    statut: str  # 'recu' | 'lu'


class RelanceDemande(BaseModel):
    delai_minutes: int = 15
