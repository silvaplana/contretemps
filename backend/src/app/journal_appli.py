"""Journal de l'appli (Seb, 20/11/2026 : « des fois il y a 0 élève, il faut
fermer et relancer l'appli »). Le téléphone note chaque demande au serveur
qui échoue, puis les envoie ici dès que la connexion revient
(frontend/src/utils/journalAppli.js). Rangé dans un fichier à côté de la
base (volume /app/data en prod), pas dans une table : rien à migrer, et il
survit aux mises en ligne.

    POST /journal/appli          les lignes notées par le téléphone
    python -m app.journal_appli  les 200 dernières lignes (lecture seule)
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

PATH = "/journal/appli"
# Au-delà, on ne garde que la seconde moitié : le fichier reste petit.
MAX_BYTES = 1_000_000


class Entry(BaseModel):
    at: str = Field(max_length=40)
    method: str = Field(max_length=10)
    path: str = Field(max_length=300)
    reason: str = Field(max_length=300)


def log_file() -> Path:
    explicit = os.environ.get("FICHIER_JOURNAL_APPLI")
    if explicit:
        return Path(explicit)
    url = os.environ.get("DATABASE_URL", "sqlite:///./contretemps.db")
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///")).resolve().parent / "journal-appli.log"
    return Path("journal-appli.log")


def _clean(text: str) -> str:
    return " ".join(text.split())


def append(member_id: str, entries: list[Entry]) -> None:
    file = log_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    received = datetime.now().isoformat(timespec="seconds")
    lines = "".join(
        f"{received} | fiche {_clean(member_id)} | {_clean(e.at)} | {_clean(e.method)} {_clean(e.path)} | {_clean(e.reason)}\n"
        for e in entries
    )
    with file.open("a", encoding="utf-8") as f:
        f.write(lines)
    if file.stat().st_size > MAX_BYTES:
        kept = file.read_text(encoding="utf-8")[-MAX_BYTES // 2 :]
        file.write_text(kept[kept.find("\n") + 1 :], encoding="utf-8")


def install(app: FastAPI) -> None:
    # Session obligatoire, comme toute route (voir app/main.py).
    @app.post(PATH, status_code=204, include_in_schema=False)
    def receive(entries: list[Entry], request: Request) -> None:
        append(request.headers.get("X-Compte-Id", "?"), entries[:50])


def main() -> None:
    parser = argparse.ArgumentParser(description="Lit le journal de l'appli (rien n'est écrit).")
    parser.add_argument("--lignes", type=int, default=200)
    args = parser.parse_args()
    file = log_file()
    if not file.exists():
        print("Journal vide : aucune demande échouée reçue.")
        return
    for line in file.read_text(encoding="utf-8").splitlines()[-args.lignes :]:
        print(line)


if __name__ == "__main__":
    main()
