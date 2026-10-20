"""Assemblées générales d'une saison (sous-module Assemblée générale,
spec/modules/financier.md §5), repris de Sambo Admin (generalassemblies/) :
la base du PowerPoint de l'AG.

Une AG (table fin_assemblies) a un nom, une saison, un état (brouillon,
validé, officiel : un seul officiel par saison et par organisation), des
consignes, un modèle et un coût cumulé. Elle garde au plus 3 PowerPoint
(voir KINDS), un par sorte :
- "modele" : le PowerPoint d'exemple dont on reprend la mise en page, envoyé
  depuis l'ordinateur ou copié d'une autre AG ;
- "genere" : le PowerPoint produit par le dernier calcul ;
- "modifie" : le PowerPoint retouché par le trésorier, renvoyé dans l'appli.
Un nouveau fichier remplace celui de la même sorte (table
fin_assembly_files, fichiers <storage>/<organisation>/<AG>/v<n>.pptx).

Exécuter un calcul (voir run), en arrière-plan :
1. bilan de la saison : l'officiel, sinon le validé, sinon le brouillon le
   plus récent (sous-module Bilan) ; aucun : refusé ;
2. PowerPoint modèle : celui de l'AG ; sinon le PowerPoint final de l'AG
   officielle de la saison précédente, sinon le modèle général de
   l'organisation (<storage>/<organisation>/modele.pptx) : il devient alors
   le modèle de l'AG ;
3. le texte des diapos du trésorier est écrit (voir assembly_ai.py) ;
4. l'appli le place dans le modèle (voir slides.fill) et vérifie que chaque
   montant écrit vient bien du bilan.
Le coût est noté à l'organisation (port `note_cost`, comme le bilan).
"""

from __future__ import annotations

import json
import shutil
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .ai import DEFAULT_MODEL, MODELS, AnalysisError
from .assembly_ai import Draft, Writer
from .models import OFFICIAL, STATES, VALIDATED, FinAssembly, FinAssemblyFile
from .ports import Member, Season
from .slides import SlidesError, amounts_in, check_amounts, fill, open_presentation, outline, texts, thumbnails

STATE_RANK = {"officiel": 0, "valide": 1, "brouillon": 2}
RUN_TIMEOUT = timedelta(minutes=20)
MAX_UPLOAD = 50 * 1024 * 1024
# Les 3 PowerPoint d'une AG : sorte -> origin en base (voir le haut du fichier).
KINDS = {"modele": "modele", "genere": "genere", "modifie": "envoye"}
KIND_LABELS = {"modele": "modèle", "genere": "produit", "modifie": "modifié"}
# PowerPoint final d'une AG : le modifié s'il existe, sinon le produit.
FINAL_KINDS = ("modifie", "genere")
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class AssemblyError(ValueError):
    """Données invalides (message affichable tel quel)."""


