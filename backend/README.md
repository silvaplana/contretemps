# backend

API REST (FastAPI) packagée avec `pyproject.toml` et un layout `src/`.

## Structure

```
backend/
├── pyproject.toml
├── .env.example         # variables attendues (vide pour l'instant)
├── src/
│   └── app/
│       └── main.py      # point d'entrée : crée l'app FastAPI + CORS, lance uvicorn
└── tests/
    └── test_health.py
```

Au fur et à mesure des fonctionnalités (élèves, cours, inscriptions,
planning, ...), suivre le découpage en modules de
[test-python](../../test-python) : un dossier par domaine sous `src/`,
avec une classe client + une classe "receiver" FastAPI, montée sur l'app
unique dans `app/main.py`.

## Installation (venv + pip)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Utilisation

```bash
app
# ou
python -m app.main
```

Le serveur écoute par défaut sur `http://0.0.0.0:8000`.

- `GET /health` -> `{"status": "ok"}`

## Tests

```bash
pytest
```
