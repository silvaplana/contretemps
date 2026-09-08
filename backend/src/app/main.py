"""Point d'entree unique du backend Contretemps.

Assemble les differents modules metiers (voir backend/README.md et le
decoupage de test-python) sur une seule app FastAPI / un seul service HTTP.
N'appartient a aucun des modules qu'il monte.
"""

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import Auth, AuthReceiver
from comptes import Comptes, ComptesReceiver
from db import Base, engine
from ecoles import Ecoles, EcolesReceiver

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


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
