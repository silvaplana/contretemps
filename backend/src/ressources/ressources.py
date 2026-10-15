"""« Usage ressources et IA de la saison » (Admin > École, spec §5.1.1) :
la place que l'école occupe sur le disque, et ce qu'ont coûté ses
opérations d'IA, par poste.

Les modules qui font appel à une IA (lecture des fiches, détourage d'un
logo...) notent chaque opération par `noter_ia` ; ce module ne sait rien
d'eux au-delà du nom de leur poste.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from saisons import Saison
from saisons.portee import saison_demandee, toutes_saisons

from .models import ConsommationIA

# Postes de dépense : clé enregistrée -> libellé affiché.
CATEGORIES_IA = {
    "lecture_fiche": "Lecture des fiches d'inscription",
    "detourage_logo": "Personnalisation : détourage du logo",
    "chat_documents": "Chat documents",
}


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
            saison_id = saison_demandee() or db.scalar(
                select(func.max(Saison.id)).where(Saison.ecole_id == ecole_id)
            )
            saison = db.get(Saison, saison_id) if saison_id else None
        return {
            "saison": saison.nom if saison is not None and saison.ecole_id == ecole_id else None,
            "memoire": memoire,
            "memoire_total_octets": sum(rubrique["octets"] for rubrique in memoire),
            "ia": ia,
            "ia_total_usd": round(sum(ligne["cout_usd"] for ligne in ia), 4),
            "ia_total_toutes_saisons_usd": round(total_toutes or 0.0, 4),
        }
