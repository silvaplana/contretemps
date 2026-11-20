"""Tables `autoimport_rules` (un import réglé une fois) et `autoimport_seen`
(ce que chaque import a déjà regardé), spec/modules/import-auto-pieces.md §7.
Effacer un import efface ses lignes vues, jamais les pièces créées."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutoImportRule(Base):
    __tablename__ = "autoimport_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, default="Nouvel import")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Saison des pièces créées : seuls les fichiers datés dedans (§3). Nul : toutes.
    season_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # achat, vente, frais, honoraires
    nature: Mapped[str] = mapped_column(String(20), nullable=False, default="achat")
    # docs, drive, mail, helloasso ; `source_ref` : dossier Docs, drive ou boîte.
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="docs")
    source_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    # none, docs, drive
    target_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    target_ref: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    # hourly, daily, weekly, monthly ; `at_time` « HH:MM », heure de Paris.
    frequency: Mapped[str] = mapped_column(String(10), nullable=False, default="daily")
    at_time: Mapped[str] = mapped_column(String(5), nullable=False, default="07:00")
    created_status: Mapped[str] = mapped_column(String(20), nullable=False, default="a_valider")
    # Source boîte mail (§4.1) : mots séparés par des virgules.
    mail_senders: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    mail_words: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    mail_need_amount: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Source HelloAsso (§4.2) : formule de la campagne → compte de produits
    # (catégorie des ventes), dit une fois par la trésorière.
    helloasso_accounts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Formule → part licence en centimes (vers le compte des licences à reverser).
    helloasso_licences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # La personne qui a créé l'import : les pièces sont établies en son nom.
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Ce que le dernier passage a dit (« 1 nouvelle pièce », une erreur…).
    last_message: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class AutoImportSeen(Base):
    __tablename__ = "autoimport_seen"
    __table_args__ = (UniqueConstraint("rule_id", "source_key", name="uq_autoimport_seen"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("autoimport_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    # Chemin du fichier, identifiant du mail ou du versement.
    source_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # La pièce créée ; nul : regardé sans donner de pièce.
    note_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
