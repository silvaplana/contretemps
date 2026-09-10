"""Point d'entree unique du backend Contretemps.

Assemble les differents modules metiers (voir backend/README.md et le
decoupage de test-python) sur une seule app FastAPI / un seul service HTTP.
N'appartient a aucun des modules qu'il monte.
"""

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from auth import Auth, AuthReceiver
from choregraphies import Choregraphies, ChoregraphiesReceiver
from comptes import Comptes, ComptesReceiver
from cours import CoursReceiver, CoursService
from db import Base, engine
from ecoles import Ecoles, EcolesReceiver
from eleves import Eleves, ElevesReceiver, ImportExcel, ImportExcelReceiver
from messagerie import Conversations, MessagerieReceiver, Messages
from presence import Presence, PresenceReceiver
from profs import Profs, ProfsReceiver
from videos import DOSSIER_VIDEOS_LIVE, Videos, VideosReceiver

load_dotenv()  # charge backend/.env si present

app = FastAPI(title="Contretemps API")
app.add_middleware(
    # Autorise le frontend React (Vite, servi sur un autre port en dev) a
    # appeler l'API. A restreindre a une origine precise avant mise en prod.
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cree les tables si elles n'existent pas encore (pratique en dev/SQLite ;
# en prod, voir plutot Alembic - backend/alembic/ - pour les migrations
# reelles). Chaque module importe pour son cote (ci-dessous) enregistre ses
# tables sur Base.metadata au moment de l'import.
Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Monte les routes des ecoles (/ecoles) sur la meme app.
ecoles_client = Ecoles()
ecoles_receiver = EcolesReceiver(client=ecoles_client, app=app)

# Monte les routes des comptes (/comptes) - socle reutilise par auth
# ci-dessous, et plus tard par eleves/profs.
comptes_client = Comptes()
comptes_receiver = ComptesReceiver(client=comptes_client, app=app)

# Monte les routes de connexion (/auth/...) - depend de ecoles et comptes.
auth_client = Auth(ecoles=ecoles_client, comptes=comptes_client)
auth_receiver = AuthReceiver(client=auth_client, app=app)

# Monte les routes des cours (/cours) - depend de comptes (professeurs/eleves).
cours_client = CoursService()
cours_receiver = CoursReceiver(client=cours_client, app=app)

# Monte les routes des eleves (/eleves, /contacts) - depend de comptes.
eleves_client = Eleves(comptes=comptes_client)
eleves_receiver = ElevesReceiver(client=eleves_client, comptes=comptes_client, app=app)

# Monte les routes de l'import Excel des eleves (/eleves/import/...) -
# depend de eleves (reutilise ses primitives CRUD) et cours.
import_excel_client = ImportExcel(eleves=eleves_client, cours=cours_client)
import_excel_receiver = ImportExcelReceiver(client=import_excel_client, app=app)

# Monte les routes des profs (/profs) - depend de comptes et cours.
profs_client = Profs(comptes=comptes_client, cours=cours_client)
profs_receiver = ProfsReceiver(client=profs_client, app=app)

# Monte les routes de presence (/seances, /cours/{id}/seances, /profs/{id}/heures) - depend de cours.
presence_client = Presence(cours=cours_client)
presence_receiver = PresenceReceiver(client=presence_client, app=app)

# Monte les routes des choregraphies (/cours/{id}/choregraphies, /choregraphies/...) - depend de cours.
choregraphies_client = Choregraphies(cours=cours_client)
choregraphies_receiver = ChoregraphiesReceiver(client=choregraphies_client, app=app)

# Monte les routes des videos (/cours/{id}/videos, /choregraphies/{id}/videos, /videos/...).
videos_client = Videos(cours=cours_client)
videos_receiver = VideosReceiver(client=videos_client, app=app)

# Sert les fichiers video eux-memes en statique (un dossier par ecole,
# voir videos/stockage.py) - videos.lien_fichier stocke le chemin relatif
# a DOSSIER_VIDEOS_LIVE, servi ici sous /media/videos/<ce chemin>.
DOSSIER_VIDEOS_LIVE.mkdir(parents=True, exist_ok=True)
app.mount("/media/videos", StaticFiles(directory=str(DOSSIER_VIDEOS_LIVE)), name="videos")

# Monte les routes de messagerie (/conversations, /dm, /messages...) - depend
# de comptes et cours (resolution des membres "cours").
conversations_client = Conversations(comptes=comptes_client, cours=cours_client)
messages_client = Messages(conversations=conversations_client)
messagerie_receiver = MessagerieReceiver(
    conversations=conversations_client, messages=messages_client, app=app
)


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
