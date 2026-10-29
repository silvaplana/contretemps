"""Efface toutes les notes de frais d'une école : notes, dépenses,
justificatifs, et leurs dossiers « Notes de frais », « Honoraires » et
« Achats » dans Docs › Financier.
Garde les catégories et les RIB. Pour repartir de zéro après des essais
(demande de Seb du 2026-10-18). Irréversible.

À lancer sur le serveur, dans le conteneur backend :

    docker compose exec backend python -m app.vider_notes_frais

La commande affiche les écoles et ce qu'elles contiennent, demande le
numéro de l'école, puis de retaper son nom avant d'effacer quoi que ce soit.

Sans clavier (action GitHub « Maintenance », voir DEPLOY.md §6) :

    python -m app.vider_notes_frais --lister
    python -m app.vider_notes_frais --ecole 3 --nom "Contretemps"

`--nom` tient lieu de confirmation : rien n'est effacé s'il ne correspond
pas exactement au nom de l'école.
"""

from __future__ import annotations

import argparse
import shutil
import sys

from sqlalchemy import func, select

from app import main as appli
from db import SessionLocal
from documents.models import KIND_FOLDER, SYSTEM_RESERVED, DocNode
from ecoles.models import Ecole
from notes_frais.models import Depense, NoteFrais, PieceJustificative


def _compter(db, org_id: int) -> tuple[int, int, int]:
    notes = db.scalar(select(func.count()).select_from(NoteFrais).where(NoteFrais.org_id == org_id))
    depenses = db.scalar(select(func.count()).select_from(Depense).where(Depense.org_id == org_id))
    pieces = db.scalar(
        select(func.count())
        .select_from(PieceJustificative)
        .join(Depense, PieceJustificative.depense_id == Depense.id)
        .where(Depense.org_id == org_id)
    )
    return notes, depenses, pieces


def _dossiers_docs(db, org_id: int) -> list[DocNode]:
    """Les dossiers « Notes de frais », « Honoraires » et « Achats » rangés
    dans un dossier réservé (Financier de chaque saison), corbeille comprise."""
    reserves = select(DocNode.id).where(DocNode.org_id == org_id, DocNode.system_kind == SYSTEM_RESERVED)
    return list(
        db.scalars(
            select(DocNode).where(
                DocNode.org_id == org_id,
                DocNode.kind == KIND_FOLDER,
                DocNode.name.in_(appli.notes_frais_client.ports.classeur.DOSSIERS),
                DocNode.parent_id.in_(reserves),
            )
        )
    )


def vider(db, org_id: int) -> None:
    depenses = select(Depense.id).where(Depense.org_id == org_id)
    db.query(PieceJustificative).filter(PieceJustificative.depense_id.in_(depenses)).delete(synchronize_session=False)
    db.query(Depense).filter(Depense.org_id == org_id).delete(synchronize_session=False)
    db.query(NoteFrais).filter(NoteFrais.org_id == org_id).delete(synchronize_session=False)
    db.commit()
    dossiers = _dossiers_docs(db, org_id)
    if dossiers:
        appli.documents_client._erase(db, org_id, dossiers)
    shutil.rmtree(appli.notes_frais_client.stockage._org(org_id), ignore_errors=True)


def _lister(db) -> list[Ecole]:
    ecoles = list(db.scalars(select(Ecole).order_by(Ecole.id)))
    for ecole in ecoles:
        notes, depenses, pieces = _compter(db, ecole.id)
        print(f"{ecole.id:>3}  {ecole.nom} ({ecole.code_postal}) : {notes} notes, {depenses} dépenses, {pieces} justificatifs")
    return ecoles


def _effacer(db, ecoles: list[Ecole], numero: str, nom: str) -> None:
    ecole = next((e for e in ecoles if str(e.id) == numero.strip()), None)
    if ecole is None:
        sys.exit("École inconnue : rien n'a été effacé.")
    if nom.strip() != ecole.nom:
        sys.exit(f"Le nom ne correspond pas à « {ecole.nom} » : rien n'a été effacé.")
    vider(db, ecole.id)
    print(f"Notes de frais de « {ecole.nom} » effacées (catégories et RIB gardés).")


def main() -> None:
    options = argparse.ArgumentParser(description="Efface les notes de frais d'une école.")
    options.add_argument("--lister", action="store_true", help="afficher les écoles et ce qu'elles contiennent, sans rien effacer")
    options.add_argument("--ecole", help="numéro de l'école à vider")
    options.add_argument("--nom", help="nom exact de l'école, en confirmation")
    arguments = options.parse_args()
    with SessionLocal() as db:
        ecoles = _lister(db)
        if arguments.lister:
            return
        if arguments.ecole is not None:
            _effacer(db, ecoles, arguments.ecole, arguments.nom or "")
            return
        choix = input("Numéro de l'école à vider (Entrée pour annuler) : ").strip()
        if not choix:
            sys.exit("Rien n'a été effacé.")
        ecole = next((e for e in ecoles if str(e.id) == choix), None)
        nom = input(f"Retapez le nom « {ecole.nom} » pour tout effacer : ") if ecole else ""
        _effacer(db, ecoles, choix, nom)


if __name__ == "__main__":
    main()
