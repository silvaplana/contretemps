"""Range dans Docs les justificatifs restés dans les enveloppes du disque
(`NOTES_FRAIS_DIR`), décision de Seb du 29 octobre 2026 : un seul endroit,
Docs › Financier, et l'état ne se lit que dans l'appli
(spec/modules/notes-de-frais.md §7 bis et §10).

Pour chaque note envoyée : ses photos, que l'ancien rangement avait déjà
copiées dans Docs, y sont reprises telles quelles (ou copiées si elles
manquent), puis effacées du disque avec « Note de frais.pdf » de l'enveloppe.
Les badges Brouillon / Validé / Officiel des dossiers de notes sont retirés.
Les tickets pas encore envoyés (`depenses/`) restent sur le disque.
Sans risque de relancer : ce qui est déjà rangé est laissé.

À lancer sur le serveur, dans le conteneur backend :

    docker compose exec backend python -m app.ranger_notes_frais

`--essai` affiche ce qui serait fait, sans rien changer.
"""

from __future__ import annotations

import argparse
import logging

from sqlalchemy import select

from app import main as appli
from db import SessionLocal
from documents.models import KIND_FOLDER, SYSTEM_RESERVED, DocNode
from notes_frais.models import Depense, NoteFrais, PieceJustificative
from notes_frais.ports import Membre
from notes_frais.recapitulatif import NOM_FICHIER

logger = logging.getLogger(__name__)


def ranger(db, essai: bool = False) -> tuple[int, int]:
    """(notes rangées, justificatifs rangés)."""
    service = appli.notes_frais_client
    notes = list(
        db.scalars(
            select(NoteFrais)
            .join(Depense, Depense.note_id == NoteFrais.id)
            .join(PieceJustificative, PieceJustificative.depense_id == Depense.id)
            .where(PieceJustificative.doc_node_id.is_(None))
            .distinct()
        )
    )
    nb_pieces = 0
    for note in notes:
        pieces = [p for d in note.depenses for p in d.pieces if p.doc_node_id is None]
        nb_pieces += len(pieces)
        print(f"École {note.org_id}, note {note.id} « {note.titre} » : {len(pieces)} justificatif(s)")
        if essai:
            continue
        membre = Membre(person_id=note.person_id, org_id=note.org_id, nom="", est_tresorier=True)
        chemin = service._chemin_docs(db, note)
        fichiers = [(service._nom_dans_docs(note, d, p), service.stockage.chemin(note.org_id, p.chemin))
                    for d in note.depenses for p in d.pieces if p.doc_node_id is None]
        presents = [(nom, f) for nom, f in fichiers if f.exists()]
        ids = service.ports.classeur.classer(db, membre, chemin, presents, reprendre=True) if presents else []
        par_nom = dict(zip((nom for nom, _ in presents), ids))
        for piece, (nom, fichier) in zip(pieces, fichiers):
            if nom not in par_nom:
                logger.warning("Note %s : %s introuvable sur le disque", note.id, fichier)
                continue
            piece.doc_node_id, ancien, piece.chemin = par_nom[nom], piece.chemin, nom
            db.commit()
            service.stockage.delete(note.org_id, ancien)
        enveloppe = service.stockage.dossier_note(
            note.org_id, note.person_id, "", note.envoyee_le.date().isoformat(), note.titre, note.id
        )
        service.stockage.delete(note.org_id, f"{enveloppe}/{NOM_FICHIER}")
    if not essai:
        _retirer_les_badges(db)
    return len(notes), nb_pieces


def _retirer_les_badges(db) -> None:
    """Dossiers de notes (Financier › Notes de frais › personne › note) :
    plus de badge, l'état est dans l'appli."""
    documents = appli.documents_client
    classeur = appli.notes_frais_client.ports.classeur
    reserves = select(DocNode.id).where(DocNode.system_kind == SYSTEM_RESERVED)
    racines = select(DocNode.id).where(DocNode.name.in_(classeur.DOSSIERS), DocNode.parent_id.in_(reserves))
    personnes = select(DocNode.id).where(DocNode.parent_id.in_(racines), DocNode.kind == KIND_FOLDER)
    for dossier in db.scalars(select(DocNode).where(DocNode.parent_id.in_(personnes), DocNode.status.is_not(None))):
        qui = classeur._qui(Membre(person_id=dossier.created_by or 0, org_id=dossier.org_id, nom=""))
        documents.update(db, qui, dossier.id, status=None, change_status=True)


def main() -> None:
    options = argparse.ArgumentParser(description="Range dans Docs les justificatifs des notes de frais.")
    options.add_argument("--essai", action="store_true", help="afficher ce qui serait fait, sans rien changer")
    arguments = options.parse_args()
    with SessionLocal() as db:
        notes, pieces = ranger(db, essai=arguments.essai)
    print(f"{notes} note(s), {pieces} justificatif(s) {'à ranger' if arguments.essai else 'rangés dans Docs'}.")


if __name__ == "__main__":
    main()
