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
                           ├── /contretemps/* → réseau "web" → contretemps-frontend:80 (Caddy interne)
                           │                                        │
                           │                                        └── /api/* → backend:8000 (FastAPI)
                           └── /contretemps-inscription/* → réseau "web" → contretemps-inscription-frontend:80
                                                                                 │
                                                                                 └── /api/* → backend:8000 (MÊME backend)
```

`contretemps-inscription-frontend` (voir `frontend-inscription/`, spec/SPEC-inscription.md) est
une appli sœur séparée — page publique d'inscription, destinée à être liée en priorité depuis le
site externe de l'école (`dansecontretemps.fr`) plutôt que depuis l'appli principale — mais elle
parle au **même** backend Contretemps (même réseau Docker, aucune base de données séparée).

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

redir /contretemps-inscription /contretemps-inscription/ 308
handle_path /contretemps-inscription/* {
	reverse_proxy contretemps-inscription-frontend:80
}
```

Puis recharger le gateway :

```bash
cd ~/gateway
docker compose up -d
```

Le site est alors accessible sur `https://silvaplana.cloud/contretemps/` et
`https://silvaplana.cloud/contretemps-inscription/`.

## 3. Mettre à jour après un nouveau push GitHub

**Automatique depuis le 2026-10-18** : chaque fusion dans `main` est mise en
ligne par GitHub Actions (voir section 5). À la main, en dépannage, une
seule commande fait tout ce qui suit (pull, build, migrations, vérification) :

```bash
ssh vps
cd contretemps
./deploy.sh
```

Le détail de ce que fait `deploy.sh` :

```bash
git pull
docker compose up -d --build
```

`Base.metadata.create_all` (voir `app/main.py`) crée automatiquement les tables MANQUANTES au
démarrage — pratique, mais ça ne fait JAMAIS rien pour une colonne ajoutée à une table déjà
existante. C'est pourquoi `deploy.sh` applique toujours les migrations Alembic après le `docker compose up
-d --build` ci-dessus (sans effet s'il n'y en a pas de nouvelle) :

```bash
docker compose exec backend alembic upgrade head
```

## 4. Secrets (si besoin plus tard)

`docker-compose.yml` charge `backend/.env` s'il existe (`env_file`,
`required: false`) — le créer une fois sur le VPS à partir de
`backend/.env.example` quand une variable y sera ajoutée :

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Le frontend, lui, a une variable qui doit être connue AU BUILD (pas au
lancement du conteneur, voir frontend/Dockerfile) : `GOOGLE_CLIENT_ID`
("Sauvegarder École" -> Google Drive, voir frontend/.env.example). Créer
un `.env` **à la racine du repo** (gitignoré, lu automatiquement par
`docker compose` pour les substitutions `${...}` de `docker-compose.yml`) :

```bash
echo "GOOGLE_CLIENT_ID=votre-client-id.apps.googleusercontent.com" > .env
docker compose up -d --build frontend
```

Sans ce fichier, `GOOGLE_CLIENT_ID` reste vide et le frontend se construit
quand même — seule la destination "Cet appareil" est proposée dans le
menu sauvegarde, sans erreur.

### Connexion bancaire du Financier (Enable Banking)

Financier › Comptes › ⋯ › Se connecter aux comptes en banque (spec `modules/financier.md`
§3.5). Il faut une application Enable Banking (Control Panel
<https://enablebanking.com/cp>) : son **Application ID** et sa **clé privée
`.pem`** (téléchargée à sa création). Celle de Sambo Admin peut servir.

1. Dans le Control Panel, ajouter l'adresse de retour de l'application :
   `https://silvaplana.cloud/contretemps/api/finances/bank/return`.
2. Sur le VPS, la clé en **fichier**, lisible par soi seul, jamais dans le
   dépôt ni dans une variable (le conteneur la voit en lecture seule dans
   `/run/secrets/`, hors de `/app/data`, donc hors des sauvegardes) :

   ```bash
   mkdir -p ~/contretemps/backend/secrets
   # La clé de Sambo Admin est dans ~/test-python/backend/secrets/.
   cp ~/test-python/backend/secrets/<nom de la clé>.pem ~/contretemps/backend/secrets/enable_banking.pem
   chmod 700 ~/contretemps/backend/secrets
   chmod 600 ~/contretemps/backend/secrets/enable_banking.pem
   ```

   (600 suffit : `appuser`, dans le conteneur, a le même numéro, 1000, que
   l'utilisateur du VPS.)
3. Dans `backend/.env` : `ENABLE_BANKING_APP_ID=...` et
   `ENABLE_BANKING_REDIRECT_URL=https://silvaplana.cloud/contretemps/api/finances/bank/return`,
   puis `docker compose up -d backend`.

Sans contrat Enable Banking, l'application ne lit que les comptes que son
propriétaire y a d'abord liés (Control Panel) : c'est le cas de l'école du
propriétaire, pas d'autres écoles.

## 5. Mise en ligne automatique (GitHub Actions)

À chaque fusion dans `main` (et à la demande, onglet **Actions** du dépôt >
« Déployer sur le VPS » > **Run workflow**), GitHub se connecte au VPS en
SSH, lance `deploy.sh`, puis vérifie que `/contretemps/api/health`,
`/contretemps/` et `/contretemps-inscription/` répondent. Un déploiement raté
apparaît en rouge dans l'onglet Actions, avec le journal complet, et GitHub
envoie un mail.

- Fichiers : `.github/workflows/deploy.yml` (côté GitHub) et `deploy.sh`
  (côté VPS).
- La clé de déploiement est rangée dans les secrets du dépôt, jamais dans le
  dépôt. Sur le VPS, `authorized_keys` la limite à lancer `deploy.sh` : elle
  ne donne pas de terminal et ne peut lancer aucune autre commande.
- `deploy.sh` vient du dépôt : la relecture des PR reste le garde-fou de ce
  qui tourne sur le serveur.
- Les `.env` (racine et `backend/`) restent sur le VPS, `git pull` n'y touche
  pas.
- Tant que les secrets ne sont pas en place, le workflow ne fait rien (simple
  avertissement, pas d'erreur).

### Mise en place (une seule fois)

Sur le VPS (`ssh vps`) :

1. Récupérer `deploy.sh` et vérifier qu'il marche à la main :

   ```bash
   cd ~/contretemps && git pull && ./deploy.sh
   ```

   Si `docker` demande `sudo`, ajouter l'utilisateur au groupe docker, se
   déconnecter puis se reconnecter : `sudo usermod -aG docker $USER`.

2. Créer la clé de déploiement (sans mot de passe, GitHub ne pourrait pas
   le taper) :

   ```bash
   ssh-keygen -t ed25519 -N "" -C "github-actions-contretemps" -f ~/deploy_contretemps
   ```

3. L'autoriser, limitée à `deploy.sh` :

   ```bash
   echo "command=\"$HOME/contretemps/deploy.sh\",restrict $(cat ~/deploy_contretemps.pub)" >> ~/.ssh/authorized_keys
   ```

4. Afficher les quatre valeurs à coller dans GitHub (étape 5) :

   ```bash
   whoami                                                              # -> VPS_USER
   cat ~/deploy_contretemps                                            # -> VPS_SSH_KEY (tout, lignes BEGIN et END comprises)
   echo "187.124.17.136 $(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)"   # -> VPS_KNOWN_HOSTS
   ```

   `VPS_HOST` vaut `187.124.17.136`. Si SSH n'écoute pas sur le port 22,
   ajouter aussi un secret `VPS_PORT` et écrire `[187.124.17.136]:PORT` au
   début de `VPS_KNOWN_HOSTS` au lieu de l'adresse seule.

Dans GitHub, page
<https://github.com/silvaplana/contretemps/settings/secrets/actions>
(Settings > Secrets and variables > Actions) :

5. Pour chacune des quatre valeurs, **New repository secret**, nom
   `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` ou `VPS_KNOWN_HOSTS`, coller la
   valeur, **Add secret**.

De retour sur le VPS :

6. Effacer la clé privée, qui n'a plus besoin d'être sur le serveur :

   ```bash
   rm ~/deploy_contretemps ~/deploy_contretemps.pub
   ```

Puis dans GitHub :

7. Onglet **Actions** > « Déployer sur le VPS » > **Run workflow** > **Run
   workflow**. Le déploiement doit passer au vert.

Pour couper l'accès : supprimer la ligne `github-actions-contretemps` de
`~/.ssh/authorized_keys` sur le VPS.


## 6. Maintenance à la demande (GitHub Actions)

Pour les quelques commandes à lancer sur le serveur sans s'y connecter :
onglet **Actions** du dépôt > « Maintenance du VPS » > **Run workflow**, puis
choisir la tâche. Un fil Claude peut aussi la lancer quand on le lui demande.
Claude n'a jamais de clé SSH : c'est GitHub qui se connecte, avec la clé de
déploiement (§5).

| Tâche | Ce qu'elle fait |
|---|---|
| Lister les écoles et leurs notes de frais | Affiche chaque école, son numéro, et combien de notes, dépenses et justificatifs elle a. N'efface rien. |
| Effacer les notes de frais d'une école | Demande le numéro de l'école et son nom exact (confirmation). Efface notes, dépenses, justificatifs et le dossier « Notes de frais » de Docs › Financier ; garde catégories et RIB. Irréversible. |

- Fichiers : `.github/workflows/maintenance.yml` (le formulaire) et le début
  de `deploy.sh` (la liste fermée des tâches). La clé ne peut toujours lancer
  que `deploy.sh` ; une tâche absente de cette liste est refusée.
- Ajouter une tâche = une PR qui l'ajoute aux deux fichiers, relue comme le
  reste.
- Une tâche n'attend jamais un déploiement en cours : elle passe après.

## Adresses d'école (spec §2.7, mises en service le 2026-10-15)

Chaque école a son adresse `https://<adresse>.contretemps.silvaplana.cloud`
(Contretemps : `le-beausset`).

- **DNS** (Hostinger, zone `silvaplana.cloud`) : un enregistrement `A`
  `*.contretemps` -> `187.124.17.136`. Toutes les adresses, même futures,
  arrivent ainsi au VPS.
- **Gateway** (`~/gateway/Caddyfile`, hors repo) : certificat créé à la
  première visite, après accord du backend, puis tout est transmis au
  conteneur `contretemps-frontend-ecoles` sans retirer de préfixe :

```caddyfile
{
	email {$ACME_EMAIL}
	on_demand_tls {
		ask http://contretemps-frontend-ecoles/api/sous-domaines/existe
	}
}

*.contretemps.silvaplana.cloud {
	tls {
		on_demand
	}
	reverse_proxy contretemps-frontend-ecoles:80
}
```

  Avant de recharger : `docker compose exec caddy caddy validate --config
  /etc/caddy/Caddyfile --adapter caddyfile`, puis `caddy reload`.
- **Conteneur** `frontend-ecoles` (docker-compose.yml) : même code que
  `frontend`, construit à la racine (`VITE_BASE=/`, API sous `/api`), avec
  `frontend/Caddyfile.ecoles` : manifest, icônes et nom de l'appli dans
  `index.html` viennent du backend, selon l'école de l'adresse (en-tête Host).
- **Liens des mails** : toujours vers l'adresse de l'école (celle de
  Personnalisation), depuis le 2026-10-15. `ADRESSE_PAR_ECOLE=0` dans
  `backend/.env` revient à l'adresse générique (dépannage seulement).


## Pages en ligne des fichiers (documents.md §5.5, depuis le 2026-10-16)

Un fichier de l'appli « mis en ligne » (onglet Diffuser, en Officiel) a son
adresse sous celle de l'école : `https://<page>.<adresse>.contretemps.silvaplana.cloud`
(ex. `https://spectacle-de-juin.le-beausset.contretemps.silvaplana.cloud`).

- **DNS** : rien à faire, le joker `*.contretemps` couvre aussi les noms à
  deux niveaux.
- **Gateway** (`~/gateway/Caddyfile`) : un bloc de plus, identique à celui
  des écoles, pour les noms à deux niveaux (le `*` de Caddy ne vaut que pour
  un niveau). Le backend n'accepte le certificat que si l'école existe et que
  la page est en ligne (`/sous-domaines/existe`) :

```caddyfile
*.*.contretemps.silvaplana.cloud {
	tls {
		on_demand
	}
	reverse_proxy contretemps-frontend-ecoles:80
}
```

  Puis `caddy validate` et `caddy reload` comme ci-dessus.
- Le conteneur `frontend-ecoles` sert la page sans rien changer : l'appli
  reconnaît l'adresse et n'affiche que la page (`frontend/src/pagePublique/`).


## OnlyOffice (édition Word / Excel / PowerPoint, essai depuis le 2026-10-16)

Serveur de documents **partagé par toutes les applis du VPS**, hors de ce dépôt :
`~/onlyoffice/docker-compose.yml` (image `onlyoffice/documentserver:9.4.0.1`, limité à 3 Go de mémoire,
réseau `web`), clé `JWT_SECRET` dans `~/onlyoffice/.env` (générée sur le serveur, jamais affichée).
Servi par la passerelle sous `https://silvaplana.cloud/onlyoffice/` (bloc `handle_path /onlyoffice/*`
de `~/gateway/Caddyfile`, avec `X-Forwarded-Host {host}/onlyoffice`).

Contretemps s'y branche par `backend/src/bureautique/` avec `ONLYOFFICE_JWT_SECRET` (même valeur,
dans `backend/.env`) et `ONLYOFFICE_URL` (par défaut `https://silvaplana.cloud/onlyoffice`).
Une autre appli s'y branche de la même façon (configuration signée, adresse de lecture du fichier,
adresse de retour). Version gratuite : 20 connexions simultanées au total, toutes applis confondues.

    cd ~/onlyoffice && docker compose up -d        # démarrer / mettre à jour
    docker exec onlyoffice curl -s http://localhost/healthcheck   # true
