"""Routes de la boîte mail de l'école (spec/modules/mail.md §3 à §6).
Lire l'état et les mails, les ranger : droit « Boîte mail du club ».
Connecter et déconnecter : l'Administrateur principal qui a ce droit (et le
Super User). Routes synchrones (IMAP bloquant) : FastAPI les exécute dans un
thread à part."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal
from datetime import datetime
from urllib.parse import quote

from comptes import Compte, rbac, roles
from ecoles.models import Ecole
from fastapi import Depends, FastAPI, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .connection import Connection, NotConnected
from .gmail import MailError, MailRefused
from .imap import SEND_MAX_BYTES, Webmail, WebmailError, WebmailNotFoundError, WebmailRefusedError

RIGHT = "mail.read"


class ConnectIn(BaseModel):
    address: str = Field(min_length=3, max_length=255, pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$")
    code: str = Field(min_length=1, max_length=100)
    provider: Literal["gmail", "infomaniak"] = "gmail"


class StatusOut(BaseModel):
    connected: bool
    address: str | None = None
    provider: str | None = None
    connected_at: datetime | None = None
    # Google a coupé l'accès : bandeau « Reconnecter ».
    cut: bool = False
    # Administrateur principal (ou Super User) : connecter, déconnecter.
    can_connect: bool = False
    # Droit « Boîte mail du club » : puce Mail dans Messages.
    can_read: bool = False


class FlagsIn(BaseModel):
    """Lu, suivi (absent : inchangé)."""

    seen: bool | None = None
    starred: bool | None = None


class MoveIn(BaseModel):
    to: str  # inbox, archive, trash, spam


class BulkIn(BaseModel):
    """Mails cochés dans la liste et action (trash, archive, spam, inbox,
    delete, read, unread)."""

    folder: str
    uids: list[int]
    action: str


def _reader(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    rbac.require_membre(appelant, ecole_id)
    if not _can_read(appelant):
        raise HTTPException(status_code=403, detail="Réservé aux personnes qui ont le droit « Boîte mail du club »")


def _owner(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    """Connecter, déconnecter : Admin › Fonctionnalités, ligne Mail (Seb,
    18 novembre), sans avoir besoin du droit de lire les mails."""
    rbac.require_membre(appelant, ecole_id)
    if appelant is not None and not roles.is_superuser(appelant):
        rbac.require_owner(appelant, ecole_id)


def _reader_or_owner(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    if _can_connect(appelant):
        rbac.require_membre(appelant, ecole_id)
    else:
        _reader(ecole_id, appelant)


def _can_read(appelant: Compte | None) -> bool:
    return appelant is None or roles.has_right(appelant, RIGHT)


def _can_connect(appelant: Compte | None) -> bool:
    return appelant is None or roles.is_superuser(appelant) or roles.is_owner(appelant)


class MailReceiver:
    def __init__(self, connection: Connection, app: FastAPI) -> None:
        self.connection = connection
        app.get("/ecoles/{ecole_id}/mail", response_model=StatusOut, dependencies=[Depends(_reader_or_owner)])(self.status)
        owner = [Depends(_owner)]
        app.put("/ecoles/{ecole_id}/mail", response_model=StatusOut, dependencies=owner)(self.connect)
        app.delete("/ecoles/{ecole_id}/mail", status_code=204, dependencies=owner)(self.disconnect)
        reader = [Depends(_reader)]
        base = "/ecoles/{ecole_id}/mail"
        app.get(f"{base}/folders", dependencies=reader)(self.folders)
        app.get(f"{base}/unread", dependencies=reader)(self.unread)
        app.get(f"{base}/messages", dependencies=reader)(self.messages)
        app.get(f"{base}/messages/{{folder}}/{{uid}}", dependencies=reader)(self.message)
        app.get(f"{base}/messages/{{folder}}/{{uid}}/attachments/{{index}}", dependencies=reader)(self.attachment)
        app.put(f"{base}/messages/{{folder}}/{{uid}}/flags", dependencies=reader)(self.flags)
        app.post(f"{base}/messages/{{folder}}/{{uid}}/move", dependencies=reader)(self.move)
        app.delete(f"{base}/messages/{{folder}}/{{uid}}", dependencies=reader)(self.delete)
        app.post(f"{base}/bulk", dependencies=reader)(self.bulk)
        app.post(f"{base}/send", dependencies=reader)(self.send)

    def _status(self, db: Session, ecole_id: int, appelant: Compte | None) -> StatusOut:
        account = self.connection.account(db, ecole_id)
        if account is None:
            return StatusOut(connected=False, can_connect=_can_connect(appelant), can_read=_can_read(appelant))
        return StatusOut(
            connected=True, address=account.address, provider=account.provider, connected_at=account.connected_at,
            cut=account.cut_at is not None, can_connect=_can_connect(appelant), can_read=_can_read(appelant),
        )

    def status(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte | None = Depends(rbac.compte_appelant)):
        return self._status(db, ecole_id, appelant)

    def connect(
        self, ecole_id: int, data: ConnectIn, db: Session = Depends(get_db),
        appelant: Compte | None = Depends(rbac.compte_appelant),
    ):
        try:
            self.connection.connect(db, ecole_id, data.address, data.code, data.provider)
        except MailRefused as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        except MailError as erreur:
            raise HTTPException(status_code=502, detail=str(erreur)) from None
        return self._status(db, ecole_id, appelant)

    def disconnect(self, ecole_id: int, db: Session = Depends(get_db)):
        self.connection.disconnect(db, ecole_id)

    # --- Lire et ranger (§5, §6) ------------------------------------------

    def _call(self, db: Session, ecole_id: int, action: Callable[[Webmail], object]):
        try:
            return action(self.connection.client(db, ecole_id))
        except NotConnected:
            raise HTTPException(status_code=409, detail="La boîte mail du club n'est pas connectée") from None
        except WebmailRefusedError as erreur:
            self.connection.mark_cut(db, ecole_id)
            raise HTTPException(status_code=409, detail=str(erreur)) from None
        except WebmailError as erreur:
            raise HTTPException(status_code=400, detail=str(erreur)) from None
        except WebmailNotFoundError:
            raise HTTPException(status_code=404, detail="Mail introuvable (déplacé ou supprimé ?)") from None

    def folders(self, ecole_id: int, db: Session = Depends(get_db)):
        """Dossiers de la boîte et non lus de la réception."""
        return self._call(db, ecole_id, lambda w: w.folders())

    def unread(self, ecole_id: int, db: Session = Depends(get_db)):
        """Pastille des non lus : 0 si la boîte n'est pas lisible."""
        try:
            return {"unread": self._call(db, ecole_id, lambda w: w.unread())}
        except HTTPException:
            return {"unread": 0}

    def messages(
        self, ecole_id: int, folder: str = "inbox", before: int | None = None, q: str = "",
        db: Session = Depends(get_db),
    ):
        """Une page de 40 mails (q : recherche, mots-clés de Gmail)."""
        return self._call(db, ecole_id, lambda w: w.list(folder, before, q))

    def message(self, ecole_id: int, folder: str, uid: int, db: Session = Depends(get_db)):
        """Un mail complet ; le marque comme lu."""
        return self._call(db, ecole_id, lambda w: w.get(folder, uid))

    def attachment(self, ecole_id: int, folder: str, uid: int, index: int, db: Session = Depends(get_db)):
        """Pièce jointe, toujours en téléchargement (jamais affichée par le
        navigateur sur le domaine de l'appli)."""
        data, filename, _content_type = self._call(db, ecole_id, lambda w: w.attachment(folder, uid, index))
        ascii_name = filename.encode("ascii", "replace").decode("ascii").replace('"', "_").replace("?", "_")
        return Response(
            data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    def flags(self, ecole_id: int, folder: str, uid: int, data: FlagsIn, db: Session = Depends(get_db)):
        return self._call(db, ecole_id, lambda w: w.set_flags(folder, uid, data.seen, data.starred))

    def move(self, ecole_id: int, folder: str, uid: int, data: MoveIn, db: Session = Depends(get_db)):
        return self._call(db, ecole_id, lambda w: w.move(folder, uid, data.to))

    def delete(self, ecole_id: int, folder: str, uid: int, db: Session = Depends(get_db)):
        """Suppression définitive (corbeille ou spam seulement)."""
        return self._call(db, ecole_id, lambda w: w.delete(folder, uid))

    def bulk(self, ecole_id: int, data: BulkIn, db: Session = Depends(get_db)):
        return self._call(db, ecole_id, lambda w: w.bulk(data.folder, data.uids, data.action))

    # --- Écrire (§7) --------------------------------------------------------

    def send(
        self,
        ecole_id: int,
        to: str = Form(""),
        cc: str = Form(""),
        bcc: str = Form(""),
        subject: str = Form(""),
        body: str = Form(""),
        inReplyTo: str = Form(""),
        references: str = Form(""),
        answeredFolder: str = Form(""),
        answeredUid: int | None = Form(None),
        forwardFolder: str = Form(""),
        forwardUid: int | None = Form(None),
        files: list[UploadFile] | None = None,
        db: Session = Depends(get_db),
    ):
        """Envoie au nom du club (formulaire multipart, comme Sambo Admin).
        Réponse : answered* (marqué « répondu ») ; transfert : forward*
        (pièces jointes du mail reprises). L'Annuler de 10 s est à l'écran :
        la demande part à la fin."""
        attachments, total = [], 0
        for upload in files or []:
            data = upload.file.read()
            total += len(data)
            if total > SEND_MAX_BYTES:
                raise HTTPException(status_code=400, detail="Pièces jointes trop lourdes (18 Mo au total au maximum)")
            attachments.append((upload.filename or "piece-jointe", upload.content_type or "", data))
        ecole = db.get(Ecole, ecole_id)

        def envoyer(w: Webmail):
            w.sender_name = ecole.nom if ecole else ""
            return w.send(
                to=to, cc=cc, bcc=bcc, subject=subject, body=body, in_reply_to=inReplyTo, references=references,
                attachments=attachments,
                forward=(forwardFolder, forwardUid) if forwardFolder and forwardUid is not None else None,
                answered=(answeredFolder, answeredUid) if answeredFolder and answeredUid is not None else None,
            )

        return self._call(db, ecole_id, envoyer)
