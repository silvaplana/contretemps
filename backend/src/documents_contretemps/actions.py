"""Actions de Docs ouvertes à l'assistant (spec/modules/procurations.md §1.4) :
un bouton de l'écran « Convoquer l'AG » = un outil, qui appelle la même
fonction. Ici et pas dans `documents/` : il faut passer du compte de
Contretemps au `Member` du module.
"""

from __future__ import annotations

import datetime as dt
import threading
from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from documents import Documents, assembly
from documents.models import KIND_APP, DocNode
from documents.ports import Member
from documents.service import DocError

from .adapter import membre_appelant


class ConveneAssembly(BaseModel):
    kind: Literal["ordinary", "extraordinary"] = Field(description="ordinary : AG ordinaire (AGO) ; extraordinary : AGE.")
    date: dt.date = Field(description="Jour de l'assemblée, AAAA-MM-JJ.")
    time: dt.time = Field(description="Heure de début, HH:MM.")
    folder_name: str | None = Field(
        default=None, description="Nom du dossier d'AG choisi par la personne quand l'outil a demandé lequel ; null sinon."
    )
    new_folder: bool = Field(default=False, description="true si la personne veut un nouveau dossier plutôt qu'un existant.")


class AppFile(BaseModel):
    file: str = Field(min_length=1, max_length=200, description="Nom exact du fichier (ex. « Convocation AGO du 21 novembre 2026 ») ou son id.")


class MarkAttendance(AppFile):
    names: list[str] = Field(
        min_length=1, max_length=500,
        description="Les noms des présents, « Prénom Nom », tels que tu les as lus sur la photo et vérifiés avec la personne.",
    )


class AssemblyPdf(BaseModel):
    file: str = Field(min_length=1, max_length=200, description="Nom exact de la convocation (ex. « Convocation AGO du 21 novembre 2026 ») ou son id.")
    document: Literal["summary", "convocation"] = Field(
        description="summary : le récapitulatif des réponses (qui vient, qui représente qui, quorum) ; convocation : la convocation."
    )


def _member(db: Session, compte, org_id: int) -> Member:
    return replace(membre_appelant(db, compte), org_id=org_id)


def _file(docs: Documents, db: Session, member: Member, nom: str) -> DocNode:
    """Le fichier de l'appli, par id ou par nom (le plus récent)."""
    requete = select(DocNode).where(DocNode.org_id == member.org_id, DocNode.kind == KIND_APP, DocNode.deleted_at.is_(None))
    requete = requete.where(DocNode.id == int(nom)) if nom.strip().isdigit() else requete.where(DocNode.name == nom.strip())
    node = db.scalar(requete.order_by(DocNode.id.desc()).limit(1))
    if node is None:
        raise Refus(f"fichier « {nom} » introuvable")
    docs.apps._app_node(db, member, node.id)  # droit de le voir
    return node


def _refus(appel):
    try:
        return appel()
    except DocError as erreur:
        raise Refus(erreur.message) from erreur


