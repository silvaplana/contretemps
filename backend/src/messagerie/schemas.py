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
    # Présence (voir connexions.py) — `en_ligne` n'est PAS une colonne de
    # Compte (dérivé du flux SSE réellement ouvert) : receiver.py pose
    # cet attribut à la volée sur l'objet ORM avant sérialisation, voir
    # _sortie_conversation. `derniere_activite_le`, lui, EST une vraie
    # colonne, peuplée normalement par `from_attributes`.
    en_ligne: bool = False
    derniere_activite_le: dt.datetime | None = None

    model_config = {"from_attributes": True}


class ConversationSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str | None = None
    # Nom RÉSOLU d'un groupe (voir conversations.py: nom_groupe_affiche) —
    # `nom` peut être vide en base pour une conversation automatique de
    # cours ; celui-ci, lui, est toujours le nom à afficher, calculé côté
    # serveur (jamais côté client, qui peut avoir une liste de cours pas
    # encore à jour — bug signalé, demande utilisateur du 2026-09-19).
    # None pour une conversation individuelle : son nom dépend du viewer,
    # résolu côté client (voir frontend/src/api/messages.js: nomAffiche).
    nom_affiche: str | None = None
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
    # 'app' (défaut) | 'email' | 'whatsapp' — voir messages.py: envoyer()
    # pour la nuance sur 'whatsapp' (intention seulement, pas un vrai envoi).
    canal: str = "app"
    # Généré côté navigateur avant l'envoi — voir messages.py: envoyer()
    # et frontend/src/utils/messageOutbox.js (idempotence des renvois).
    client_id: str | None = None


class FrappeEntree(BaseModel):
    compte_id: int


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
    client_id: str | None = None
    deliveries: list[DeliverySortie] = []


class StatutModification(BaseModel):
    statut: str  # 'recu' | 'lu'


class RelanceDemande(BaseModel):
    delai_minutes: int = 15
