"""Office file previews: Word, Excel, PowerPoint (and their OpenDocument
equivalents) converted to PDF by LibreOffice running headless, so the
existing PDF viewer can show them. One conversion per stored content
(cached by its sha256), one conversion at a time (the server is small).
Without LibreOffice installed, no preview: the file can still be
downloaded."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

TEXT_DOCUMENTS = {".doc", ".docx", ".odt", ".rtf"}
SPREADSHEETS = {".xls", ".xlsx", ".ods"}
PRESENTATIONS = {".ppt", ".pptx", ".odp"}
OFFICE = TEXT_DOCUMENTS | SPREADSHEETS | PRESENTATIONS

TIMEOUT_SECONDS = 120
_one_at_a_time = threading.Lock()


def extension(name: str) -> str:
    point = name.rfind(".")
    return name[point:].lower() if point > 0 else ""


def can_preview(name: str) -> bool:
    return extension(name) in OFFICE


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def convert_to_pdf(source: Path, name: str, target: Path) -> bool:
    """Writes the PDF preview of `source` (a stored file, named `name`) to
    `target`. False if LibreOffice is missing or the conversion fails."""
    programme = soffice()
    ext = extension(name)
    if programme is None or ext not in OFFICE:
        return False
    # A spreadsheet sheet on a single page: easier to read than a table cut
    # into many printed pages.
    filtre = "pdf"
    if ext in SPREADSHEETS:
        filtre = 'pdf:calc_pdf_Export:{"SinglePageSheets":{"type":"boolean","value":"true"}}'
    with _one_at_a_time, tempfile.TemporaryDirectory(prefix="apercu-") as dossier:
        travail = Path(dossier)
        # Stored files have no extension: LibreOffice needs it to know the format.
        entree = travail / f"document{ext}"
        shutil.copyfile(source, entree)
        try:
            resultat = subprocess.run(
                [
                    programme, "--headless", "--norestore", "--nolockcheck",
                    f"-env:UserInstallation=file://{travail / 'profil'}",
                    "--convert-to", filtre, "--outdir", str(travail), str(entree),
                ],
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        pdf = travail / "document.pdf"
        if resultat.returncode != 0 or not pdf.exists() or pdf.stat().st_size == 0:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(pdf, target)
        return True
