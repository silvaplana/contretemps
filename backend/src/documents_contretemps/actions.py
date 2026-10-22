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
from documents import Documents, assembly, minutes, signing
from documents.models import KIND_APP, KIND_FILE, DocNode
from documents.ports import Member
from documents.service import DocError

from .adapter import membre_appelant


# « Fais signer le PV au trésorier et aux professeurs » : les mots que
# l'assistant transmet tels quels, vers une puce de « Faire signer à qui ? ».
SIGN_GROUPS = {"professeur": "role:professeur", "professeurs": "role:professeur", "eleve": "role:eleve", "eleves": "role:eleve"}
SIGN_FUNCTIONS = {
    mot: "Président·e" for mot in ("president", "presidente", "presidence")
} | {
    mot: "Vice-président·e" for mot in ("vice-president", "vice-presidente", "vice president", "vice presidente")
} | {
    mot: "Secrétaire" for mot in ("secretaire", "secretariat")
} | {
    mot: "Trésorier·e" for mot in ("tresorier", "tresoriere")
}


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


class SendAppFile(AppFile):
    signers: list[str] | None = Field(
        default=None, max_length=10,
        description="Procès-verbal ou document à signer Validé : qui doit signer, si la personne l'a dit : des noms "
        "(« Prénom Nom »), une fonction du bureau (« président », « trésorier », « secrétaire »), « professeurs » ou "
        "« élèves » ; null = pour un PV, la présidence et le secrétariat du bureau ; pour les deux, s'il est déjà "
        "parti, relancer ceux qui n'ont pas encore signé (ni refusé).",
    )


class PrepareSignature(BaseModel):
    document: str = Field(min_length=1, max_length=200, description="Nom exact du PDF ou du Word à faire signer, tel qu'il est dans Docs, ou son id.")
    mode: Literal["end", "initials"] = Field(
        default="end", description="end : une signature à la fin ; initials : signature à la fin et paraphe en bas de chaque page.",
    )
    mention: str | None = Field(
        default=None, max_length=120, description="Mention écrite au-dessus de chaque signature ; null = « Lu et approuvé ».",
    )
    message: str | None = Field(default=None, max_length=2000, description="Message aux signataires, repris dans le mail ; null = aucun.")


