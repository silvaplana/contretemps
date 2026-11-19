"""Le passage d'un import (spec/modules/import-auto-pieces.md §5) : lister
la source, écarter ce qui est déjà vu ou hors saison, déposer une copie dans
la destination s'il y en a une, créer la pièce À valider par le service des
pièces (`notes_frais`), noter le fichier comme vu.

Sources par composition : une fonction par nature de source qui rend des
`SourceFile` (docs, drive ; mail et helloasso aux étapes 5 et 6)."""

from __future__ import annotations

import hashlib
import io
import logging
import mimetypes
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AutoImportRule, AutoImportSeen

logger = logging.getLogger(__name__)
PARIS = ZoneInfo("Europe/Paris")
ACCEPTES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif", "application/pdf"}
NATURES = {"achat": "achat", "frais": "frais", "honoraires": "honoraires", "vente": None}
MAX_PAR_PASSAGE = 50  # le reste au passage suivant (lecture des pièces payante)


@dataclass
class SourceFile:
    key: str  # unique dans la source : chemin, identifiant du mail
    name: str
    modified: datetime | None
    read: Callable[[], bytes]
    # Où est le fichier quand il n'y a pas de destination (lien de la pièce).
    link: dict = field(default_factory=dict)
    mime: str = ""
    # Date de la pièce quand la source la connaît (versement HelloAsso).
    day: date | None = None
    nature: str | None = None  # imposée par la source (mail : d'après l'expéditeur)


class SkipRule(Exception):
    """L'import ne peut pas passer (source injoignable…) : message montré."""


