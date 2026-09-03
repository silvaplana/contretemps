# Déploiement (Docker + VPS Hostinger)

Ce projet est dockerisé et rejoint le **même VPS et le même gateway
partagé** que `test-python` et `fight-rank` (`silvaplana.cloud`) : voir
`test-python/DEPLOY.md` pour l'explication complète de l'architecture
(gateway Caddy, réseau `web`, un domaine pour plusieurs applis sous des
chemins différents). Ce document ne répète que ce qui est spécifique à
Contretemps.

```
Internet ──443/HTTPS──▶ gateway (Caddy, ~/gateway sur le VPS, hors repo)
                           │
                           ├── /sambo-admin/* → test-python
                           ├── /fight-rank/*  → fight-rank
                           └── /contretemps/* → réseau "web" → contretemps-frontend:80 (Caddy interne)
                                                                    │
                                                                    └── /api/* → backend:8000 (FastAPI)
```

## 1. Premier déploiement sur le VPS

Le réseau `web` et Docker existent déjà sur le VPS (mis en place pour les
projets précédents) — pas besoin de les recréer.

```bash
ssh vps
git clone https://github.com/silvaplana/contretemps.git
cd contretemps
docker compose up -d --build
```

Rien n'est encore accessible publiquement à ce stade : il manque le
routage côté gateway (étape 2).

## 2. Brancher le gateway

Sur le VPS, ajouter un bloc de routage dans `~/gateway/Caddyfile`
(fichier hors de ce repo, voir `test-python/DEPLOY.md` section 1bis) :

```caddyfile
redir /contretemps /contretemps/ 308
handle_path /contretemps/* {
	reverse_proxy contretemps-frontend:80
}
```

Puis recharger le gateway :

```bash
cd ~/gateway
docker compose up -d
```

Le site est alors accessible sur `https://silvaplana.cloud/contretemps/`.

## 3. Mettre à jour après un nouveau push GitHub

```bash
ssh vps
cd contretemps
git pull
docker compose up -d --build
```

## 4. Secrets (si besoin plus tard)

`docker-compose.yml` charge `backend/.env` s'il existe (`env_file`,
`required: false`) — le créer une fois sur le VPS à partir de
`backend/.env.example` quand une variable y sera ajoutée :

```bash
cp backend/.env.example backend/.env
nano backend/.env
```
