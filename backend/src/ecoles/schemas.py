"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py). Sépare "ce que l'API expose" de "ce qui est stocké".
"""

from datetime import datetime

from pydantic import BaseModel


class EcoleCreation(BaseModel):
    nom: str
    code_postal: str
    # Adresse web (spec §2.7) : vide = proposée d'après le nom.
    sous_domaine: str | None = None
    ville: str | None = None


class EcoleModification(BaseModel):
    nom: str | None = None
    code_postal: str | None = None
    adresse: str | None = None
    ville: str | None = None
    # Espaces acceptés (« 123 456 789 00012 ») ; 14 chiffres sinon refusé.
    siret: str | None = None
    # Espaces acceptés ; clé de contrôle vérifiée.
    iban: str | None = None


class EcolePublique(BaseModel):
    """Ce que tout le monde peut voir d'une école, sans être connecté
    (GET /ecoles) : son nom et son code postal."""

    id: int
    nom: str
    code_postal: str
    sous_domaine: str | None = None

    model_config = {"from_attributes": True}


class EcoleSortie(BaseModel):
    """Vue complète (réglages de sauvegarde compris) : réservée aux admins
    de l'école (voir receiver.py, RBAC §2.4)."""

    id: int
    nom: str
    code_postal: str
    adresse: str | None = None
    ville: str | None = None
    siret: str | None = None
    iban: str | None = None
    sous_domaine: str | None = None
    created_at: datetime
    sauvegarde_active: bool
    sauvegarde_periodicite: str
    sauvegarde_jour_semaine: int | None
    sauvegarde_heure: str | None
    sauvegarde_derniere_execution: datetime | None

    # Autorise Pydantic à lire directement un objet SQLAlchemy (Ecole),
    # pas seulement un dict.
    model_config = {"from_attributes": True}


class SauvegardeProgrammeeModification(BaseModel):
    """"Programmer sauvegarde École" (Admin > École) — voir
    sauvegarde_worker.py."""

    active: bool
    periodicite: str  # 'jour' | 'semaine' | 'mois'
    jour_semaine: int | None = None  # 0=lundi..6=dimanche, si 'semaine'
    heure: str | None = None  # "HH:MM"


class SauvegardeFichier(BaseModel):
    """Une sauvegarde passée, générée côté serveur par le worker (voir
    "Sauvegarder École" > historique) — juste assez pour lister et
    proposer un téléchargement, pas le contenu lui-même."""

    nom: str
    date: datetime
    taille_octets: int
