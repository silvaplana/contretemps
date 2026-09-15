"""Table `ecoles` (voir spec/SPEC.md §6.1). Juste la forme des données —
la logique (création avec ses codes par défaut, etc.) vit dans ecoles.py.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
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

    # Sauvegarde programmée (Admin > École > menu > "Programmer sauvegarde
    # École") — EN BASE, pas en localStorage : décision utilisateur
    # explicite, tous les admins sur tous les appareils doivent voir/
    # modifier le même réglage unique (voir sauvegarde_worker.py, qui lit
    # ces colonnes pour savoir quand déclencher une sauvegarde côté
    # serveur).
    sauvegarde_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'jour' | 'semaine' | 'mois'.
    sauvegarde_periodicite: Mapped[str] = mapped_column(String(20), nullable=False, default="semaine")
    # 0=lundi .. 6=dimanche — utilisé seulement si periodicite='semaine'
    # (voir sauvegarde_worker.py : ignoré sinon, 'mois' se cale sur le 1er
    # du mois par simplicité, voir sa docstring).
    sauvegarde_jour_semaine: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sauvegarde_heure: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM"
    # Dernière exécution RÉUSSIE (voir sauvegarde_worker.py) — évite de
    # se redéclencher plusieurs fois dans le même créneau si le worker
    # est relancé (redéploiement...).
    sauvegarde_derniere_execution: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
