"""Point d'entree unique du backend Contretemps.

Pour l'instant, une seule app FastAPI vide (juste /health). Au fur et a
mesure des fonctionnalites (eleves, cours, inscriptions, planning, ...),
suivre le decoupage en modules de test-python (backend/src/<module>/) :
chaque module expose une classe "receiver" qui monte ses routes sur cette
meme app, montee ici dans main.py.
"""

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
