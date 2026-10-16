"""Diffuser à des personnes choisies (fichier-de-base.md §2.3) : un email par
personne, avec son lien personnel ; le suivi envoyé / ouvert / répondu.

- En Validé, on n'envoie qu'à des personnes nommées (soi, les relecteurs),
  au plus MAX_REVIEWERS, et leurs réponses sont des essais ; en Officiel, à
  qui l'on veut, réponses comptées (décision de Seb du 16 octobre, §7).
- Le lien personnel ouvre le formulaire d'entrée sans compte ; une seule
  réponse par lien : y revenir la corrige.
- Renvoyer à quelqu'un qui a déjà reçu le fichier lui renvoie le même lien.
- Les emails partent après la réponse à la requête (`deliver`) : une école
  de 200 élèves n'attend pas 200 connexions au serveur de mails.
"""

from __future__ import annotations

import logging
import secrets
from html import escape
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import app_content
from .app_content import ContentError
from .models import LEVEL_MANAGE, DocNode, DocResponse, DocSend, utcnow
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

logger = logging.getLogger(__name__)

MAX_REVIEWERS = 10
MAX_MESSAGE = 2000
BUTTONS = {"inform": "Voir en ligne", "question": "Répondre", "act": "S'inscrire"}


class AppSends:
    def __init__(self, docs: Documents) -> None:
        self.docs = docs

    @property
    def apps(self):
        return self.docs.apps

    def _error(self, status: int, message: str):
        from .service import DocError

        return DocError(status, message)

    # ------------------------------------------------------------------
    # Préparer l'envoi
    # ------------------------------------------------------------------

    def _ready(self, db: Session, member: Member, node_id: int) -> tuple[DocNode, bool]:
        """Le fichier, et s'il s'agit d'une relecture (Validé)."""
        node = self.apps._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_MANAGE)
        if node.space == "personal":
            raise self._error(409, "Un fichier de l'espace Personnel ne se diffuse pas.")
        if node.status not in ("validated", "official"):
            raise self._error(409, "Passez d'abord le fichier en Validé (relecture) ou en Officiel (tout le monde).")
        version = self.apps.current_version(db, node)
        if version is None or not version.content.get("entry", {}).get("blocks"):
            raise self._error(409, "Le formulaire d'entrée est vide.")
        return node, node.status == "validated"

    def _recipients(self, db: Session, member: Member, principals, test: bool):
        cles = []
        for p in principals or []:
            t, i = str(p.get("type", "")), str(p.get("id", ""))
            if t not in ("member", "group") or not i or (t, i) in cles:
                continue
            cles.append((t, i))
        if not cles:
            raise self._error(422, "Choisissez au moins une personne ou un groupe.")
        if test and any(t == "group" for t, _ in cles):
            raise self._error(409, "En Validé, le fichier part seulement aux relecteurs : choisissez-les un par un.")
        gens = self.docs.directory.recipients(db, member.org_id, cles)
        if test and len(gens) > MAX_REVIEWERS:
            raise self._error(409, f"En Validé, {MAX_REVIEWERS} relecteurs au plus.")
        return gens

    def preview(self, db: Session, member: Member, node_id: int, principals) -> dict:
        """Le récapitulatif avant « Envoyer »."""
        _, test = self._ready(db, member, node_id)
        gens = self._recipients(db, member, principals, test)
        return {
            "test": test,
            "available": self._mailer_ok(),
            "count": sum(1 for g in gens if g.email),
            "without_email": [g.name for g in gens if not g.email],
            # Qui reçoit, nommément (Seb : « ce n'est pas clair à qui »).
            "recipients": [{"name": g.name, "email": g.email} for g in gens if g.email],
        }

    def _mailer_ok(self) -> bool:
        return self.docs.mailer is not None and self.docs.mailer.available

    # ------------------------------------------------------------------
    # Essai sur soi-même (Seb, 16 octobre)
    # ------------------------------------------------------------------

    def trial(self, db: Session, member: Member, node_id: int) -> tuple[dict, list[dict]]:
        """Envoie le fichier à soi-même, dans tous les états : on reçoit le
        mail, on répond par son lien, la réponse arrive dans Résultats comme
        un essai (elle ne compte pas). Le même lien resert à chaque essai."""
        node = self.apps._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_MANAGE)
        version = self.apps.current_version(db, node)
        if version is None or not version.content.get("entry", {}).get("blocks"):
            raise self._error(409, "Le formulaire d'entrée est vide.")
        if not self._mailer_ok():
            raise self._error(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
        # L'adresse de connexion d'abord ; sinon celle de sa fiche dans l'école.
        trouves = self.docs.directory.recipients(db, member.org_id, [("member", str(member.person_id))])
        nom = trouves[0].name if trouves else member.display_name
        email = member.email or (trouves[0].email if trouves else None)
        if not email:
            raise self._error(409, "Votre fiche n'a pas d'adresse email.")
        s = db.scalar(
            select(DocSend).where(DocSend.node_id == node.id, DocSend.channel == "trial", DocSend.person_id == member.person_id)
        )
        if s is None:
            s = DocSend(
                org_id=node.org_id, node_id=node.id, token=secrets.token_urlsafe(24), person_id=member.person_id,
                channel="trial", test=True,
            )
            db.add(s)
        s.name, s.email, s.status, s.error, s.sent_by = nom, email, "pending", None, member.person_id
        self.docs._log(db, member, node, "sent", {"count": 1, "test": True, "trial": True})
        db.commit()
        ecole, adresse = self.docs.mailer.org(db, node.org_id)
        sujet, texte, html = compose(
            node.name, node.family, version.content, s.name, "", f"{adresse}/r/{s.token}",
            ecole, member.display_name, True, False, trial=True,
        )
        job = {"send_id": s.id, "to": s.email, "subject": sujet, "text": texte, "html": html,
               "sender_name": ecole, "reply_to": None}
        return {"sent": 1, "test": True, "email": s.email}, [job]

    # ------------------------------------------------------------------
    # Envoyer
    # ------------------------------------------------------------------

    def send(self, db: Session, member: Member, node_id: int, principals, message: str | None) -> tuple[dict, list[dict]]:
        """Crée les envois et rend (récapitulatif, emails à faire partir)."""
        node, test = self._ready(db, member, node_id)
        gens = [g for g in self._recipients(db, member, principals, test) if g.email]
        if not self._mailer_ok():
            raise self._error(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
        if not gens:
            raise self._error(409, "Personne n'a d'adresse email parmi les personnes choisies.")
        mailer = self.docs.mailer
        ecole, adresse = mailer.org(db, node.org_id)
        moi = self.docs.directory.recipients(db, member.org_id, [("member", str(member.person_id))])
        reply_to = moi[0].email if moi and moi[0].email else None
        version = self.apps.current_version(db, node)
        message = (message or "").strip()[:MAX_MESSAGE]

        deja = {
            s.person_id: s
            for s in db.scalars(select(DocSend).where(DocSend.node_id == node.id, DocSend.test.is_(test), DocSend.channel == "email"))
        }
        envois = []
        for g in gens:
            s = deja.get(g.person_id)
            if s is None:
                s = DocSend(
                    org_id=node.org_id, node_id=node.id, token=secrets.token_urlsafe(24), person_id=g.person_id,
                    channel="email", test=test,
                )
                db.add(s)
            s.name, s.email, s.status, s.error, s.sent_by = g.name, g.email, "pending", None, member.person_id
            envois.append(s)
        self.docs._log(db, member, node, "sent", {"count": len(envois), "test": test})
        db.commit()

        jobs = []
        for s in envois:
            sujet, texte, html = compose(
                node.name, node.family, version.content, s.name, message, f"{adresse}/r/{s.token}",
                ecole, member.display_name, test, bool(reply_to),
            )
            jobs.append({"send_id": s.id, "to": s.email, "subject": sujet, "text": texte, "html": html,
                         "sender_name": ecole, "reply_to": reply_to})
        return {"sent": len(envois), "test": test}, jobs

    def deliver(self, bind, jobs: list[dict]) -> None:
        """Fait partir les emails (après la réponse) et note le résultat."""
        with Session(bind=bind) as db:
            for job in jobs:
                s = db.get(DocSend, job["send_id"])
                if s is None:
                    continue
                try:
                    self.docs.mailer.send(job["to"], job["subject"], job["text"], job["html"], job["sender_name"], job["reply_to"])
                    s.status, s.sent_at, s.error = "sent", utcnow(), None
                except Exception as erreur:  # noqa: BLE001 (on note l'échec, on continue)
                    logger.warning("Diffuser : échec de l'envoi à %s : %s", job["to"], erreur)
                    s.status, s.error = "failed", str(erreur)[:255] or "Échec de l'envoi"
                db.commit()

    def list(self, db: Session, member: Member, node_id: int) -> dict:
        node = self.apps._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_MANAGE)
        envois = db.scalars(select(DocSend).where(DocSend.node_id == node.id).order_by(DocSend.name, DocSend.id))
        return {
            "items": [
                {
                    "id": s.id,
                    "name": s.name,
                    "email": s.email,
                    "test": s.test,
                    "trial": s.channel == "trial",
                    "status": s.status,
                    "error": s.error,
                    "sent_at": s.sent_at.isoformat() if s.sent_at else None,
                    "opened_at": s.opened_at.isoformat() if s.opened_at else None,
                    "answered_at": s.answered_at.isoformat() if s.answered_at else None,
                }
                for s in envois
            ],
            "available": self._mailer_ok(),
        }

    # ------------------------------------------------------------------
    # Le lien personnel (route publique, sans compte)
    # ------------------------------------------------------------------

    def _link(self, db: Session, token: str) -> tuple[DocSend, DocNode]:
        s = db.scalar(select(DocSend).where(DocSend.token == token)) if token else None
        node = db.get(DocNode, s.node_id) if s is not None else None
        if s is None or node is None or node.deleted_at is not None:
            raise self._error(404, "Ce lien ne mène plus à rien.")
        return s, node

    @staticmethod
    def _accepting(s: DocSend, node: DocNode) -> bool:
        if node.family == "inform":
            return False
        # Un essai sur soi-même reste ouvert, quel que soit l'état.
        if s.channel == "trial":
            return True
        # Un lien de relecture se ferme quand le fichier passe en Officiel.
        return node.status == ("validated" if s.test else "official")

    def link_page(self, db: Session, token: str) -> dict:
        s, node = self._link(db, token)
        version = self.apps.current_version(db, node)
        if version is None:
            raise self._error(404, "Ce lien ne mène plus à rien.")
        if s.opened_at is None:
            s.opened_at = utcnow()
            db.commit()
        reponse = db.get(DocResponse, s.response_id) if s.response_id else None
        return {
            "org_id": node.org_id,
            "name": node.name,
            "family": node.family,
            "person": s.name,
            "test": s.test,
            "trial": s.channel == "trial",
            "content": {"schema": version.content.get("schema", 1), "entry": version.content.get("entry", {"blocks": []})},
            "accepting": self._accepting(s, node),
            "values": reponse.values if reponse is not None else None,
        }

    def link_answer(self, db: Session, token: str, values) -> dict:
        s, node = self._link(db, token)
        if not self._accepting(s, node):
            raise self._error(409, "Les réponses sont fermées.")
        version = self.apps.current_version(db, node)
        try:
            gardees = app_content.check_values(version.content, values, test=s.test)
        except ContentError as erreur:
            raise self._error(422, str(erreur)) from erreur
        reponse = db.get(DocResponse, s.response_id) if s.response_id else None
        if reponse is None:
            reponse = DocResponse(
                org_id=node.org_id, node_id=node.id, person_id=s.person_id, email=s.email,
                is_test=s.test, source="link", status="answered",
            )
            db.add(reponse)
        reponse.version_id, reponse.values, reponse.updated_at = version.id, gardees, utcnow()
        db.flush()
        s.response_id, s.answered_at = reponse.id, utcnow()
        db.commit()
        return {"ok": True}


def compose(
    name: str, family: str, content: dict, person: str, message: str, link: str,
    org_name: str, sender: str, test: bool, can_reply: bool, trial: bool = False,
) -> tuple[str, str, str]:
    """L'email : une version lisible du formulaire d'entrée (tout le texte
    pour un fichier à lire, l'introduction sinon) et le lien personnel,
    écrit en clair (auth/mails.py : Brevo réécrit les liens cliquables)."""
    sujet = ("[Essai] " if trial else "[Relecture] " if test else "") + name
    paragraphes = [message] if message else []
    paragraphes += app_content.readable(content, intro_only=family != "inform")
    if trial:
        paragraphes.append(
            "Essai : vous vous êtes envoyé ce fichier pour voir ce que recevront les autres. "
            "Votre réponse est un essai : elle apparaîtra dans Résultats avec la mention « Essai », sans compter."
        )
    elif test:
        paragraphes.append(
            f"Relecture : {sender} vous demande de vérifier ce fichier avant son envoi. "
            "Vos réponses sont des essais, elles ne comptent pas."
        )
    bouton = BUTTONS.get(family, "Ouvrir")
    fin = ["Ce lien vous est personnel : ne le transférez à personne."]
    fin.append(
        f"Message envoyé par {sender} pour {org_name}."
        + (" Pour lui écrire, répondez simplement à ce mail." if can_reply else "")
    )
    texte = "\n\n".join([f"Bonjour {person},", *paragraphes, f"{bouton} :\n{link}", *fin]) + "\n"
    p = '<p style="margin:0 0 16px;white-space:pre-line">{}</p>'
    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#222;max-width:520px">'
        + f'<p style="margin:0 0 16px;font-size:20px;font-weight:bold">{escape(name)}</p>'
        + p.format(f"Bonjour {escape(person)},")
        + "".join(p.format(escape(x)) for x in paragraphes)
        + f'<p style="margin:24px 0 4px;font-weight:bold">{escape(bouton)} :</p>'
        + f'<p style="margin:0 0 24px;word-break:break-all">{escape(link)}</p>'
        + "".join(f'<p style="margin:0 0 8px;font-size:13px;color:#777">{escape(x)}</p>' for x in fin)
        + "</div>"
    )
    return sujet, texte, html