def mime_of(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def due(rule: AutoImportRule, now: datetime) -> bool:
    """L'heure de cet import est-elle venue ? `now` en UTC."""
    if not rule.active:
        return False
    last = rule.last_run_at.replace(tzinfo=timezone.utc) if rule.last_run_at and rule.last_run_at.tzinfo is None else rule.last_run_at
    if rule.frequency == "hourly":
        return last is None or now - last >= timedelta(minutes=55)
    local = now.astimezone(PARIS)
    try:
        h, m = (int(x) for x in (rule.at_time or "07:00").split(":"))
        at = time(h, m)
    except ValueError:
        at = time(7, 0)
    if local.time() < at:
        return False
    last_local = last.astimezone(PARIS) if last else None
    if rule.frequency == "weekly":
        return last_local is None or local - last_local >= timedelta(days=7) - timedelta(hours=1)
    if rule.frequency == "monthly":
        return last_local is None or (last_local.year, last_local.month) != (local.year, local.month)
    return last_local is None or last_local.date() != local.date() or last_local.time() < at


class AutoImport:
    def __init__(self, notes, documents, drives=None, sources: dict | None = None) -> None:
        self.notes = notes
        self.documents = documents
        self.drives = drives
        # Sources en plus (mail, helloasso) : kind → fonction(db, rule) → [SourceFile].
        self.sources = sources or {}

    # --- Les imports d'une école ------------------------------------------

    @staticmethod
    def rules(db: Session, org_id: int) -> list[AutoImportRule]:
        return list(db.scalars(
            select(AutoImportRule).where(AutoImportRule.organization_id == org_id).order_by(AutoImportRule.id)
        ))

    @staticmethod
    def rule(db: Session, org_id: int, rule_id: int) -> AutoImportRule:
        rule = db.get(AutoImportRule, rule_id)
        if rule is None or rule.organization_id != org_id:
            raise LookupError("Import introuvable.")
        return rule

    @staticmethod
    def counts(db: Session, org_id: int) -> dict[int, int]:
        rows = db.execute(
            select(AutoImportSeen.rule_id, func.count(AutoImportSeen.note_id))
            .join(AutoImportRule, AutoImportRule.id == AutoImportSeen.rule_id)
            .where(AutoImportRule.organization_id == org_id, AutoImportSeen.note_id.is_not(None))
            .group_by(AutoImportSeen.rule_id)
        )
        return {rule_id: n for rule_id, n in rows}

    @staticmethod
    def note_ids(db: Session, rule: AutoImportRule) -> list[int]:
        return list(db.scalars(
            select(AutoImportSeen.note_id).where(AutoImportSeen.rule_id == rule.id, AutoImportSeen.note_id.is_not(None))
            .order_by(AutoImportSeen.id)
        ))

    def delete(self, db: Session, org_id: int, rule_id: int) -> None:
        """Efface l'import et ce qu'il a vu ; jamais les pièces (§3)."""
        rule = self.rule(db, org_id, rule_id)
        for seen in db.scalars(select(AutoImportSeen).where(AutoImportSeen.rule_id == rule.id)):
            db.delete(seen)
        db.delete(rule)
        db.commit()

    # --- Membres au nom desquels l'appli agit -----------------------------

    @staticmethod
    def _membre(rule: AutoImportRule):
        from notes_frais.ports import Membre

        return Membre(person_id=rule.created_by or 0, org_id=rule.organization_id, nom="Import auto pièces",
                      est_tresorier=True)

    @staticmethod
    def _docs_member(rule: AutoImportRule):
        from documents.ports import Member

        return Member(person_id=rule.created_by or 0, org_id=rule.organization_id, display_name="Import auto pièces",
                      is_admin=True, groups=frozenset({"role:admin", "role:tresorier"}), writes_closed_periods=True)

    # --- Sources ----------------------------------------------------------

    def _docs_files(self, db: Session, rule: AutoImportRule) -> list[SourceFile]:
        from documents.models import KIND_FILE, DocNode

        folder = db.get(DocNode, rule.source_ref or 0)
        if folder is None or folder.org_id != rule.organization_id or folder.deleted_at is not None:
            raise SkipRule("Le dossier source n'existe plus dans Docs.")
        member = self._docs_member(rule)
        files = []
        for node in db.scalars(select(DocNode).where(
            DocNode.parent_id == folder.id, DocNode.kind == KIND_FILE, DocNode.deleted_at.is_(None),
        ).order_by(DocNode.id)):
            def read(node_id=node.id):
                chemin, _, _ = self.documents.content(db, member, node_id)
                return chemin.read_bytes()

            files.append(SourceFile(
                key=f"docs:{node.id}", name=node.name, modified=node.updated_at or node.created_at, read=read,
                link={"doc_node_id": node.id}, mime=node.mime or mime_of(node.name),
            ))
        return files

    def _drive_files(self, db: Session, rule: AutoImportRule) -> list[SourceFile]:
        if self.drives is None or rule.source_ref is None:
            raise SkipRule("Le drive n'est pas connecté.")
        drive_id, org_id = rule.source_ref, rule.organization_id
        try:
            entries = self.drives.call(db, org_id, drive_id, lambda c: c.list(rule.source_path))
        except Exception as erreur:
            raise SkipRule(f"Le drive ne répond pas : {erreur}") from erreur
        files = []
        for e in entries:
            if e.is_dir:
                continue

            def read(path=e.path):
                return self.drives.call(db, org_id, drive_id, lambda c: c.read(path))

            files.append(SourceFile(
                key=f"drive:{drive_id}:{e.path}", name=e.name, modified=e.modified, read=read,
                link={"drive_id": drive_id, "drive_path": e.path}, mime=mime_of(e.name),
            ))
        return files

    def _files(self, db: Session, rule: AutoImportRule) -> list[SourceFile]:
        if rule.source_kind == "docs":
            return self._docs_files(db, rule)
        if rule.source_kind == "drive":
            return self._drive_files(db, rule)
        source = self.sources.get(rule.source_kind)
        if source is None:
            raise SkipRule("Cette source n'est pas encore proposée.")
        return source(db, rule)

    # --- Destination ------------------------------------------------------

    def _deposit(self, db: Session, rule: AutoImportRule, f: SourceFile, content: bytes) -> dict:
        """Une copie dans la destination ; le lien de la pièce."""
        if rule.target_kind == "docs":
            from documents.models import DocNode

            folder = db.get(DocNode, rule.target_ref or 0)
            if folder is None or folder.org_id != rule.organization_id or folder.deleted_at is not None:
                raise SkipRule("Le dossier de destination n'existe plus dans Docs.")
            node = self.documents.upload(db, self._docs_member(rule), folder.space, folder.id, f.name, io.BytesIO(content))
            return {"doc_node_id": node["id"]}
        if rule.target_kind == "drive":
            if self.drives is None or rule.target_ref is None:
                raise SkipRule("Le drive de destination n'est pas connecté.")
            path = self.drives.call(
                db, rule.organization_id, rule.target_ref,
                lambda c: c.write(rule.target_path, f.name, content, f.mime or mime_of(f.name)),
            )
            return {"drive_id": rule.target_ref, "drive_path": path}
        if not f.link:
            raise SkipRule("Cette source demande une destination.")
        return f.link

    # --- Saison -----------------------------------------------------------

    @staticmethod
    def _season(db: Session, rule: AutoImportRule) -> tuple[date, date] | None:
        if rule.season_id is None:
            return None
        from saisons.models import Saison
        from saisons.portee import toutes_saisons

        with toutes_saisons(db):
            saison = db.get(Saison, rule.season_id)
        return (saison.date_debut, saison.date_fin) if saison is not None else None

    # --- Le passage -------------------------------------------------------

    def run(self, db: Session, rule: AutoImportRule) -> int:
        """Le passage de cet import ; le nombre de pièces créées. Le message
        du passage est gardé sur l'import (`last_message`)."""
        created = 0
        try:
            created = self._run(db, rule)
            rule.last_message = (
                "Rien de nouveau" if created == 0 else f"{created} nouvelle{'s' if created > 1 else ''} "
                f"pièce{'s' if created > 1 else ''}, À valider dans Pièces"
            )
        except SkipRule as erreur:
            db.rollback()
            rule.last_message = str(erreur)[:300]
        rule.last_run_at = datetime.now(timezone.utc)
        db.commit()
        return created

    def _run(self, db: Session, rule: AutoImportRule) -> int:
        if NATURES.get(rule.nature) is None and rule.source_kind != "helloasso":
            raise SkipRule("Les ventes ne se saisissent pas encore dans Pièces : cet import attend.")
        files = self._files(db, rule)
        seen = set(db.scalars(select(AutoImportSeen.source_key).where(AutoImportSeen.rule_id == rule.id)))
        hashes = set(db.scalars(select(AutoImportSeen.sha256).where(
            AutoImportSeen.rule_id == rule.id, AutoImportSeen.sha256.is_not(None))))
        season = self._season(db, rule)
        created, done = 0, 0
        for f in files:
            if f.key in seen or done >= MAX_PAR_PASSAGE:
                continue
            day = f.day or (f.modified.date() if f.modified else None)
            if season and day and not (season[0] <= day <= season[1]):
                self._seen(db, rule, f.key, None, None)
                continue
            done += 1
            mime = f.mime or mime_of(f.name)
            if mime not in ACCEPTES:
                self._seen(db, rule, f.key, None, None)
                continue
            try:
                content = f.read()
            except Exception:
                logger.exception("Import auto %s : %s illisible", rule.id, f.key)
                continue
            sha = hashlib.sha256(content).hexdigest()
            if sha in hashes:  # le même fichier, déplacé ou renommé
                self._seen(db, rule, f.key, sha, None)
                continue
            link = self._deposit(db, rule, f, content)
            note = self.notes.etablir(
                db, self._membre(rule), nature=f.nature or NATURES.get(rule.nature) or "achat",
                fichier=(content, f.name, mime), jour=f.day, lien=link,
            )
            self._seen(db, rule, f.key, sha, getattr(note, "id", None))
            hashes.add(sha)
            created += 1
        return created

    @staticmethod
    def _seen(db: Session, rule: AutoImportRule, key: str, sha: str | None, note_id: int | None) -> None:
        db.add(AutoImportSeen(rule_id=rule.id, source_key=key[:500], sha256=sha, note_id=note_id))
        db.commit()

    def run_due(self, db: Session, now: datetime | None = None) -> int:
        """Tous les imports dont l'heure est venue (boucle du serveur)."""
        now = now or datetime.now(timezone.utc)
        total = 0
        from registry.activation import disabled

        for rule in list(db.scalars(select(AutoImportRule).where(AutoImportRule.active.is_(True)))):
            if "auto_import" in disabled(db, rule.organization_id):
                continue
            if due(rule, now):
                try:
                    total += self.run(db, rule)
                except Exception:
                    db.rollback()
                    logger.exception("Import auto %s : passage impossible", rule.id)
        return total
