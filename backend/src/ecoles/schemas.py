"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py). Sépare "ce que l'API expose" de "ce qui est stocké".
"""

from datetime import datetime

from pydantic import BaseModel


class EcoleCreation(BaseModel):
    nom: str
    code_postal: str
    # Optionnels : si absents, ecoles.py propose les valeurs par défaut
    # `ADMIN_ECOLE_ANNEE` etc. (voir spec §2.3).
    code_acces_admin: str | None = None
    code_acces_prof: str | None = None
    code_acces_eleve: str | None = None


class EcoleModification(BaseModel):
    nom: str | None = None
    code_postal: str | None = None
    code_acces_admin: str | None = None
    code_acces_prof: str | None = None
    code_acces_eleve: str | None = None


class EcoleSortie(BaseModel):
    id: int
    nom: str
    code_postal: str
    code_acces_admin: str
    code_acces_prof: str
    code_acces_eleve: str
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