class AssemblyNotFoundError(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


class GeneralAssemblies:
    def __init__(
        self,
        storage_dir: str | Path,
        seasons: Callable[[Session, int], list[Season]],
        reports: Callable[[Session, Member, int], list[dict]],
        report: Callable[[Session, Member, int], dict],
        session_factory: Callable[[], Session] | None = None,
        note_cost: Callable[[Session, int, float, str], object] | None = None,
        writer: Writer | None = None,
        background: bool = True,
    ) -> None:
        """seasons(db, org_id) : les saisons, la plus ancienne en premier ;
        reports / report : liste des bilans d'une saison et bilan complet
        (FinancialReports.list / get) ; session_factory : session propre au
        calcul en arrière-plan ; note_cost(db, org_id, dollars, détail) :
        note le coût à l'organisation. background=False : calcul exécuté
        directement (tests)."""
        self.storage = Path(storage_dir)
        self.seasons = seasons
        self.reports = reports
        self.report = report
        self.session_factory = session_factory
        self.note_cost = note_cost
        self.writer = writer or Writer()
        self.background = background

    def _org_dir(self, org_id: int) -> Path:
        return self.storage / str(org_id)

    def _template_path(self, org_id: int) -> Path:
        """Modèle général de l'organisation."""
        return self._org_dir(org_id) / "modele.pptx"

    def _folder(self, row: FinAssembly) -> Path:
        return self._org_dir(row.org_id) / str(row.id)

    # ----- lecture -----

    def options(self, db: Session, member: Member, season_id: int | None) -> dict:
        """Modèles, états, et pour la saison : bilan et PowerPoint modèle que
        prendrait un calcul maintenant."""
        _check(member)
        sources: dict = {"report": None, "template": None}
        if season_id is not None:
            report = self._source_report(db, member, season_id)
            sources["report"] = report and {"id": report["id"], "name": report["name"], "state": report["state"]}
            template = self._template(db, member, season_id)
            sources["template"] = template and template[1]
        return {
            "models": [{"id": key, "label": spec["label"]} for key, spec in MODELS.items()],
            "defaultModel": DEFAULT_MODEL,
            "states": [{"id": key, "label": label} for key, label in STATES.items()],
            "templateUploaded": self._template_path(member.org_id).exists(),
            **sources,
        }

    @staticmethod
    def counts(db: Session, member: Member) -> dict[int, int]:
        """Nombre d'AG par saison (affiché dans le choix de la saison)."""
        _check(member)
        rows = db.execute(
            select(FinAssembly.season_id, func.count()).where(FinAssembly.org_id == member.org_id).group_by(FinAssembly.season_id)
        ).all()
        return {season_id: count for season_id, count in rows}

    def list(self, db: Session, member: Member, season_id: int) -> list[dict]:
        _check(member)
        rows = db.scalars(
            select(FinAssembly)
            .where(FinAssembly.org_id == member.org_id, FinAssembly.season_id == season_id)
            .order_by(FinAssembly.id.desc())
        )
        return [self._summary(db, row) for row in rows]

    def get(self, db: Session, member: Member, assembly_id: int) -> dict:
        row = self._row(db, member, assembly_id)
        return {
            **self._summary(db, row),
            "prompt": row.prompt,
            "result": json.loads(row.result) if row.result else None,
            "files": self._files(db, row.id),
        }

    @staticmethod
    def _files(db: Session, assembly_id: int) -> dict:
        """Les 3 PowerPoint de l'AG : {"modele", "genere", "modifie"}, chacun
        {"kind", "filename", "source", "createdAt"} ou None."""
        rows = db.scalars(
            select(FinAssemblyFile).where(FinAssemblyFile.assembly_id == assembly_id).order_by(FinAssemblyFile.number)
        )
        latest = {row.origin: row for row in rows}
        return {
            kind: {
                "kind": kind,
                "filename": latest[origin].filename,
                "source": latest[origin].source,
                "createdAt": latest[origin].created_at.isoformat(timespec="seconds"),
            }
            if origin in latest
            else None
            for kind, origin in KINDS.items()
        }

    @staticmethod
    def _row(db: Session, member: Member, assembly_id: int) -> FinAssembly:
        _check(member)
        row = db.get(FinAssembly, assembly_id)
        if row is None or row.org_id != member.org_id:
            raise AssemblyNotFoundError(assembly_id)
        return row

    @staticmethod
    def _summary(db: Session, row: FinAssembly) -> dict:
        status, error = row.status, row.error
        if status == "running" and row.run_started_at is not None and row.run_started_at < _now() - RUN_TIMEOUT:
            status, error = "error", "Calcul interrompu (serveur redémarré) : relancez-le."
        ready = db.scalar(
            select(FinAssemblyFile.id).where(
                FinAssemblyFile.assembly_id == row.id, FinAssemblyFile.origin.in_(("genere", "envoye"))
            )
        )
        return {
            "id": row.id,
            "seasonId": row.season_id,
            "name": row.name,
            "state": row.state,
            "model": row.model,
            "modelLabel": MODELS.get(row.model, {}).get("label", row.model),
            "aiCostUsd": row.ai_cost_usd,
            "status": status,
            "error": error,
            # Un PowerPoint d'AG existe (produit ou modifié).
            "hasPpt": ready is not None,
            "updatedAt": row.updated_at.isoformat(timespec="seconds"),
        }

    # ----- écriture -----

    def create(self, db: Session, member: Member, data: dict) -> dict:
        _check(member)
        season_id = data.get("seasonId")
        if not any(s.id == season_id for s in self.seasons(db, member.org_id)):
            raise AssemblyError("Saison inconnue")
        name, state, prompt, model = self._validate(data)
        if state == OFFICIAL:
            self._demote_official(db, member.org_id, season_id)
        row = FinAssembly(org_id=member.org_id, season_id=season_id, name=name, state=state, prompt=prompt, model=model)
        db.add(row)
        db.commit()
        return self.get(db, member, row.id)

    def update(self, db: Session, member: Member, assembly_id: int, data: dict) -> dict:
        row = self._row(db, member, assembly_id)
        name, state, prompt, model = self._validate(data)
        if state == OFFICIAL:
            self._demote_official(db, member.org_id, row.season_id, assembly_id)
        row.name, row.state, row.prompt, row.model, row.updated_at = name, state, prompt, model, _now()
        db.commit()
        return self.get(db, member, assembly_id)

    def delete(self, db: Session, member: Member, assembly_id: int) -> None:
        row = self._row(db, member, assembly_id)
        folder = self._folder(row)
        db.execute(FinAssemblyFile.__table__.delete().where(FinAssemblyFile.assembly_id == assembly_id))
        db.delete(row)
        db.commit()
        shutil.rmtree(folder, ignore_errors=True)

    @staticmethod
    def _demote_official(db: Session, org_id: int, season_id: int, keep: int | None = None) -> None:
        """Une seule AG officielle par saison : l'ancienne repasse en validé."""
        db.execute(
            update(FinAssembly)
            .where(FinAssembly.org_id == org_id, FinAssembly.season_id == season_id, FinAssembly.state == OFFICIAL, FinAssembly.id != keep)
            .values(state=VALIDATED)
        )

    @staticmethod
    def _validate(data: dict) -> tuple[str, str, str, str]:
        name = (data.get("name") or "").strip()
        if not name:
            raise AssemblyError("Le nom est obligatoire")
        state = data.get("state") or "brouillon"
        if state not in STATES:
            raise AssemblyError(f"État inconnu : {state}")
        model = data.get("model") or DEFAULT_MODEL
        if model not in MODELS:
            raise AssemblyError(f"Modèle inconnu : {model}")
        return name, state, (data.get("prompt") or "").strip(), model

    # ----- fichiers -----

    def file_path(self, db: Session, member: Member, assembly_id: int, kind: str | None = None) -> tuple[Path, str]:
        """Fichier d'un des 3 PowerPoint de l'AG et son nom de téléchargement.
        kind None : le PowerPoint final (voir FINAL_KINDS)."""
        row = self._row(db, member, assembly_id)
        return self._file_of(db, row, kind)

    def _file_of(self, db: Session, row: FinAssembly, kind: str | None = None) -> tuple[Path, str]:
        if kind is not None and kind not in KINDS:
            raise AssemblyNotFoundError(kind)
        for candidate in (kind,) if kind else FINAL_KINDS:
            file = db.scalars(
                select(FinAssemblyFile)
                .where(FinAssemblyFile.assembly_id == row.id, FinAssemblyFile.origin == KINDS[candidate])
                .order_by(FinAssemblyFile.number.desc())
            ).first()
            if file is not None:
                return self._folder(row) / f"v{file.number}.pptx", file.filename
        raise AssemblyNotFoundError(row.id)

    def _set_file(self, db: Session, row: FinAssembly, kind: str, source: Path | bytes, filename: str, origin_text: str) -> None:
        """Enregistre un PowerPoint de l'AG, à la place de celui de la même
        sorte. origin_text : d'où il vient, en clair (affiché dans l'écran)."""
        origin = KINDS[kind]
        folder = self._folder(row)
        folder.mkdir(parents=True, exist_ok=True)
        number = (db.scalar(select(func.max(FinAssemblyFile.number)).where(FinAssemblyFile.assembly_id == row.id)) or 0) + 1
        target = folder / f"v{number}.pptx"
        if isinstance(source, bytes):
            target.write_bytes(source)
        else:
            shutil.move(str(source), target)
        replaced = list(
            db.scalars(
                select(FinAssemblyFile.number).where(FinAssemblyFile.assembly_id == row.id, FinAssemblyFile.origin == origin)
            )
        )
        db.execute(
            FinAssemblyFile.__table__.delete().where(FinAssemblyFile.assembly_id == row.id, FinAssemblyFile.origin == origin)
        )
        db.add(FinAssemblyFile(assembly_id=row.id, number=number, origin=origin, filename=filename, source=origin_text))
        row.updated_at = _now()
        db.commit()
        # Fichiers et images des diapos des PowerPoint remplacés.
        for old in replaced:
            (folder / f"v{old}.pptx").unlink(missing_ok=True)
            shutil.rmtree(folder / f"v{old}-apercu", ignore_errors=True)

    @staticmethod
    def _check_pptx(content: bytes, path: Path) -> None:
        if len(content) > MAX_UPLOAD:
            raise AssemblyError("Fichier trop gros (50 Mo au plus)")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        try:
            open_presentation(path)
        except SlidesError as exc:
            path.unlink(missing_ok=True)
            raise AssemblyError(str(exc)) from exc

    def upload(self, db: Session, member: Member, assembly_id: int, content: bytes, filename: str) -> dict:
        """PowerPoint modifié par le trésorier (remplace le précédent)."""
        row = self._row(db, member, assembly_id)
        tmp = self._folder(row) / "envoi.tmp"
        self._check_pptx(content, tmp)
        self._set_file(db, row, "modifie", tmp, filename or "ag.pptx", "Importé de votre ordinateur")
        return self.get(db, member, assembly_id)

    def set_model(self, db: Session, member: Member, assembly_id: int, content: bytes, filename: str) -> dict:
        """PowerPoint modèle de l'AG, envoyé depuis l'ordinateur."""
        row = self._row(db, member, assembly_id)
        tmp = self._folder(row) / "modele.tmp"
        self._check_pptx(content, tmp)
        self._set_file(db, row, "modele", tmp, filename or "modele.pptx", "Importé de votre ordinateur")
        return self.get(db, member, assembly_id)

    def copy_model(self, db: Session, member: Member, assembly_id: int, source_id: int | None, kind: str) -> dict:
        """PowerPoint modèle de l'AG, copié d'un PowerPoint d'une autre AG
        (source_id, kind : une sorte de KINDS) ou du modèle général de
        l'organisation (kind "general")."""
        row = self._row(db, member, assembly_id)
        if kind == "general":
            template = self._template_path(member.org_id)
            if not template.exists():
                raise AssemblyError("Il n'y a pas de modèle général")
            path, filename, origin_text = template, "Modèle général.pptx", "Copie du modèle général"
        else:
            if source_id is None or source_id == assembly_id or kind not in KINDS:
                raise AssemblyError("Choisissez un PowerPoint d'une autre AG")
            try:
                source = self._row(db, member, source_id)
                path, filename = self._file_of(db, source, kind)
            except AssemblyNotFoundError as exc:
                raise AssemblyError("Ce PowerPoint n'existe plus") from exc
            season = next((s.name for s in self.seasons(db, member.org_id) if s.id == source.season_id), "?")
            origin_text = f"Copie du PowerPoint {KIND_LABELS[kind]} de l'AG « {source.name} » ({season})"
        self._set_file(db, row, "modele", path.read_bytes(), filename, origin_text)
        return self.get(db, member, assembly_id)

    def model_sources(self, db: Session, member: Member, exclude: int | None = None) -> list[dict]:
        """PowerPoint qui peuvent servir de modèle : ceux de toutes les autres
        AG de l'organisation (toutes saisons, le plus récent d'abord), puis le
        modèle général s'il existe."""
        _check(member)
        names = {s.id: s.name for s in self.seasons(db, member.org_id)}
        rows = db.execute(
            select(FinAssemblyFile, FinAssembly.name, FinAssembly.season_id)
            .join(FinAssembly, FinAssembly.id == FinAssemblyFile.assembly_id)
            .where(FinAssembly.org_id == member.org_id, FinAssembly.id != exclude)
            .order_by(FinAssemblyFile.number)
        ).all()
        kinds = {origin: kind for kind, origin in KINDS.items()}
        latest = {(file.assembly_id, file.origin): (file, name, season_id) for file, name, season_id in rows if file.origin in kinds}
        sources = [
            {
                "assemblyId": file.assembly_id,
                "kind": kinds[file.origin],
                "label": f"{names.get(season_id, '?')}, {name} : PowerPoint {KIND_LABELS[kinds[file.origin]]}",
                "filename": file.filename,
                "createdAt": file.created_at.isoformat(timespec="seconds"),
            }
            for file, name, season_id in sorted(latest.values(), key=lambda r: (r[0].created_at, r[0].number), reverse=True)
        ]
        if self._template_path(member.org_id).exists():
            sources.append({"assemblyId": None, "kind": "general", "label": "Modèle général", "filename": "modele.pptx", "createdAt": None})
        return sources

    def set_template(self, member: Member, content: bytes) -> dict:
        """Modèle général de l'organisation : pris par une AG sans modèle,
        quand la saison précédente n'a pas d'AG officielle."""
        _check(member)
        tmp = self._org_dir(member.org_id) / "modele.tmp"
        self._check_pptx(content, tmp)
        tmp.replace(self._template_path(member.org_id))
        return {"templateUploaded": True}

    def _preview(self, db: Session, member: Member, assembly_id: int, kind: str) -> tuple[Path, Path]:
        path, _ = self.file_path(db, member, assembly_id, kind)
        return path, path.with_name(f"{path.stem}-apercu")

    def slides(self, db: Session, member: Member, assembly_id: int, kind: str) -> dict:
        """Aperçu d'un des 3 PowerPoint : textes de chaque diapo et, si
        LibreOffice (Impress) est installé, numéro de l'image de chaque diapo
        affichée."""
        path, folder = self._preview(db, member, assembly_id, kind)
        images = thumbnails(path, folder)
        result, index = [], 0
        for slide in texts(path):
            image = None
            if not slide["hidden"]:
                index += 1
                image = index if images and index <= len(images) else None
            result.append({**slide, "image": image})
        return {"slides": result, "thumbnails": images is not None}

    def thumbnail(self, db: Session, member: Member, assembly_id: int, kind: str, image: int) -> Path:
        images = thumbnails(*self._preview(db, member, assembly_id, kind)) or []
        if not 1 <= image <= len(images):
            raise AssemblyNotFoundError(image)
        return images[image - 1]

    # ----- sources du calcul -----

    def _source_report(self, db: Session, member: Member, season_id: int) -> dict | None:
        """Bilan de la saison : l'officiel, sinon le validé, sinon le brouillon
        le plus récent (liste déjà triée du plus récent)."""
        candidates = [r for r in self.reports(db, member, season_id) if r["hasResult"]]
        return min(candidates, key=lambda r: STATE_RANK[r["state"]], default=None)

    def _template(self, db: Session, member: Member, season_id: int) -> tuple[Path, dict] | None:
        """PowerPoint modèle par défaut d'une AG qui n'en a pas : le PowerPoint
        final de l'AG officielle de la saison précédente, sinon le modèle
        général."""
        seasons = self.seasons(db, member.org_id)
        index = next((i for i, s in enumerate(seasons) if s.id == season_id), None)
        if index:
            previous = seasons[index - 1]
            official = db.scalars(
                select(FinAssembly).where(
                    FinAssembly.org_id == member.org_id,
                    FinAssembly.season_id == previous.id,
                    FinAssembly.state == OFFICIAL,
                    FinAssembly.id.in_(
                        select(FinAssemblyFile.assembly_id).where(FinAssemblyFile.origin.in_(("genere", "envoye")))
                    ),
                )
            ).first()
            if official is not None:
                path, _ = self._file_of(db, official)
                return path, {"kind": "previous", "name": f"AG officielle {previous.name} ({official.name})"}
        template = self._template_path(member.org_id)
        if template.exists():
            return template, {"kind": "uploaded", "name": "Modèle général"}
        return None

    def _model(self, db: Session, member: Member, row: FinAssembly) -> tuple[Path, dict] | None:
        """PowerPoint modèle d'une AG : le sien, sinon celui par défaut."""
        try:
            path, filename = self._file_of(db, row, "modele")
        except AssemblyNotFoundError:
            return self._template(db, member, row.season_id)
        return path, {"kind": "own", "name": filename}

    # ----- calcul -----

    def run(self, db: Session, member: Member, assembly_id: int, data: dict) -> dict:
        row = self._row(db, member, assembly_id)
        if self._summary(db, row)["status"] == "running":
            raise AssemblyError("Un calcul est déjà en cours")
        if self._source_report(db, member, row.season_id) is None:
            raise AssemblyError("Aucun bilan calculé pour cette saison : produisez-le d'abord dans Bilan.")
        if self._model(db, member, row) is None:
            raise AssemblyError("Pas de PowerPoint modèle : choisissez d'abord le PowerPoint d'une AG précédente.")
        current = {"name": row.name, "state": row.state, "prompt": row.prompt, "model": row.model}
        name, state, prompt, model = self._validate({**current, **{k: v for k, v in data.items() if v is not None}})
        if state == OFFICIAL:
            self._demote_official(db, member.org_id, row.season_id, assembly_id)
        row.name, row.state, row.prompt, row.model = name, state, prompt, model
        row.status, row.error, row.run_started_at, row.updated_at = "running", None, _now(), _now()
        db.commit()
        if self.background and self.session_factory is not None:
            threading.Thread(target=self._execute_in_own_session, args=(member, assembly_id), daemon=True).start()
        else:
            self._execute(db, member, assembly_id)
        return self.get(db, member, assembly_id)

    def _execute_in_own_session(self, member: Member, assembly_id: int) -> None:
        db = self.session_factory()
        try:
            self._execute(db, member, assembly_id)
        finally:
            db.close()

    def _execute(self, db: Session, member: Member, assembly_id: int) -> None:
        row = self._row(db, member, assembly_id)
        cost = 0.0
        try:
            seasons = self.seasons(db, member.org_id)
            index = next(i for i, s in enumerate(seasons) if s.id == row.season_id)
            season = seasons[index]
            source = self._source_report(db, member, season.id)
            if source is None:
                raise AssemblyError("Aucun bilan calculé pour cette saison.")
            report = self.report(db, member, source["id"])
            template, template_info = self._model(db, member, row)
            if template_info["kind"] != "own":
                # Modèle par défaut : il devient le modèle de l'AG.
                self._set_file(
                    db,
                    row,
                    "modele",
                    template.read_bytes(),
                    f"{template_info['name']}.pptx",
                    f"Pris par défaut, faute de modèle choisi : {template_info['name']}",
                )
                template, _ = self._file_of(db, row, "modele")
            data = self._ai_data(seasons, index, report, outline(template))
            draft: Draft = self.writer.write(row.model, data, row.prompt)
            cost = draft.cost
            output = self._folder(row) / "calcul.tmp"
            output.parent.mkdir(parents=True, exist_ok=True)
            changed = fill(template, output, draft.zones)
            warnings = check_amounts(draft.zones, self._known_amounts(report["result"]) | set(amounts_in(row.prompt)))
            self._set_file(
                db,
                row,
                "genere",
                output,
                f"AG-{season.name}-{row.name}.pptx",
                f"Produit par {MODELS[draft.model]['label']} à partir du PowerPoint modèle",
            )
            row.result = json.dumps(
                {
                    "report": {"id": report["id"], "name": report["name"], "state": report["state"]},
                    "template": template_info,
                    "changedSlides": changed,
                    "summary": draft.summary,
                    "warnings": warnings,
                    "model": draft.model,
                    "modelLabel": MODELS[draft.model]["label"],
                    "servedBy": draft.served_by,
                    "costUsd": cost,
                    "generatedAt": _now().isoformat(timespec="seconds"),
                },
                ensure_ascii=False,
            )
            row.status, row.error = "idle", None
        except Exception as exc:  # noqa: BLE001 - tout échec doit sortir le calcul de l'état « en cours »
            db.rollback()
            row = self._row(db, member, assembly_id)
            cost = exc.cost if isinstance(exc, AnalysisError) else cost
            row.status = "error"
            row.error = str(exc) if isinstance(exc, (AnalysisError, AssemblyError, SlidesError)) else f"Le calcul a échoué : {exc}"
        row.ai_cost_usd += cost
        row.updated_at = _now()
        db.commit()
        if cost and self.note_cost is not None:
            self.note_cost(db, member.org_id, cost, f"AG {row.name}")

    @staticmethod
    def _known_amounts(result: dict) -> set[float]:
        """Montants du bilan (et de la saison précédente) que le texte peut citer."""
        amounts = {result.get(k) for k in ("opening", "closing", "totalIncome", "totalExpense", "result")}
        amounts |= {r["amount"] for r in result.get("income", []) + result.get("expense", [])}
        amounts |= set(result.get("net", {}).values())
        previous = result.get("previous") or {}
        amounts |= {previous.get(k) for k in ("opening", "closing", "totalIncome", "totalExpense", "result")}
        amounts |= set((previous.get("net") or {}).values())
        return {a for a in amounts if a is not None}

    @staticmethod
    def _ai_data(seasons: list[Season], index: int, report: dict, template: list[dict]) -> dict:
        """Données envoyées au modèle (noms de champs en français : il les lit)."""
        season = seasons[index]
        result = report["result"]
        previous = result.get("previous")
        following = seasons[index + 1].name if index + 1 < len(seasons) else None
        if following is None and season.name[:4].isdigit():
            start = int(season.name[:4])
            following = f"{start + 1}-{start + 2}"
        return {
            "saison": season.name,
            "saisonSuivante": following,
            "bilan": {
                "nom": report["name"],
                "etat": report["state"],
                "debutSaison": result["start"],
                "finSaison": result["end"],
                "dateArret": result["cutoff"],
                "saisonTerminee": result["cutoff"] >= result["end"],
                "soldeDebut": result["opening"],
                "soldeFin": result["closing"],
                "recettes": {r["category"]: r["amount"] for r in result["income"]},
                "depenses": {r["category"]: r["amount"] for r in result["expense"]},
                "totalRecettes": result["totalIncome"],
                "totalDepenses": result["totalExpense"],
                "resultat": result["result"],
                "verificationDesSoldesOk": result["verification"]["ok"],
                "analyse": result.get("analysis", []),
                "saisonPrecedente": previous
                and {
                    "saison": previous["season"],
                    "soldeDebut": previous["opening"],
                    "soldeFin": previous["closing"],
                    "totalRecettes": previous["totalIncome"],
                    "totalDepenses": previous["totalExpense"],
                    "resultat": previous["result"],
                    "recettesEtDepensesNettesParCategorie": previous["net"],
                },
            },
            "inscrits": [{"saison": s.name, "inscrits": s.members} for s in seasons[: index + 1]],
            "modele": template,
        }
