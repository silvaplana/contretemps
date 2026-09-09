# Image de base : Python "slim" (legere, sans les outils inutiles)
FROM python:3.12-slim

WORKDIR /app

# On copie d'abord uniquement ce qui decrit les dependances puis le code
# source. Docker met en cache chaque etape : si tu ne changes que le
# code, la reinstallation des dependances n'est rejouee que si
# pyproject.toml a change.
COPY pyproject.toml ./
COPY src ./src
# Fixtures de démo (voir app/seed.py et videos/stockage.py) — aucune
# vraie donnée, committables (voir backend/README.md) : figées dans
# l'image, distinctes du dossier "live" (mutable, dans le volume
# /app/data, voir plus bas).
COPY seed_data ./seed_data
COPY videos_reference ./videos_reference

RUN pip install --no-cache-dir .

# Bonne pratique : ne pas executer l'application en tant que root
# a l'interieur du conteneur.
#
# /app (WORKDIR) appartient a root (copie ci-dessus) -> appuser ne peut
# pas y ecrire, donc pas y creer le fichier SQLite ni les dossiers vidéo
# par defaut (chemins relatifs au CWD, voir db/database.py et
# videos/stockage.py). /app/data est cree expres, avec les bons droits,
# et monte en volume (voir docker-compose.yml) pour que tout ca survive
# aux redeploiements. Les sous-dossiers (uploads/, videos_reference/)
# sont crees par l'appli elle-meme au demarrage, appuser peut y ecrire
# puisqu'il possede /app/data.
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
ENV DATABASE_URL=sqlite:////app/data/contretemps.db
ENV VIDEOS_DIR=/app/data/uploads/videos
# Contrairement à VIDEOS_DIR ci-dessus (mutable, dans le volume), la
# référence pointe vers le dossier figé dans l'image (voir COPY plus
# haut) — jamais modifiée à l'exécution, seulement lue par
# reset_demo.py pour repeupler VIDEOS_DIR.
ENV VIDEOS_REFERENCE_DIR=/app/videos_reference
# Voir app/seed.py : une fois pip install-é, __file__ pointe vers
# site-packages, pas vers l'arborescence source — indique où seed.py
# trouve vraiment seed_data/ dans CETTE image.
ENV SEED_DATA_DIR=/app/seed_data
USER appuser

# Documente le port utilise par l'API (n'ouvre rien a lui seul,
# c'est docker-compose.yml qui decide de ce qui est expose/publie).
EXPOSE 8000

CMD ["python", "-m", "app.main"]