class DraftMinutes(BaseModel):
    assembly: str | None = Field(
        default=None, max_length=200,
        description="L'assemblée (ex. « AGO du 21 novembre 2026 ») quand l'outil a demandé laquelle ; null sinon.",
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


def _a_ouvrir(cree: dict) -> dict:
    """Le fichier de l'appli créé, à ouvrir à l'écran pour le relire
    (Seb, 21 octobre : il s'ouvre au-dessus de l'assistant)."""
    return {"open": {"id": cree["id"], "name": cree["name"], "kind": "app", "family": cree["family"],
                     "space": "private", "parent_id": cree["folder_id"]}}


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

        def faire(db: Session) -> dict:
            return _a_ouvrir(_refus(lambda: assembly.convene(
                docs, db, member, p.kind, debut.isoformat(timespec="minutes"),
                folder_id=dossier["id"] if dossier else None, new_folder=dossier is None,
            )))

        return Ligne(
            f"Préparer la convocation de l'{titre} à {assembly.when_text(debut).split(' à ')[1]}, rangée dans {ou} "
            f"(brouillon « Convocation {titre} », à relire avant de valider)",
            faire,
        )

    def prepare_signature(db: Session, compte, org_id: int, p: PrepareSignature) -> Ligne:
        member = _member(db, compte, org_id)
        requete = select(DocNode).where(DocNode.org_id == org_id, DocNode.kind == KIND_FILE, DocNode.deleted_at.is_(None))
        nom = p.document.strip()
        requete = requete.where(DocNode.id == int(nom)) if nom.isdigit() else requete.where(DocNode.name == nom)
        source = db.scalar(requete.order_by(DocNode.id.desc()).limit(1))
        if source is None:
            raise Refus(f"document « {p.document} » introuvable dans Docs")
        source = _refus(lambda: signing._source(docs, db, member, source.id))
        ou = "signature à la fin" + (" et paraphe en bas de chaque page" if p.mode == "initials" else "")

        def faire(db: Session) -> dict:
            cree = _refus(lambda: signing.create(docs, db, member, source.space, source.parent_id, source.id))
            version = docs.apps.current_version(db, db.get(DocNode, cree["id"]))
            bloc = signing.block_of(version.content)
            reglages = {"mode": p.mode, "message": p.message or ""}
            if p.mention is not None:
                reglages["mention"] = p.mention
            blocs = [{**b, "props": {**b["props"], **reglages}} if b is bloc else b for b in version.content["entry"]["blocks"]]
            _refus(lambda: docs.apps.save(db, member, cree["id"], {**version.content, "entry": {"blocks": blocs}}))
            return _a_ouvrir(cree)

        return Ligne(
            f"Préparer « Signature : {signing._stem(source.name)} » à côté de « {source.name} » ({ou}), "
            "en brouillon, à relire avant de valider",
            faire,
        )

    def validate(db: Session, compte, org_id: int, p: AppFile) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        if node.status == "official":
            raise Refus(f"« {node.name} » est déjà Officiel")
        version = docs.apps.current_version(db, node)
        if version is not None and signing.block_of(version.content) is not None:
            if node.status == "validated":
                raise Refus(f"« {node.name} » est déjà validé : le document est figé")

            def figer(db: Session) -> None:
                _refus(lambda: docs.update(db, member, node.id, status="validated", change_status=True))

            return Ligne(f"Valider « {node.name} » : le document est figé (empreinte enregistrée), prêt à faire signer", figer)
        if version is not None and minutes.block_of(version.content) is not None:
            # Le PV devient Officiel quand tout le monde a signé (proces-verbal-ag.md §1).
            if node.status == "validated":
                raise Refus(f"« {node.name} » est déjà validé : il reste à l'envoyer pour signature")

            def valider(db: Session) -> None:
                _refus(lambda: docs.update(db, member, node.id, status="validated", change_status=True))

            return Ligne(f"Valider « {node.name} » : le texte est figé, prêt à envoyer pour signature au bureau", valider)

        def faire(db: Session) -> None:
            _refus(lambda: docs.update(db, member, node.id, status="official", change_status=True))

        return Ligne(f"Valider « {node.name} » : il devient Officiel (figé), prêt à envoyer", faire)

    def send(db: Session, compte, org_id: int, p: SendAppFile) -> Ligne:
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is not None and minutes.block_of(version.content) is not None:
            return send_minutes(db, member, node, version.content, p.signers)
        if version is not None and signing.block_of(version.content) is not None:
            return send_signing(db, member, node, p.signers)
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

    def send_minutes(db: Session, member: Member, node: DocNode, content: dict, noms: list[str] | None) -> Ligne:
        """Validé : pour signature ; Officiel (tout le monde a signé) : aux membres."""
        if node.status == "official":
            convocation = db.get(DocNode, minutes.source_of(content))
            gens = assembly.convoked(db, convocation) if convocation is not None else {}
            if not gens:
                raise Refus("la convocation de cette assemblée est introuvable : envoyer à l'écran (Diffuser)")
            cibles = [{"type": "member", "id": str(i)} for i in gens]
            apercu = _refus(lambda: docs.sends.preview(db, member, node.id, cibles))

            def envoyer(db: Session) -> None:
                _, jobs = _refus(lambda: docs.sends.send(db, member, node.id, cibles, None))
                threading.Thread(target=docs.sends.deliver, args=(db.get_bind(), jobs), daemon=True).start()

            return Ligne(f"Envoyer « {node.name} » à lire par email aux {apercu['count']} membres convoqués à l'assemblée", envoyer)
        if node.status != "validated":
            raise Refus(f"« {node.name} » n'est pas encore validé : le valider d'abord (validate_app_file)")
        etat = _refus(lambda: minutes.status(docs, db, member, node.id))
        bureau = {b["person_id"]: b for b in etat["board"]}
        if noms:
            gens = {b["person_id"]: b["name"] for b in etat["board"]}
            convocation = db.get(DocNode, etat["convocation_id"]) if etat["convocation_id"] else None
            if convocation is not None:
                gens = {**assembly.convoked(db, convocation), **gens}
            ids, restes = assembly.match_names(gens, noms)
            if restes:
                raise Refus(f"pas de membre unique pour : {', '.join(restes)}. Demande le nom et le prénom complets.")
            qui = [(i, gens[i]) for i in ids]
        elif etat["signers"]:
            qui = [(s["person_id"], s["name"]) for s in etat["signers"] if not s["signed_at"]]
            if not qui:
                raise Refus("tout le monde a signé")
        else:
            qui = [(b["person_id"], b["name"]) for b in etat["board"] if b["default"]]
            if not qui:
                raise Refus(
                    "personne n'a la fonction Président·e ou Secrétaire (École › Administrateurs, colonne Bureau) : "
                    "demande à la personne qui doit signer, puis rappelle l'outil avec leurs noms"
                )
        liste = ", ".join(f"{n} ({bureau[i]['functions']})" if i in bureau and bureau[i]["functions"] else n for i, n in qui)
        relance = bool(etat["signers"]) and not noms

        def signer(db: Session) -> None:
            _, jobs = _refus(lambda: minutes.send_for_signature(docs, db, member, node.id, [i for i, _ in qui]))
            threading.Thread(target=docs.sends.deliver, args=(db.get_bind(), jobs), daemon=True).start()

        return Ligne(f"{'Relancer pour' if relance else 'Envoyer pour'} signature « {node.name} » à {liste}", signer)

    def send_signing(db: Session, member: Member, node: DocNode, noms: list[str] | None) -> Ligne:
        """« Faire signer à qui ? » (signature-documents.md §2.3) : des membres,
        des fonctions du bureau, les professeurs ou les élèves ; sans noms,
        « Relancer les N ». Quelqu'un hors de l'école s'ajoute à l'écran."""
        if node.status == "official":
            raise Refus(f"« {node.name} » est déjà signé par tous")
        if node.status != "validated":
            raise Refus(f"« {node.name} » n'est pas encore validé : le valider d'abord (validate_app_file)")
        etat = _refus(lambda: signing.signers_status(docs, db, member, node.id))
        if not noms:
            if not etat["signers"]:
                raise Refus(
                    "à qui faire signer ? Demande-le à la personne (des noms, une fonction du bureau, les professeurs "
                    "ou les élèves), puis rappelle l'outil avec signers"
                )
            refus = {s["id"] for s in etat["signers"] if s["state"] == "refused"}
            qui = [s["name"] for s in etat["signers"] if s["state"] != "signed" and s["id"] not in refus]
            if not qui:
                raise Refus("personne à relancer : tout le monde a signé ou refusé")

            def relancer(db: Session) -> None:
                _, jobs = _refus(lambda: signing.remind(docs, db, member, node.id, None))
                threading.Thread(target=docs.sends.deliver, args=(db.get_bind(), jobs), daemon=True).start()

            return Ligne(f"Relancer pour signature « {node.name} » : {', '.join(qui)}", relancer)
        bureau = {b["function"]: b["person_id"] for b in etat["board"]}
        tous = {r.person_id: r.name for r in docs.directory.recipients(db, node.org_id, [("group", "role:tous")])}
        cibles, restes = [], []
        for nom in noms:
            cle = assembly._norm(nom).removeprefix("le ").removeprefix("la ").removeprefix("les ").strip()
            fonction = SIGN_FUNCTIONS.get(cle)
            if cle in SIGN_GROUPS:
                cibles.append({"type": "group", "id": SIGN_GROUPS[cle]})
            elif fonction is not None and fonction in bureau:
                cibles.append({"type": "member", "id": str(bureau[fonction])})
            else:
                ids, pas = assembly.match_names(tous, [nom])
                cibles += [{"type": "member", "id": str(i)} for i in ids]
                restes += pas
        if restes:
            raise Refus(f"pas de membre unique ni de fonction du bureau pour : {', '.join(restes)}. Demande le nom et le prénom complets.")
        apercu = _refus(lambda: signing.preview_send(docs, db, member, node.id, cibles, []))
        if not apercu["count"]:
            raise Refus("tout le monde a déjà signé" if apercu["signed"] else "personne n'a d'adresse email parmi ces personnes")
        liste = ", ".join(r["name"] for r in apercu["recipients"])
        sans = f" ; sans adresse email : {', '.join(apercu['without_email'])}" if apercu["without_email"] else ""

        def envoyer(db: Session) -> None:
            _, jobs = _refus(lambda: signing.send(docs, db, member, node.id, cibles, []))
            threading.Thread(target=docs.sends.deliver, args=(db.get_bind(), jobs), daemon=True).start()

        return Ligne(f"Envoyer pour signature « {node.name} » à {liste}{sans}", envoyer)

    def produce_signed(db: Session, compte, org_id: int, p: AppFile) -> Ligne:
        """« Produire le document signé » (signature-documents.md §2.5) :
        refusé tant qu'il manque une signature."""
        member = _member(db, compte, org_id)
        node = _file(docs, db, member, p.file)
        version = docs.apps.current_version(db, node)
        if version is None or signing.block_of(version.content) is None:
            raise Refus("ce fichier n'est pas un document à signer")
        etat = _refus(lambda: signing.signers_status(docs, db, member, node.id))
        if not etat["frozen"] or not etat["signers"]:
            raise Refus("personne n'a encore été invité à signer : valider puis envoyer d'abord (send_app_file)")
        manque = [s["name"] for s in etat["signers"] if s["state"] != "signed"]
        if manque:
            raise Refus(f"il manque la signature de {', '.join(manque)} : le document signé se produit quand tout le monde a signé")
        n = len(etat["signers"])
        fige = signing.frozen(db, node)
        nom = signing._signed_name(fige, signing.minutes.signers(db, node))

        def faire(db: Session) -> None:
            _, jobs = _refus(lambda: signing.produce(docs, db, member, node.id))
            threading.Thread(target=signing.deliver_signed, args=(docs.mailer, jobs), daemon=True).start()

        return Ligne(
            f"Produire « {nom} » et ses preuves à côté de l'original, les envoyer par email "
            f"{'aux ' + str(n) + ' signataires' if n > 1 else 'au signataire'} et passer « {node.name} » en Officiel",
            faire,
        )

    def draft_minutes(db: Session, compte, org_id: int, p: DraftMinutes) -> Ligne:
        member = _member(db, compte, org_id)
        possibles = _refus(lambda: minutes.pending(docs, db, member))
        if p.assembly:
            cle = assembly._norm(p.assembly.removeprefix("Convocation "))
            possibles = [a for a in possibles if assembly._norm(a["title"]) == cle]
            if not possibles:
                raise Refus(f"pas d'assemblée passée sans procès-verbal qui s'appelle « {p.assembly} »")
        if not possibles:
            raise Refus("aucune assemblée passée n'attend son procès-verbal (convocation officielle, envoyée, date passée)")
        if len(possibles) > 1:
            noms = ", ".join(f"« {a['title']} »" for a in possibles)
            raise Refus(f"plusieurs assemblées attendent leur procès-verbal : {noms}. Demande laquelle, puis rappelle l'outil.")
        ag = possibles[0]
        convocation = db.get(DocNode, ag["id"])
        feuille = assembly.sheet(docs, db, convocation, docs.apps.current_version(db, convocation).content)
        if not feuille["present"]:
            raise Refus(
                "personne n'est pointé présent sur la feuille d'émargement : demande d'abord la photo de la liste des "
                "présents (puis mark_attendance)"
            )

        def faire(db: Session) -> dict:
            return _a_ouvrir(_refus(lambda: minutes.draft(docs, db, member, ag["id"])))

        return Ligne(
            f"Préparer le procès-verbal de l'{ag['title']} en brouillon (« PV de l'{ag['title']} », à côté de la convocation ; "
            f"{feuille['present']} présents, {feuille['represented']} représentés, comptés par l'appli)",
            faire,
        )

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
        Action("draft_minutes", "Docs",
               "Produire le procès-verbal d'une assemblée générale passée (comme Docs › + › Produire le PV d'AG) : "
               "prépare le PV en brouillon à côté de la convocation, chiffres (présents, représentés, quorum, bilan) "
               "écrits par l'appli, plan repris du PV de l'an dernier, « À compléter » pour le reste. Il faut d'abord "
               "les présents pointés (mark_attendance). Ensuite tu n'écris dans le texte que ce que la personne te dit "
               "(jamais un résultat de vote inventé), puis on valide (validate_app_file) et on envoie pour signature "
               "(send_app_file).",
               DraftMinutes, draft_minutes),
        Action("prepare_signature", "Docs",
               "Faire signer un PDF ou un Word de Docs (comme ⋯ › Faire signer… ou Docs › + › Faire signer un "
               "document) : prépare en brouillon, à côté du document, le fichier « Signature : … » avec où signer, la "
               "mention et le message aux signataires. Ensuite la personne relit (un Word se corrige dans l'Aperçu), "
               "puis on valide (validate_app_file), ce qui fige le document. Tu ne signes jamais à la place de quelqu'un.",
               PrepareSignature, prepare_signature),
        Action("validate_app_file", "Docs",
               "Valide un fichier de Docs : une convocation ou un questionnaire passe en Officiel, figé, prêt à envoyer ; "
               "un procès-verbal ou un document à signer passe en Validé, figé, prêt pour les signatures. Seulement "
               "quand la personne a relu et le demande.",
               AppFile, validate),
        Action("send_app_file", "Docs",
               "Envoie par email, chacun avec son lien personnel : une convocation d'AG validée aux membres (ceux de la "
               "dernière AG, sinon tous les membres de la saison) ; un procès-verbal validé pour signature au bureau "
               "(présidence et secrétariat, ou les noms donnés ; s'il est déjà parti, relance ceux qui n'ont pas signé) ; "
               "un procès-verbal signé de tous, à lire, aux membres convoqués ; un document à signer validé, aux "
               "signataires nommés (noms, fonctions du bureau, professeurs, élèves ; s'il est déjà parti, relance ceux "
               "qui n'ont ni signé ni refusé). Jamais pour répondre ou signer à la "
               "place de quelqu'un : chacun répond et signe lui-même.",
               SendAppFile, send),
        Action("produce_signed", "Docs",
               "Produit le document signé d'un document à signer dont tout le monde a signé (comme Voir les résultats › "
               "Produire le document signé) : le PDF avec les signatures et, à part, le certificat de preuves, rangés à côté de "
               "l'original, envoyé par email aux signataires ; le fichier passe en Officiel. Refusé tant qu'il manque "
               "une signature : pour savoir où en sont les signatures, lis le fichier avec lire_fichier.",
               AppFile, produce_signed),
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
