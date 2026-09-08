# backend

API REST (FastAPI) packagée avec `pyproject.toml` et un layout `src/`.

## Structure

Un dossier par module métier, chacun avec le même schéma (voir
[[backend-architecture]] côté mémoire projet, ou juste ci-dessous) —
inspiré du découpage de [test-python](../../test-python) :

```
backend/
├── pyproject.toml
├── .env.example          # DATABASE_URL (vide -> SQLite local)
├── alembic.ini / alembic/  # migrations (une seule base, partagée par tous les modules)
├── src/
│   ├── app/
│   │   ├── main.py       # assemble tous les modules sur UNE app FastAPI
│   │   └── seed.py       # recrée les données de démo (voir mockData.js)
│   ├── db/                # engine/session/Base partagés — n'appartient à aucun module métier
│   ├── ecoles/             # Admin > École
│   ├── comptes/            # Profil (+ table Compte/Famille, socle réutilisé par eleves/profs/auth)
│   ├── auth/               # Login, bascule de profil famille
│   ├── cours/              # Admin > Cours (+ planning hebdomadaire)
│   └── eleves/             # Admin > Élèves
└── tests/
```

Chaque module `<nom>/` :
- `models.py` — les tables SQLAlchemy de ce module, **rien d'autre** (pas
  de logique). Un seul fichier même s'il y a plusieurs classes — convention
  Python/SQLAlchemy, pas la règle Java "une classe = un fichier".
- `<nom>.py` — la logique métier (une classe "client"), aucune dépendance
  FastAPI. Réutilisable par d'autres modules (ex. `auth` appelle `comptes`).
- `receiver.py` — les routes REST, montées sur l'app FastAPI **partagée**
  (créée dans `app/main.py`) ; ne fait que traduire HTTP <-> appels au
  client, aucun calcul métier ici.
- `schemas.py` — formes Pydantic des requêtes/réponses HTTP (pas les
  tables) quand une route a besoin de valider un corps de requête.

Modules prévus mais pas encore codés (voir spec/SPEC.md) : `profs`,
`messagerie` (conversations.py + messages.py), `presence`,
`choregraphies`, `videos`. L'import Excel réel (§6.4bis) est différé —
`eleves.py` expose déjà les primitives CRUD qu'un futur `import_excel.py`
pourra réutiliser.

## Installation (venv + pip)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Base de données

SQLite en local par défaut (fichier `contretemps.db`, créé automatiquement
au lancement) — zéro install. PostgreSQL en prod via `DATABASE_URL` (voir
`.env.example`) : le code SQLAlchemy est portable, rien à changer.

```bash
alembic upgrade head      # applique les migrations (crée les tables)
python -m app.seed        # recrée les données de démo (école, admin, profs)
```

Après avoir modifié un `models.py` :

```bash
alembic revision --autogenerate -m "description du changement"
alembic upgrade head
```

## Utilisation

```bash
app
# ou
python -m app.main
```

Le serveur écoute par défaut sur `http://0.0.0.0:8000`. Documentation
interactive générée automatiquement : `http://localhost:8000/docs`.

- `GET /health` -> `{"status": "ok"}`
- `GET/POST/PUT /ecoles...`, `GET /comptes/{id}`, `POST /auth/login`... —
  voir `/docs` pour le détail à jour.

## Tests

```bash
pytest
```

Chaque test tourne sur une base SQLite en mémoire isolée (voir
`tests/conftest.py`), jamais sur `contretemps.db`.
