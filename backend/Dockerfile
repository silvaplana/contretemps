# Image de base : Python "slim" (legere, sans les outils inutiles)
FROM python:3.12-slim

WORKDIR /app

# On copie d'abord uniquement ce qui decrit les dependances puis le code
# source. Docker met en cache chaque etape : si tu ne changes que le
# code, la reinstallation des dependances n'est rejouee que si
# pyproject.toml a change.
COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# Bonne pratique : ne pas executer l'application en tant que root
# a l'interieur du conteneur.
#
# /app (WORKDIR) appartient a root (copie ci-dessus) -> appuser ne peut
# pas y ecrire, donc pas y creer le fichier SQLite par defaut
# (sqlite:///./contretemps.db, chemin relatif au CWD, voir db/database.py).
# /app/data est cree expres, avec les bons droits, et monte en volume
# (voir docker-compose.yml) pour que la base survive aux redeploiements.
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
ENV DATABASE_URL=sqlite:////app/data/contretemps.db
USER appuser

# Documente le port utilise par l'API (n'ouvre rien a lui seul,
# c'est docker-compose.yml qui decide de ce qui est expose/publie).
EXPOSE 8000

CMD ["python", "-m", "app.main"]
