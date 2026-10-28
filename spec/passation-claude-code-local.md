# Passation vers Claude Code local (28 octobre 2026)

À lire après `CLAUDE.md`. Ce fichier dit ce qui n'est pas ailleurs dans le dépôt : où on en est,
les habitudes de Seb, et ce qu'il faut préparer pour les deux prochains chantiers. Les specs
(`spec/core.md`, `spec/modules/*.md`, `spec/a-faire.md`) sont à jour à chaque PR et font foi.

## 1. Où on en est

Tout est fusionné et en ligne jusqu'à la PR #98. Pas de PR en cours, à part les anciennes #4 et #8.

- **Structure des adhérents** (`spec/core.md` §13) : étapes 1a à 7c en ligne (saisons, formules,
  options, codes promo, règles de tarif en français vérifiées par `plans/rules.py`).
  La règle de tarif n'a été essayée qu'avec un assistant simulé dans les tests.
- **HelloAsso** (`spec/modules/helloasso.md`) : 8a connexion, 8b campagne de la saison et champs
  verrouillés, 8c synchronisation (toutes les 5 min + bouton), 8d tarifs en lecture seule.
  **Essayé seulement contre un faux HelloAsso dans les tests** : Seb doit l'essayer avec sa vraie
  campagne. Ensuite : étape 9, formulaire d'inscription (maquette d'abord). Restent aussi : choix
  de la campagne à la création de saison, colonnes Payé / Reste, photo, « Modifiable sur HelloAsso ».
- **Fights** (module `session_clips`, « Fights » à l'écran, `spec/modules/video-combats.md`) :
  étapes 1, 2 (découpe dans le conteneur `sparring-worker`), 2 bis (Filmer un combat), 3a (serveur,
  pastille caméra, jumelage, découpe au fil des morceaux, PR #94) et 3b (appli caméra Android
  `recorder/`, APK fabriqué par `.github/workflows/recorder-apk.yml`, PR #95) en ligne.
  APK : <https://github.com/silvaplana/contretemps/releases/download/camera-latest/fights-camera.apk>
  (clé debug du runner : une mise à jour = désinstaller puis rejumeler).
  **Prochaine : 3c, les gestes reconnus par le téléphone** (poing levé bras plié = début, poignée de
  main = fin, X en secours ; bip et/ou lampe ; YOLO pose TFLite). Attend la vidéo de test de Seb
  (quelques combats avec gestes) et la hauteur sous plafond de la salle (fixation : mât
  sol-plafond ou pied lesté). Les réglages de la découpe (`signals.py`, `fights.py`) n'ont jamais vu
  de vraie vidéo.
- **Financier** (`spec/modules/financier.md`) : Comptes, Bilan, AG, Prévisionnel, repris de Sambo
  Admin. Les comptes se remplissent par import des relevés PDF Crédit Mutuel. Pas encore de
  connexion bancaire (voir §3).

## 2. Habitudes de Seb

- Seb dicte : « SoundAdmin » = Sambo Admin (dépôt `silvaplana/test-python`), « Abbey » = AppBase,
  « la G » = l'AG.
- Réponses courtes : la recommandation d'abord, une seule question fermée.
- Maquette cliquable avant la spec pour un nouvel écran ; une fois validée, l'écran la suit
  exactement. Chaque étape de code part sur son « vas-y ».
- **Fusionner seulement quand Seb écrit « merge »** : fusionner dans `main` met en ligne (~15 min).
  Si la mise en ligne échoue parce que le VPS ne répond pas en SSH, attendre quelques minutes et
  relancer l'action « Déployer sur le VPS ».
- Deux branches qui ajoutent chacune une migration : vérifier l'ordre Alembic (`down_revision`)
  après avoir récupéré `main`, sinon deux têtes.
- `create_all` tourne avant `alembic upgrade head` : une migration qui crée une table doit tester
  `has_table`.
- Sans accord de Seb, ne pas toucher `docker-compose.yml`, les Dockerfile, les Caddyfile,
  `deploy.sh`, `.github/workflows/`, ni les `.env`. Les commandes sur le serveur passent par
  l'action « Maintenance du VPS » (`DEPLOY.md` §6).
- Goût : simple, sans encadré ni titre inutile, pas d'email ni d'heure quand ce n'est pas utile.

## 3. Brancher un vrai compte en banque

Sambo Admin le fait déjà avec **Enable Banking** (agrégateur PSD2) : `test-python`,
`backend/src/bankaccounts/` (client `enablebanking.py` : JWT RS256 signé par une clé privée `.pem`,
`kid` = identifiant de l'application ; flux `POST /auth` → banque → retour avec `code` →
`POST /sessions` → soldes et opérations). Dans Contretemps, `fin_operations.source` prévoit déjà
`banque` à côté de `releve`. La règle de l'étape reste : reprendre ce code tel quel.

À préparer :

1. **Côté Enable Banking** (Control Panel <https://enablebanking.com/cp>) : l'application existante
   de Sambo Admin peut servir, ou une nouvelle. Il faut son **Application ID** et sa **clé privée
   `.pem`**. Déclarer l'**URL de retour** de Contretemps à l'identique (HTTPS) dans l'application.
   Sans contrat, l'application ne lit que les comptes liés par son propriétaire : ça suffit pour le
   compte de l'école de Seb, pas pour d'autres écoles.
2. **Sur le VPS, jamais dans le dépôt** :
   - dans `backend/.env` : `ENABLE_BANKING_APP_ID`, le chemin de la clé, l'URL de retour, la banque
     (`ENABLE_BANKING_ASPSP_NAME=Crédit Mutuel`, pays `FR`, type `personal` ou `business`) ;
   - la clé `.pem` : dans Sambo Admin elle est dans `backend/secrets/` monté en lecture seule par
     `docker-compose.yml`. Contretemps n'a pas ce montage : soit Seb accepte d'ajouter la ligne
     dans `docker-compose.yml` (fichier à ne pas toucher sans accord), soit la clé va sur le volume
     `backend_data` (`/app/data/secrets/`, à copier avec `docker cp`), soit son contenu va dans une
     variable de `backend/.env`. À décider avec Seb avant de coder.
   - Mettre à jour `backend/.env.example` (noms de variables seulement) et `DEPLOY.md` §4.
3. **Multi-école** : la clé et l'identifiant sont ceux de la plateforme ; ce qui est propre à une
   école (banque choisie, session bancaire, comptes autorisés, date d'expiration du consentement,
   180 jours max) va en base, table préfixée `fin_`, filtrée par organisation. L'URL de retour est
   unique : le paramètre `state` doit dire quelle école revient. Le consentement expire : prévoir
   « Reconnecter la banque ».
4. **Opérations** : celles de la banque arrivent comme provisoires (« en attente du relevé ») et le
   relevé PDF fait foi quand il arrive (spec Financier §3).

## 4. Boucle de rétroaction sur Fights

Pour tourner en boucle en local : une vidéo de test de Seb (quelques combats avec poing levé et
poignée de main), `pytest` sur `session_clips`, et lancer la découpe sur la vidéo pour régler
`signals.py` / `fights.py`. YOLO (PyTorch) n'est installé que dans l'image `sparring-worker` ; en
local il faut l'installer à part. L'APK se fabrique par l'action GitHub (le SDK Android peut aussi
s'installer en local).
