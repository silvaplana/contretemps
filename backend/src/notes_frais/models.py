"""Tables du module notes de frais (spec/modules/notes-de-frais.md §10).

Comme le module documents : aucune clé étrangère vers les tables de l'appli
hôte. `org_id` et `*person_id` sont de simples entiers fournis par les ports
(voir ports.py) ; `person_id` reste le même d'une saison à l'autre, donc une
note envoyée en juin se rembourse encore en septembre. Pas de `saison_id` :
ces tables ne sont pas filtrées par saison.

Montants en centimes entiers ; le total d'une note n'est jamais stocké.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _maintenant() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Statuts d'une note (§5).
ENVOYEE = "envoyee"
VALIDEE = "validee"
REFUSEE = "refusee"
REMBOURSEE = "remboursee"
# Machine commune aux dépenses (financier.md §8.3 bis) : envoyée = à valider,
# validée = à payer, préparée, virée (« j'ai fait le virement »), remboursée = payé.
PREPAREE = "preparee"
VIREE = "viree"
STATUTS = (ENVOYEE, VALIDEE, REFUSEE, PREPAREE, VIREE, REMBOURSEE)

# Nature d'une note (financier.md §8.3 bis : une seule structure « dépense »).
FRAIS = "frais"
HONORAIRES = "honoraires"
ACHAT = "achat"
NATURES = (FRAIS, HONORAIRES, ACHAT)
# person_id d'une note d'honoraires dont le prof n'est pas encore reconnu.
PERSONNE_A_CHOISIR = 0


class CategorieFrais(Base):
    __tablename__ = "nf_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    libelle: Mapped[str] = mapped_column(String(60), nullable=False)
    # Numéro du compte de charges du plan comptable dont la catégorie est le
    # reflet (Ports.plan), ou None pour une catégorie libre.
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Une catégorie retirée reste sur les anciennes dépenses.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NoteFrais(Base):
    __tablename__ = "nf_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    titre: Mapped[str] = mapped_column(String(120), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default=ENVOYEE, index=True)
    # Abandon de frais (§8) : validée = terminée, pas de virement.
    don: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # RIB recopié à l'envoi : le virement part sur celui-là, même si la
    # personne change le sien ensuite.
    rib_titulaire: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rib_iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    rib_bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    motif_refus: Mapped[str | None] = mapped_column(Text, nullable=True)
    envoyee_le: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_maintenant)
    traitee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    traitee_par: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remboursee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remboursee_par: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nature: Mapped[str] = mapped_column(String(20), nullable=False, default=FRAIS, server_default=FRAIS)
    # Achat : le fournisseur (person_id = le trésorier qui l'a établi).
    supplier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Virements (financier.md §8.3 bis) : préparé pour `payer_id`, envoyé,
    # puis payé quand l'opération `bank_operation_id` est vue sur le compte.
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prepared_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transfer_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transfer_sent_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bank_operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    depenses: Mapped[list["Depense"]] = relationship(back_populates="note", order_by="Depense.date")


class Depense(Base):
    __tablename__ = "nf_depenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    montant_centimes: Mapped[int] = mapped_column(Integer, nullable=False)
    categorie_id: Mapped[int | None] = mapped_column(ForeignKey("nf_categories.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Pré-remplie par la lecture du ticket (§4.2).
    lue_par_ia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Null : « À envoyer » (§4.1).
    note_id: Mapped[int | None] = mapped_column(ForeignKey("nf_notes.id"), nullable=True, index=True)
    creee_le: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_maintenant)

    note: Mapped[NoteFrais | None] = relationship(back_populates="depenses")
    categorie: Mapped[CategorieFrais | None] = relationship()
    pieces: Mapped[list["PieceJustificative"]] = relationship(
        back_populates="depense", order_by="PieceJustificative.ordre", cascade="all, delete-orphan"
    )


class PieceJustificative(Base):
    """Photo ou PDF d'un ticket : sur le disque (stockage.py) tant que la
    dépense n'est pas envoyée, puis dans Docs (`doc_node_id`, chemin vide)."""

    __tablename__ = "nf_pieces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    depense_id: Mapped[int] = mapped_column(ForeignKey("nf_depenses.id"), nullable=False, index=True)
    # Chemin relatif au dossier de l'organisation (stockage.py).
    chemin: Mapped[str] = mapped_column(String(500), nullable=False)
    type_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    taille: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ordre: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    doc_node_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    depense: Mapped[Depense] = relationship(back_populates="pieces")


class Rib(Base):
    """RIB facultatif d'une personne (§4.5) : vu d'elle et des trésoriers."""

    __tablename__ = "nf_ribs"
    __table_args__ = (UniqueConstraint("org_id", "person_id", name="uq_nf_rib_personne"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
    titulaire: Mapped[str | None] = mapped_column(String(120), nullable=True)
    iban: Mapped[str] = mapped_column(String(34), nullable=False)
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    modifie_le: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_maintenant, onupdate=_maintenant)


class Payer(Base):
    """Réglage « Qui paie » (financier.md §8.3 bis) : les personnes à qui on
    peut faire payer un virement. Aucune ligne : les trésoriers."""

    __tablename__ = "nf_payers"
    __table_args__ = (UniqueConstraint("org_id", "person_id", name="uq_nf_payer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(Integer, nullable=False)
