"""« Usage ressources et IA de la saison » (Admin > École, spec §5.1.1) :
la place que l'école occupe sur le disque, et ce qu'ont coûté ses
opérations d'IA, par poste.

Les modules qui font appel à une IA (lecture des fiches, détourage d'un
logo...) notent chaque opération par `noter_ia` ; ce module ne sait rien
d'eux au-delà du nom de leur poste.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ecoles.models import Ecole
from saisons import Saison, saison_courante_id
from saisons.portee import saison_demandee, toutes_saisons

from .models import ConsommationIA

# Postes de dépense : clé enregistrée -> libellé affiché.
CATEGORIES_IA = {
    "lecture_fiche": "Lecture des fiches d'inscription",
    "detourage_logo": "Personnalisation : détourage du logo",
    "chat_documents": "Chat documents",
    "lecture_ticket": "Notes de frais : lecture des tickets",
    "bilan_financier": "Financier : analyse des bilans",
    "rapport_financier": "Financier : rapport financier de l’AG",
    "assemblee_generale": "Financier : PowerPoint des assemblées générales",
    "previsionnel": "Financier : prévisionnels",
    "liste_presents": "Assemblée générale : lecture de la liste des présents",
    "regle_tarif": "Tarifs : règles en français",
}

# Postes comptés dans le plafond mensuel de l'assistant (la lecture des
# tickets aussi : spec/modules/notes-de-frais.md §12).
POSTES_PLAFOND = ("chat_documents", "lecture_ticket", "regle_tarif")


def _taille(dossier: Path) -> int:
    """Taille de tout ce que contient `dossier` (0 s'il n'existe pas)."""
    if not dossier.exists():
        return 0
    total = 0
    for fichier in dossier.rglob("*"):
        try:
            if fichier.is_file():
                total += fichier.stat().st_size
        except OSError:
            continue
    return total


class Ressources:
    def __init__(self, dossiers: dict[str, tuple[str, Path]]) -> None:
        """`dossiers` : rubrique de la mémoire -> (libellé, dossier racine,
        dans lequel chaque école a son sous-dossier à son numéro)."""
        self.dossiers = dossiers

    def noter_ia(
        self, db: Session, ecole_id: int, categorie: str, cout_usd: float, detail: str | None = None
    ) -> None:
        db.add(ConsommationIA(ecole_id=ecole_id, categorie=categorie, cout_usd=cout_usd, detail=detail))
        db.commit()

    def cout_categorie(self, db: Session, ecole_id: int, categorie: str) -> float:
        """Total d'un poste sur la saison affichée (filtre de saison automatique)."""
        total = db.scalar(
            select(func.coalesce(func.sum(ConsommationIA.cout_usd), 0.0)).where(
                ConsommationIA.ecole_id == ecole_id, ConsommationIA.categorie == categorie
            )
        )
        return round(float(total or 0.0), 5)

    def cout_du_mois(self, db: Session, ecole_id: int, categorie: str) -> float:
        """Total d'un poste depuis le 1er du mois civil (UTC), toutes saisons
        confondues : c'est ce que compte le plafond de l'assistant."""
        debut = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, day=1, hour=0, minute=0, second=0, microsecond=0)
        with toutes_saisons(db):
            total = db.scalar(
                select(func.coalesce(func.sum(ConsommationIA.cout_usd), 0.0)).where(
                    ConsommationIA.ecole_id == ecole_id,
                    ConsommationIA.categorie == categorie,
                    ConsommationIA.cree_le >= debut,
                )
            )
        return round(float(total or 0.0), 5)

    def plafond_assistant(self, db: Session, ecole_id: int) -> float:
        ecole = db.get(Ecole, ecole_id)
        return float(ecole.assistant_plafond_mensuel_usd) if ecole is not None else 0.0

    def plafond_assistant_atteint(self, db: Session, ecole_id: int) -> bool:
        depense = sum(self.cout_du_mois(db, ecole_id, poste) for poste in POSTES_PLAFOND)
        return depense >= self.plafond_assistant(db, ecole_id)

    def definir_plafond_assistant(self, db: Session, ecole_id: int, plafond_usd: float) -> float:
        ecole = db.get(Ecole, ecole_id)
        if ecole is None:
            raise LookupError(ecole_id)
        ecole.assistant_plafond_mensuel_usd = round(max(0.0, float(plafond_usd)), 2)
        db.commit()
        return ecole.assistant_plafond_mensuel_usd

    def usage(self, db: Session, ecole_id: int) -> dict:
        memoire = [
            {"cle": cle, "libelle": libelle, "octets": _taille(racine / str(ecole_id))}
            for cle, (libelle, racine) in self.dossiers.items()
        ]

        # Saison affichée : le filtre de saison s'applique de lui-même
        # (voir saisons/portee.py).
        lignes = db.execute(
            select(ConsommationIA.categorie, func.count(), func.coalesce(func.sum(ConsommationIA.cout_usd), 0.0))
            .where(ConsommationIA.ecole_id == ecole_id)
            .group_by(ConsommationIA.categorie)
        ).all()
        ia = [
            {"categorie": cat, "libelle": CATEGORIES_IA.get(cat, cat), "nombre": nombre, "cout_usd": round(cout, 4)}
            for cat, nombre, cout in lignes
        ]
        ia.sort(key=lambda ligne: ligne["cout_usd"], reverse=True)
        with toutes_saisons(db):
            total_toutes = db.scalar(
                select(func.coalesce(func.sum(ConsommationIA.cout_usd), 0.0)).where(
                    ConsommationIA.ecole_id == ecole_id
                )
            )
            saison_id = saison_demandee() or saison_courante_id(db, ecole_id)
            saison = db.get(Saison, saison_id) if saison_id else None
        return {
            "saison": saison.nom if saison is not None and saison.ecole_id == ecole_id else None,
            "memoire": memoire,
            "memoire_total_octets": sum(rubrique["octets"] for rubrique in memoire),
            "ia": ia,
            "ia_total_usd": round(sum(ligne["cout_usd"] for ligne in ia), 4),
            "ia_total_toutes_saisons_usd": round(total_toutes or 0.0, 4),
            "assistant_plafond_mensuel_usd": self.plafond_assistant(db, ecole_id),
            "assistant_cout_du_mois_usd": round(self.cout_du_mois(db, ecole_id, "chat_documents"), 4),
        }
