# CLAUDE.md

Contretemps est le brouillon d'AppBase : un core et des modules pour lancer un
SaaS vite. Chaque module se code ici de façon isolée pour être extrait tel quel.

## Règles de comportement

### 1. Réfléchir avant de coder
- Énonce tes hypothèses avant d'écrire du code.
- Si la demande est ambiguë, pose la question au lieu de deviner.
- Si une approche plus simple existe, propose-la.

### 2. La simplicité d'abord
- Écris le minimum de code qui répond à la demande.
- Pas d'abstraction, de pattern ou de configuration « au cas où ».
- Pas de fonctionnalité non demandée ni absente de la spec.
- Si 50 lignes suffisent, n'en écris pas 200.

### 3. Changements chirurgicaux
- Ne modifie que le code nécessaire à la demande.
- Pas de refacto, renommage ou reformatage non demandés.
- Respecte le style existant du projet.
- Si tu repères un autre problème, signale-le sans le corriger.

### 4. Objectif vérifiable
- Avant de coder, définis comment vérifier que c'est réussi (test qui passe, résultat attendu).
- Pour un bug : écris d'abord un test qui le reproduit, puis corrige.
- Itère jusqu'à ce que la vérification passe, puis dis-moi comment tu l'as vérifié.

## Façon de travailler
- Récupère toujours les derniers commits avant de spécifier ou de coder : je code aussi de mon côté.
- La spec fait foi. Lis avant toute tâche : `spec/core.md` (le socle), `spec/modules/<module>.md`
  (le module touché), `spec/SPEC.md` (Contretemps), `spec/a-faire.md` (ce qui reste). Si une
  demande contredit la spec, signale-le ; une décision nouvelle s'écrit dans la spec, dans la même PR.
- Une étape = une PR. Fusionner dans `main` = mise en ligne automatique sur le VPS
  (`.github/workflows/deploy.yml`, voir [DEPLOY.md](DEPLOY.md) §5) : ne fusionne jamais sans ma demande.
- Pas d'accès aux données de prod : une correction de données se livre comme une commande
  (`python -m app.<commande>`) que je lance sur le VPS.
- Je viens de Java : écris du Python idiomatique (fonctions simples, dataclasses/Pydantic), pas de
  hiérarchies de classes à la Java. Composition plutôt qu'héritage.
- Explique brièvement tes choix quand tu touches à la base de données.

## Stack
- Backend : Python 3.11+, FastAPI, SQLAlchemy 2, migrations Alembic.
- Base de données : SQLite, en local comme en prod (`/app/data/contretemps.db`, volume Docker).
  PostgreSQL prévu : le code SQLAlchemy doit rester portable (`DATABASE_URL`).
- Frontend : React (Vite), web mobile d'abord, installable (manifest + service worker pour les
  notifications push), Android via Capacitor ([ANDROID.md](ANDROID.md)).
- Déploiement : Docker Compose sur le VPS `silvaplana.cloud` (backend, workers, frontends) derrière
  le Caddy partagé. Pas de Kubernetes.

## Architecture (socle AppBase)
- Core : organisations (écoles), membres, rôles, droits, auth, email, push, saisons, groupes.
  Rôles du core : Membre, Admin, Trésorier, Administrateur principal, Super User ; une personne =
  une seule fiche par organisation, les rôles se cumulent ([spec/core.md](spec/core.md)).
- Modules (messagerie instantanée, vidéos, documents, notes de frais…) : chacun dans
  `backend/src/<module>/` et `frontend/src/modules/<module>/`, sans dépendre de Contretemps.
  Ce qui est propre à Contretemps va dans `<module>_contretemps/` (ex. `documents_contretemps/`).
- Cible : un contrat d'enregistrement minimal (routes, menu, droits) ; le core ne connaît pas les
  modules ([spec/core.md](spec/core.md) §9 bis). Aujourd'hui `app/main.py` les assemble à la main.
- Données spécialisées par composition (clé étrangère vers la fiche), pas par héritage.
- Multi-organisation : les écoles sont étanches. Toute requête de données filtre par école
  (`ecole_id` ; modèle : `saisons/portee.py`). Attention : un « groupe » est un cours, pas une école.
- Ne crée pas de nouveau module ou point d'extension sans me le proposer d'abord.

## Conventions
- Nouveau code, variables, tables : en anglais (dans un module, école = organisation, cours = groupe).
  Le code ancien est en français : ne le renomme pas.
- Tables d'un module préfixées par le module (`doc_`, `nf_`). Les tables existantes gardent leur nom.
- Commits en anglais.
- À l'écran : vocabulaire métier en français, jamais de mot technique ni « IA ». On dit « module »
  et « sous-module », jamais « brique » ; « nature », jamais « type ». « Gros et simple » : texte
  ≥ 17 px, touches ≥ 48 px, un bouton principal par écran, Annuler plutôt que confirmer
  (voir `spec/modules/documents.md` §6.0 bis).

## Commandes
- Backend en local : `cd backend && pip install -e ".[dev]" && alembic upgrade head && python -m app.seed && app`
  (API sur http://localhost:8000/docs). Repartir propre : `python -m app.reset_demo --yes`.
- Frontend en local : `cd frontend && npm install && npm run dev` ; lint : `npm run lint`.
- Tests : `cd backend && pytest` (SQLite en mémoire). Les tests de PDF échouent sans Chromium
  installé : connu, ce n'est pas ta régression.
- Après un changement de `models.py` : `alembic revision --autogenerate -m "..."`, relis la migration.
- Docker : `docker compose up -d --build` ; en prod c'est `deploy.sh`, lancé par la mise en ligne.

## À ne pas toucher sans demander
- Docker et Caddy : `docker-compose.yml`, `*/Dockerfile`, `frontend/Caddyfile*`, `deploy.sh`,
  `.github/workflows/`.
- Migrations déjà dans `main` (`backend/alembic/versions/`) : on en ajoute une, on ne les modifie pas.
- Secrets et `.env` : jamais dans le dépôt.
