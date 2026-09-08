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

    # Autorise Pydantic à lire directement un objet SQLAlchemy (Ecole),
    # pas seulement un dict.
    model_config = {"from_attributes": True}
