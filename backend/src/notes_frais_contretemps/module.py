"""Déclaration du sous-module Notes de frais pour Contretemps (spec/core.md
§9 bis, spec/modules/notes-de-frais.md) : le module `notes_frais` est relié
ici aux fiches, à la messagerie et au dossier Financier des Docs."""

import hashlib
import os
from pathlib import Path

from notes_frais import LecteurClaude, NotesDeFrais, NotesDeFraisReceiver, Ports, StockageEnveloppes
from registry import Module

from .actions import actions
from .adapter import (
    AnnuaireContretemps,
    BanqueContretemps,
    ClasseurContretemps,
    MessagerContretemps,
    NotifieurContretemps,
    compte_de_tiers,
    comptes_de_charges,
    ajouter_comptes_paie,
    comptes_de_produits,
    comptes_paie_manquants,
    membre_appelant,
    retirer_comptes_paie,
)

# Justificatifs pas encore envoyés (ensuite, ils sont dans Docs) : jamais
# servis en statique, seulement par les routes du module.
DOSSIER_NOTES_FRAIS = Path(os.environ.get("NOTES_FRAIS_DIR", "./data/notes_frais"))


def _lecteur_drive(core):
    """Le fichier d'un justificatif resté sur un drive : relu à chaque
    ouverture, copie de passage sous NOTES_FRAIS_DIR/_drive (import-auto-
    pieces.md §6)."""
    drives = getattr(core, "drives", None)
    if drives is None:
        return None

    def lire(db, org_id: int, drive_id: int, chemin: str) -> Path:
        try:
            contenu = drives.call(db, org_id, drive_id, lambda client: client.read(chemin))
        except Exception as erreur:
            raise LookupError("Fichier introuvable sur le drive.") from erreur
        cle = hashlib.sha256(f"{drive_id}:{chemin}".encode()).hexdigest()
        cible = DOSSIER_NOTES_FRAIS / "_drive" / str(org_id) / f"{cle}{Path(chemin).suffix.lower()}"
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(contenu)
        return cible

    return lire


def _deposeur_drive(core):
    """Emplacement des pièces manuelles (financier.md §8.13): a receipt put
    on a club drive, under the chosen folder › season of its date › …"""
    drives = getattr(core, "drives", None)
    if drives is None:
        return None

    def deposer(db, org_id: int, drive_id: int, racine: str, sous_dossiers: list[str], nom: str, contenu: bytes, mime: str, le) -> str:
        from documents_contretemps.adapter import _saison_courante
        from saisons.models import Saison
        from saisons.portee import toutes_saisons

        from .adapter import _saison_contenant

        saison = _saison_contenant(db, org_id, le)
        if saison is None:
            with toutes_saisons(db):
                courante = _saison_courante(db, org_id)
                saison = courante and db.get(Saison, courante)
        dossier = "/".join([racine, *([saison.nom] if saison else []), *sous_dossiers])
        return drives.call(db, org_id, drive_id, lambda client: client.write(client.folder(dossier), nom, contenu, mime))

    return deposer


def mount(app, core) -> None:
    ressources = core.ressources_client
    core.notes_frais_client = NotesDeFrais(
        ports=Ports(
            annuaire=AnnuaireContretemps(),
            messager=MessagerContretemps(),
            notifieur=NotifieurContretemps(core.notifications_client),
            lecteur=LecteurClaude(
                noter_cout=lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, "lecture_ticket", cout, detail),
                plafond_atteint=ressources.plafond_assistant_atteint,
            ),
            # Justificatifs rangés dans Docs › Financier › Notes de frais.
            classeur=ClasseurContretemps(core.documents_client),
            # Virement vu sur le compte (financier.md §8.3 bis).
            banque=BanqueContretemps(),
            # Catégories des dépenses = comptes de charges du plan comptable.
            plan=comptes_de_charges,
            # Comptes d'une vente = comptes de produits (financier.md §8.12).
            plan_ventes=comptes_de_produits,
            # Comptes d'un bulletin de salaire (641, 645, 431), ajoutés d'un toucher (financier.md §8.11).
            paie_manquants=comptes_paie_manquants,
            ajouter_paie=ajouter_comptes_paie,
            retirer_paie=retirer_comptes_paie,
            # Compte de tiers des écritures montrées à la revue de l'import.
            tiers=compte_de_tiers,
            # Justificatif resté sur un drive du club (Importation automatique de pièces).
            drive=_lecteur_drive(core),
            # Receipts put on a club drive (Emplacement des pièces manuelles).
            deposer=_deposeur_drive(core),
        ),
        stockage=StockageEnveloppes(DOSSIER_NOTES_FRAIS, 20 * 1024 * 1024),
    )
    NotesDeFraisReceiver(client=core.notes_frais_client, app=app, membre_courant=membre_appelant)


MODULE = Module(
    key="expense_notes", label="Notes de frais", mount=mount, requires=("documents",),
    actions=lambda core: actions(core.notes_frais_client),
)
