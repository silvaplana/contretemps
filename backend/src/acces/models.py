"""Tables de l'accès par mot de passe (voir spec/SPEC.md §2.2 et §6.3ter).

`Utilisateur` : une ligne par ADRESSE EMAIL, toutes écoles et saisons
confondues — pas une personne. C'est elle qui porte le mot de passe (haché)
et le suivi de l'invitation ; les fiches (`comptes`) s'y rattachent par leur
email, comparé en minuscules. Les profils d'une même famille (même email)
partagent donc un seul mot de passe, qui survit à la recopie des fiches à
chaque saison.

`LienAcces` : liens d'invitation et de réinitialisation, à usage unique.
Seule l'empreinte du jeton est stockée : une copie de la base ne permet pas
d'utiliser un lien.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db import Base

INVITATION = "invitation"
REINITIALISATION = "reinitialisation"


def maintenant() -> datetime:
    """UTC sans fuseau : c'est ainsi que SQLite relit un DateTime, et les
    dates d'expiration doivent se comparer entre elles."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Toujours en minuscules, sans espaces autour (voir acces.py :
    # normaliser_email).
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # scrypt (securite/mots_de_passe.py) ; vide tant que l'accès n'est pas activé.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Suivi de l'invitation (§2.2), une date par étape atteinte.
    invite_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    invitation_consultee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    profil_finalise_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    appli_installee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=maintenant)


class LienAcces(Base):
    __tablename__ = "liens_acces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateurs.id"), nullable=False, index=True)
    # INVITATION | REINITIALISATION
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    jeton_hache: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expire_le: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    utilise_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # École qui invite (nom affiché dans le mail et sur l'écran d'activation).
    ecole_id: Mapped[int | None] = mapped_column(ForeignKey("ecoles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=maintenant)
