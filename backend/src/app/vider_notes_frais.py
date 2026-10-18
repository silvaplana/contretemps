"""Efface toutes les notes de frais d'une école : notes, dépenses,
justificatifs, et leur dossier « Notes de frais » dans Docs › Financier.
Garde les catégories et les RIB. Pour repartir de zéro après des essais
(demande de Seb du 2026-10-18). Irréversible.

À lancer sur le serveur, dans le conteneur backend :

    docker compose exec backend python -m app.vider_notes_frais

La commande affiche les écoles et ce qu'elles contiennent, demande le
numéro de l'école, puis de retaper son nom avant d'effacer quoi que ce soit.
"""

from __future__ import annotations

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
    """Les dossiers « Notes de frais » rangés dans un dossier réservé
    (Financier de chaque saison), corbeille comprise."""
    reserves = select(DocNode.id).where(DocNode.org_id == org_id, DocNode.system_kind == SYSTEM_RESERVED)
    return list(
        db.scalars(
            select(DocNode).where(
                DocNode.org_id == org_id,
                DocNode.kind == KIND_FOLDER,
                DocNode.name == appli.notes_frais_client.ports.classeur.DOSSIER,
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


def main() -> None:
    with SessionLocal() as db:
        ecoles = list(db.scalars(select(Ecole).order_by(Ecole.id)))
        for ecole in ecoles:
            notes, depenses, pieces = _compter(db, ecole.id)
            print(f"{ecole.id:>3}  {ecole.nom} ({ecole.code_postal}) : {notes} notes, {depenses} dépenses, {pieces} justificatifs")
        choix = input("Numéro de l'école à vider (Entrée pour annuler) : ").strip()
        ecole = next((e for e in ecoles if str(e.id) == choix), None)
        if ecole is None:
            sys.exit("Rien n'a été effacé.")
        if input(f"Retapez le nom « {ecole.nom} » pour tout effacer : ").strip() != ecole.nom:
            sys.exit("Nom différent : rien n'a été effacé.")
        vider(db, ecole.id)
        print(f"Notes de frais de « {ecole.nom} » effacées (catégories et RIB gardés).")


if __name__ == "__main__":
    main()
