"""Table `ecoles` (voir spec/SPEC.md §6.1). Juste la forme des données —
la logique (création avec ses codes par défaut, etc.) vit dans ecoles.py.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ecole(Base):
    """Un tenant. Le nom seul n'est pas unique : deux écoles peuvent
    partager le même nom (ex. deux associations "Contretemps" dans des
    villes différentes) — c'est le couple (nom, code_postal) qui l'est.
    """

    __tablename__ = "ecoles"
    __table_args__ = (UniqueConstraint("nom", "code_postal", name="uq_ecole_nom_code_postal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    code_postal: Mapped[str] = mapped_column(String(10), nullable=False)
    # Codes d'accès : texte libre, sans contrainte de format (voir §6.1) —
    # une valeur par défaut est proposée à la création, éditable ensuite.
    code_acces_admin: Mapped[str] = mapped_column(String(50), nullable=False)
    code_acces_prof: Mapped[str] = mapped_column(String(50), nullable=False)
    code_acces_eleve: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