def actions(docs: Documents) -> list[Action]:
    def convene(db: Session, compte, org_id: int, p: ConveneAssembly) -> Ligne:
        member = _member(db, compte, org_id)
        debut = dt.datetime.combine(p.date, p.time.replace(second=0, microsecond=0))
        if debut <= assembly.now_local():
            raise Refus("cette date est passée")
        titre = assembly.assembly_title(p.kind, debut)
        _, possibles, choisi = _refus(lambda: assembly.find_folder(docs, db, member, p.kind))
        dossier, ou = None, f"Réunions › {titre} (nouveau dossier)"
        if p.folder_name and not p.new_folder:
            trouve = [d for d in possibles if d["name"].casefold() == p.folder_name.strip().casefold()]
            if not trouve:
                raise Refus(f"dossier « {p.folder_name} » introuvable dans Réunions")
            dossier = trouve[0]
        elif choisi is not None and not p.new_folder:
            dossier = next(d for d in possibles if d["id"] == choisi)
        elif possibles and not p.new_folder:
            noms = ", ".join(f"« {d['name']} »" for d in possibles)
            raise Refus(
                f"plusieurs dossiers d'AG possibles dans Réunions : {noms}. Demande à la personne où ranger la convocation "
                f"(un de ces dossiers, ou un nouveau dossier « {titre} »), puis rappelle l'outil."
            )
        if dossier is not None:
            ou = f"Réunions › {dossier['name']}"

        def faire(db: Session) -> None:
            _refus(lambda: assembly.convene(
                docs, db, member, p.kind, debut.isoformat(timespec="minutes"),
                folder_id=dossier["id"] if dossier else None, new_folder=dossier is None,
            ))

        return Ligne(
            f"Préparer la convocation de l'{titre} à {assembly.when_text(debut).split(' à ')[1]}, rangée dans {ou} "
            f"(brouillon « Convocation {titre} », à relire avant de valider)",
            faire,
        )

    def validate(db: Session, compte, org_id: int, p: AppFile) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        if node.status == "official":
            raise Refus(f"« {node.name} » est déjà Officiel")

        def faire(db: Session) -> None:
            _refus(lambda: docs.update(db, member, node.id, status="official", change_status=True))

        return Ligne(f"Valider « {node.name} » : il devient Officiel (figé), prêt à envoyer", faire)

    def send(db: Session, compte, org_id: int, p: AppFile) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is None or assembly.block_of(version.content) is None:
            raise Refus("pour ce fichier, l'envoi se fait à l'écran (Diffuser) : choisir les personnes")
        if node.status != "official":
            raise Refus(f"« {node.name} » n'est pas encore validé : le valider d'abord")
        cibles = assembly.default_principals(docs, db, node)
        apercu = _refus(lambda: docs.sends.preview(db, member, node.id, cibles))
        if not apercu["count"]:
            raise Refus("personne n'a d'adresse email parmi les membres")
        noms = [r["name"] for r in apercu["recipients"]]
        liste = ", ".join(noms[:5]) + (f" et {len(noms) - 5} autres" if len(noms) > 5 else "")
        sans = f" ; sans adresse email : {', '.join(apercu['without_email'])}" if apercu["without_email"] else ""

        def faire(db: Session) -> None:
            _, jobs = _refus(lambda: docs.sends.send(db, member, node.id, cibles, None))
            threading.Thread(target=docs.sends.deliver, args=(db.get_bind(), jobs), daemon=True).start()

        return Ligne(f"Envoyer « {node.name} » par email à {apercu['count']} membre{'s' if apercu['count'] > 1 else ''} ({liste}){sans}", faire)

    def mark_attendance(db: Session, compte, org_id: int, p: MarkAttendance) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is None or assembly.block_of(version.content) is None:
            raise Refus(f"« {node.name} » n'est pas une convocation d'AG")
        if node.status != "official":
            raise Refus(f"« {node.name} » n'est pas encore officielle")
        gens = assembly.convoked(db, node)
        ids, restes = assembly.match_names(gens, p.names)
        if restes:
            raise Refus(
                f"pas de membre convoqué unique pour : {', '.join(restes)}. Demande à la personne qui c'est "
                "(nom et prénom complets), ou ajoute-le à la main sur la feuille d'émargement."
            )
        noms = ", ".join(gens[i] for i in ids)

        def faire(db: Session) -> None:
            _refus(lambda: assembly.mark_many(docs, db, member, node.id, ids))

        return Ligne(f"Pointer présents pour « {node.name} » : {noms} ({len(ids)} personne{'s' if len(ids) > 1 else ''})", faire)

    def remind(db: Session, compte, org_id: int, p: AppFile) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is None or assembly.block_of(version.content) is None:
            raise Refus("ce fichier n'est pas une convocation d'AG")
        if node.status != "official":
            raise Refus(f"« {node.name} » n'est pas encore validé ni envoyé")
        cibles = assembly.non_respondents(db, node)
        if not cibles:
            raise Refus("tout le monde a répondu : personne à relancer")
        noms = [s.name for s in cibles]
        liste = ", ".join(noms[:5]) + (f" et {len(noms) - 5} autres" if len(noms) > 5 else "")

        def faire(db: Session) -> None:
            _, jobs = _refus(lambda: assembly.remind(docs, db, member, node.id))
            threading.Thread(target=assembly.send_reminders, args=(docs.mailer, jobs), daemon=True).start()

        n = len(cibles)
        return Ligne(f"Relancer par email {'les' if n > 1 else 'le'} {n} membre{'s' if n > 1 else ''} qui n'{'ont' if n > 1 else 'a'} "
                     f"pas répondu à « {node.name} » ({liste})", faire)

    def store_pdf(db: Session, compte, org_id: int, p: AssemblyPdf) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is None or assembly.block_of(version.content) is None:
            raise Refus("ce fichier n'est pas une convocation d'AG")
        dossier = db.get(DocNode, node.parent_id) if node.parent_id else None
        parent = db.get(DocNode, dossier.parent_id) if dossier is not None and dossier.parent_id else None
        ou = f"{parent.name} › {dossier.name}" if parent is not None else (dossier.name if dossier is not None else "le dossier")

        def faire(db: Session) -> None:
            _refus(lambda: assembly.store(docs, db, member, node.id, p.document))

        return Ligne(f"Ranger « {assembly.stored_name(node, p.document)} » dans {ou}", faire)

    return [
        Action("mark_attendance", "Docs",
               "Pointe les présents d'une assemblée générale sur la feuille d'émargement de sa convocation (comme "
               "« Lire la liste » après la photo de la liste des présents). Lis toi-même la photo envoyée, vérifie avec "
               "la personne les noms dont tu n'es pas sûr, puis donne les noms. Le quorum est recalculé par l'appli.",
               MarkAttendance, mark_attendance),
        Action("convene_assembly", "Docs",
               "Convoquer l'assemblée générale (comme Docs › + › Convoquer l'AG) : prépare la convocation en brouillon, "
               "avec l'ordre du jour de l'an dernier ou un ordre du jour de base, rangée dans Réunions. Demande d'abord "
               "à la personne ce qui manque : ordinaire ou extraordinaire, la date et l'heure. Ensuite la personne relit "
               "et corrige le brouillon, puis on le valide (validate_app_file) et on l'envoie (send_app_file).",
               ConveneAssembly, convene),
        Action("validate_app_file", "Docs",
               "Valide un fichier de Docs (convocation, questionnaire) : il passe en Officiel, figé, prêt à envoyer. "
               "Seulement quand la personne a relu et le demande.",
               AppFile, validate),
        Action("send_app_file", "Docs",
               "Envoie une convocation d'AG validée par email aux membres (ceux de la dernière AG, sinon tous les membres "
               "de la saison), chacun avec son lien personnel pour répondre. Jamais pour répondre ou signer à la place "
               "d'un membre : chacun répond lui-même.",
               AppFile, send),
        Action("remind_assembly", "Docs",
               "Relance par email, tout de suite, les membres convoqués à une AG qui n'ont pas encore répondu (comme "
               "Résultats › Relancer). Pour savoir où en sont les réponses et le quorum, lis d'abord la convocation "
               "avec lire_fichier.",
               AppFile, remind),
        Action("store_assembly_pdf", "Docs",
               "Range en PDF, dans le dossier de l'AG, le récapitulatif des réponses ou la convocation, pour que la "
               "personne l'ouvre ou l'imprime (comme les boutons Télécharger de l'écran). Les pouvoirs signés sont "
               "déjà dans le dossier « Pouvoirs ».",
               AssemblyPdf, store_pdf),
    ]
