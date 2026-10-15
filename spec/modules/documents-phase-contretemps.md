# Documents et A-documents : phase Contretemps

Version 0.1, 14 octobre 2026. Destinataire : Claude Code. Statut : **plan à valider par Seb**.

Décision de Seb (14 octobre) : AppBase n'existe pas encore ; on développe le système de documents et
d'A-documents **dans Contretemps d'abord**, en module isolé, prêt à devenir le module `documents`
d'AppBase sans réécriture.

La spec fonctionnelle complète est `appbase/spec/modules/documents.md` (les § ci-dessous y renvoient).
Ce plan dit **dans quel ordre** la livrer dans Contretemps, **ce qui change** par rapport à la spec à cause
de l'existant, et **comment rester extractible**.

Constat sur le dépôt (`silvaplana/contretemps`, commit `183795c`) :

- base **SQLite en production** (`docker-compose.yml`, `backend/.env.example`), Postgres prévu mais pas
  fait ;
- comptes **dupliqués par saison** (`comptes.saison_id`, chaînés par `compte_precedent_id`) ; rôles
  cumulables `eleve`, `professeur`, `admin`, `owner`, `superuser` (`comptes/roles.py`) ;
- portée par saison automatique et verrou d'écriture des saisons passées (`saisons/portee.py`) ;
- onglet « Docs » prototype, frontend seul (`frontend/src/screens/DocsScreen.jsx`,
  `frontend/src/data/documents.js`), sélecteur `Public | Privé | Personnel` ;
- vidéos stockées par école sur disque, envoi par blocs éprouvé (`backend/src/videos/`), mais servies
  en statique **sans contrôle d'accès** (`app.mount("/media/videos", StaticFiles…)` dans `app/main.py`) ;
- appel à Claude déjà en place avec table de prix (`inscriptions/lecture_fiche.py`) ;
- emails envoyés en SMTP direct (`auth/mails.py`, `inscriptions/email_envoi.py`).

---

## 1. Règles pour rester extractible

1. **Un paquet isolé**, identifiants en anglais (comme le futur module) :
   - `backend/src/documents/` (modèles, services, routes, types et blocs de base, tests) ;
   - `frontend/src/modules/documents/` (explorateur, aperçu, éditeur, fabrication, tuiles) ;
   - textes d'interface en français.
2. **Le paquet ne connaît pas Contretemps.** Il déclare ce dont il a besoin dans
   `documents/ports.py` sous forme de `typing.Protocol` (même forme que la façade AppBase, 01 §4.1) :

   | Port | Méthodes | Implémenté dans Contretemps par |
   |---|---|---|
   | `Organizations` | `current(request)`, `get(id)` | `ecoles` |
   | `Members` | `current(request)`, `get(id)`, `same_person(a, b)`, `roles_of(id)`, `search(q)` | `comptes` (+ chaîne `compte_precedent_id`) |
   | `Groups` | `groups_of(member)`, `members_of(group)`, `search(q)` | `groupes` (étape 2 bis), `cours` avant |
   | `Periods` | `current()`, `list()`, `is_closed(period)`, `on_created(handler)` | `saisons` |
   | `Email` | `send(to, subject, html, attachments=[])` | `auth/mails.py` (SMTP) en attendant le module email |
   | `Notify` | `push(member, title, body, url)` | `notifications` |
   | `AI` | `generate(messages, schema, model) -> (result, usage)` | client `anthropic` de `inscriptions/lecture_fiche.py`, sorti dans un petit service partagé |

   L'implémentation vit **hors du paquet**, dans `backend/src/documents_contretemps/adapter.py`, et le
   câblage dans `app/main.py`. Même chose côté web : `frontend/src/modules/documents/ports.ts`, branché
   par `frontend/src/modules/documents_contretemps.ts`.
3. **Contrôle automatique** : `import-linter` (contrat « documents n'importe ni ecoles, comptes, cours,
   saisons, inscriptions, choregraphies… ») et une règle ESLint/oxlint équivalente côté web, en CI.
4. **Vocabulaire générique dans le paquet** : organisation, membre, groupe, période. Les libellés
   « école », « cours », « saison » viennent de l'adaptateur.
5. **Portable SQLite et Postgres** : colonnes `JSON` de SQLAlchemy (pas `JSONB` spécifique), pas de
   `ltree`, recherche par `LIKE` sur un nom normalisé sans accents (colonne `name_search`) plutôt que
   `pg_trgm`. Tout ce qui exige Postgres est repoussé à l'étape 8.
6. **Identité des personnes à travers les saisons** : comme les comptes sont recréés à chaque saison,
   les droits, auteurs et « dernier endroit » stockent l'identifiant du **premier compte de la chaîne**
   (`person_id`, fourni par `Members`), jamais l'identifiant du compte de la saison. Sinon un partage
   fait en 2025-2026 disparaîtrait en 2026-2027.
7. **Saisons** : les tables du paquet **ne sont pas** des tables « racines » de `saisons/portee.py` (le
   dossier Permanent n'a pas de saison, et les dossiers des saisons passées doivent rester lisibles depuis
   la saison courante). Le verrou des saisons closes est appliqué par le paquet lui-même (`documents.md`
   §4.7, règle 0 des droits), via le port `Periods`. Les écritures du paquet passent donc par un
   contexte `toutes_saisons` fourni par l'adaptateur.

## 2. Étapes

Chaque étape = une PR autonome, déployable, tests verts, utilisable seule à l'école. Ne pas commencer
une étape avant que la précédente soit en production.

### Étape 1 : stockage protégé, vidéos migrées

- `backend/src/storage/` (futur core AppBase) : contenus par empreinte sha256, envoi par blocs repris de
  `videos/` (`Televersement`, contrôle du décalage, nettoyage des abandons), téléchargement par route
  avec contrôle de droit et prise en charge de `Range`, vignettes (Pillow, pypdfium2), détection du type
  (puremagic). Disque local derrière obstore (`documents.md` §3.2, §4.1).
- Les vidéos passent dessus ; suppression du montage statique `/media/videos`.
- *Fait le 2026-10-15, première version* : montage statique supprimé ; le fichier et l'aperçu ne se
  lisent plus que par `/videos/{id}/fichier` et `/videos/{id}/poster`, avec un **lien signé à durée
  limitée** (6 à 12 h, `securite/liens.py`) remis à qui peut voir la vidéo (la balise `<video>` ne sait
  pas envoyer la session). Lecture progressive (`Range`) conservée ; lien expiré : l'appli en redemande
  un. Pas encore : stockage par empreinte (`backend/src/storage/`) ni migration des fichiers, qui
  restent à leur place.
- *Acceptation* : une URL de vidéo copiée ne marche plus sans session (test) ; les vidéos existantes
  sont migrées par un script idempotent ; la lecture mobile et la vignette fonctionnent comme avant.

### Étape 2 : explorateur et fichiers (remplace l'onglet Docs)

- Backend : `doc_nodes`, `doc_versions`, `doc_acl`, `doc_activity`, `doc_member_state`
  (`documents.md` §4.2 à §4.8), espaces `Public | Privé | Personnel` (libellés Contretemps du prototype),
  dossier Permanent créé à l'installation, corbeille 30 jours, versions de fichiers, droits hérités
  filtrés en SQL, retour au dernier endroit.
- Dossiers de saison dans Privé uniquement, un par saison définie, créés automatiquement (Seb, 15 octobre) ;
  étape « Documents » ajoutée à l'écran de création de saison pour le contenu de départ (vide ou copie de
  la saison précédente ; §4.7) ; verrou des saisons closes.
- Frontend : un seul explorateur, mêmes fonctions sur téléphone et ordinateur (§6.0) :
  `@headless-tree/react`, `@dnd-kit/core` (appui long = clic droit, appui long + glisser = déplacer),
  `@tabler/icons-react`, tuiles de types (§7), visionneuses image et PDF. **L'onglet « Docs » est gardé**
  (Seb, 15 octobre) : on vide tout son contenu actuel et on y met le nouvel explorateur.
- Le contenu d'exemple de `data/documents.js` est **supprimé** (pas importé).
- **Les élèves n'ont pas d'espace Personnel** (Seb, 15 octobre) : leur sélecteur montre `Public | Privé`,
  Privé ne contenant que ce qui leur est partagé. Personnel existe pour les professeurs et les admins.
- *Acceptation* : parcours Playwright mobile et ordinateur (créer un dossier, envoyer une photo, la
  glisser dans un autre dossier, la supprimer, la restaurer) ; test qu'un élève ne voit rien de
  l'espace Privé, ni dans la recherche ; test qu'un dossier de saison close refuse toute écriture,
  admin compris.

### Étape 2 bis : groupes (demande de Seb du 14 octobre)

> **Seb, 15 octobre** : les groupes existent déjà dans Contretemps sans être déclarés : Admins, Professeurs,
> Élèves (par rôle) et chaque cours (ses élèves et ses profs). L'étape 2 les **lit** tels quels pour les droits,
> sans rien recréer ni tenir à jour à la main. Les groupes manuels (Bureau…) viendront avec cette étape 2 bis.

Les groupes deviennent une notion de premier plan de l'appli, pas seulement du module documents : on
écrit à un groupe, on partage un A-document avec un groupe, on diffuse un sondage à un groupe, on ouvre
une conversation de groupe. C'est la décision 3 de la spec d'architecture (« groupe générique dans le
core »), faite dès maintenant dans Contretemps, hors du paquet `documents` (paquet `backend/src/groupes/`,
qui partira dans le core d'AppBase).

- **Tables** : `groups` (nom, couleur, type, saison ou permanent, règle) et `group_members` (pour les
  groupes manuels).
- **Trois sortes de groupes**, une seule liste pour l'utilisateur :
  - *automatiques, tirés de l'existant* : chaque cours, les professeurs, les administrateurs ;
  - *par règle* : « parents d'élèves mineurs », « adhérents sans cotisation payée », « inscrits au
    gala » ; la liste se recalcule toujours, personne n'oublie d'ajouter un nouveau membre ;
  - *manuels* : liste choisie à la main (« bénévoles buvette », « bureau »).
- **Saison** : un groupe est permanent (« bureau ») ou propre à une saison (les cours) ; « reprendre les
  groupes de la saison précédente » à la création d'une saison, comme pour les dossiers.
- **Écran** : Admin > Groupes (liste, membres, règle), et dans la fiche membre ses groupes.
- **Utilisé par** : le partage (étape 3), l'envoi d'email à un groupe (module email), la diffusion des
  collectes (étape 6), la messagerie (les « groupes de chat » deviennent des conversations rattachées à
  un groupe), plus tard les présences.
- Le port `Groups` (§1) lit cette table au lieu de `cours`.
- Un groupe donne un droit seulement là où on l'a choisi (partage d'un dossier, d'un document) : en
  faire partie ne donne aucun droit par lui-même.

### Étape 3 : partage et envoi par email

- Écran Partager (§4.4 bis), droits par fichier sur membres, groupes et rôles, liens externes avec
  expiration (§4.5), envoi par email avec lien ou PDF joint, notification push.
- Le port `Email` gagne les pièces jointes (dans `auth/mails.py` en attendant le module email AppBase).

### Étape 4 : socle A-document et Document libre

- Registre des types (§5.1, §5.3), type `documents.free` (§5.6) avec éditeur **BlockNote** (pas les
  paquets XL) : aperçu et édition dans le même composant, lecture seule par défaut, bouton Modifier
  (§5.4 « Édition à la main »), états Brouillon / Validé / Officiel avec PDF figé à l'officialisation
  (Chromium sans écran, déjà dans l'image), versions `human` et `frozen`.
- Tuile pleine avec étincelle pour les A-documents.
- *Acceptation* : un type factice `demo.note` déclaré hors du paquet apparaît dans le menu + sans
  modifier le paquet (test) ; un document Officiel est verrouillé.

### Étape 5 : fabrication par IA

- Panneau Fabrication caché par défaut (§5.4) : discussion, documents liés repérés `[A] [B] [C]` avec
  sélecteur d'arborescence (`doc_links`), bibliothèque de prompts (`doc_prompts`), choix du modèle depuis
  la configuration, coût estimé et coût cumulé (`doc_generations`), plafond mensuel par école.
- L'IA part toujours de la version courante, répond par **opérations sur les blocs**, respecte les blocs
  verrouillés, voit les modifications manuelles dans le fil (§5.4 « Un seul document »).
- Extraction du texte des documents liés : `markitdown`.
- *Acceptation* : test avec un faux port `AI` qui renvoie des opérations ; une modification manuelle
  suivie d'une génération est conservée au caractère près ; un bloc verrouillé n'est jamais modifié.

### Étape 5 bis : assistant de l'association (demande de Seb du 14 octobre)

Un chat qui agit sur l'association (« fais un groupe des moins de 20 ans », « crée la convocation de
l'AG », « combien a-t-on encaissé en septembre ? »). Même moteur que la fabrication (étape 5), paquet
séparé `backend/src/assistant/` (futur core d'AppBase). Spec détaillée à écrire : `assistant.md`.

- **Registre d'outils** : chaque module déclare ses outils (fonction Python + description + schéma des
  paramètres), comme il déclare ses routes. L'assistant ne voit que les outils autorisés pour
  l'utilisateur, et chaque outil s'exécute avec ses droits.
- **Un outil de lecture générique** `chercher(entité, filtres, champs, agrégat)` sur un petit langage de
  filtres décrit par `schema()` de chaque module ; jamais de SQL écrit par l'IA, jamais toute la base dans
  le contexte : la base calcule, l'IA reçoit le résultat.
- **Des outils d'écriture**, un par geste métier, toujours derrière une carte de confirmation.
- Conversations stockées chez nous, historique renvoyé avec cache (§5.4), mémoire de l'association
  (notes durables relues à chaque conversation).
- **Plusieurs agents, comme les projets Claude (demande de Seb du 14 octobre)** : un **assistant général**
  (coordinateur, conversation de l'utilisateur) et **un agent par A-document**, qui est le chat de
  fabrication de l'étape 5 : sa propre conversation, son contexte (le document, ses liens [A] [B] [C]),
  ses outils (opérations sur les blocs) en plus des outils de lecture. Quand on demande au général
  « prépare la convocation de l'AG », il crée l'A-document, transmet une consigne à son agent et affiche
  une **carte** « Convocation AG 2026 · en cours · Ouvrir » dans la conversation ; on continue le
  travail dans l'agent du document. L'agent du document renvoie un court compte rendu au général quand
  il termine ou bloque (« prêt à valider », « il me manque la date »). La génération tourne en tâche de
  fond côté serveur : on peut fermer l'appli et revenir. Chaque agent a sa mémoire propre ; la mémoire
  de l'association est commune.
- **Règle pour toutes les étapes suivantes** : une fonctionnalité n'est terminée que si ses outils pour
  l'assistant existent (définition de « terminé »).
- Plus tard : exposer le même registre en serveur MCP pour l'utiliser depuis Claude.

### Étape 6 : kit AG

- **Blocs du socle A-document**, dans le paquet `documents` (pas dans un module AG), donc utilisables
  par tout A-document : Signature (signature simple : tracé, code email, horodatage, PDF scellé), Vote
  (main levée, bulletin secret, procurations), Émargement et quorum (QR code), Événement (.ics),
  Formulaire, Dépôt de fichier (§5.8).
- Types `assembly.notice` (convocation), `forms.proxy` (procuration, reprend `genererProcuration` du
  prototype), `assembly.minutes` (PV rempli avec les résultats des votes), `assembly.deck` (présentation).
- **Collecte de réponses** du socle (§5.10) : diffusion avec liens personnels, date limite, relances,
  onglet « Réponses » en tableau commun, export .xlsx.
- *Acceptation* : une AG de démonstration de bout en bout sur l'école de démo : convocation envoyée,
  procurations signées, émargement, quorum, votes, PV officiel généré et envoyé.

### Étape 7 : publication et inscriptions

- A-modèles (§5.6), publication en ligne `<préfixe>.contretemps.silvaplana.cloud/<page>` (§5.5) par gabarits,
  liaison du bloc Formulaire aux membres avec questions de l'IA et file « À rapprocher » (§5.9), bloc
  Paiement du socle avec le port `PaymentProvider` implémenté pour HelloAsso.
- La campagne d'inscription devient un A-document et **remplace l'appli séparée
  `frontend-inscription/`** (route Caddy `/contretemps-inscription/` redirigée).

### Étape 8 : après le passage à Postgres

- Champs personnalisés des membres en `JSONB` (§5.9), recherche plein texte (`pg_trgm`, `unaccent`),
  A-site web (§5.7), bloc Calcul (§5.8), plusieurs workers.
- Le passage à Postgres est l'étape 1 de la spec d'architecture (01 §9) ; il peut se faire à tout moment
  avant l'étape 8, idéalement avant l'étape 5 (volume des versions et des générations).

## 3. Sortie vers AppBase

Le jour où AppBase démarre (01 §9, étape 7) :

- `backend/src/documents/` et `frontend/src/modules/documents/` deviennent `modules/documents/` presque
  tels quels ;
- `backend/src/storage/` rejoint le core ;
- les ports de `documents/ports.py` sont remplacés par la façade `appbase.core.api` (mêmes méthodes,
  c'est voulu) ;
- `documents_contretemps/adapter.py` disparaît ; `person_id` devient `member_id` du core une fois les
  familles et comptes par saison remplacés par les profils (01 §9, étape 3).

## 4. Décisions à trancher par Seb

1. **Ordre des étapes** : Recommandation : celui ci-dessus. Le kit AG (étape 6) est la démonstration
   qui fera dire « waouh » ; les étapes 1 à 5 le rendent possible et sont utiles seules.
2. **Postgres avant l'étape 5 ?** Recommandation : **oui**. SQLite tiendra les étapes 1 à 4, mais les
   versions, générations et réponses de formulaires vont grossir vite, et l'étape 8 l'exige.
3. **Montrer les dossiers des saisons passées depuis la saison courante ?** Recommandation : **oui**, en
   lecture seule, regroupés sous « Saisons précédentes » : c'est la mémoire de l'école, et « Reprendre
   pour cette saison » en dépend.
4. **Groupes par règle dès l'étape 2 bis ?** Recommandation : **oui pour quelques règles prêtes**
   (cours, rôle, âge, cotisation payée, inscrit à…), choisies dans une liste ; pas d'éditeur de règles
   libre. Les groupes manuels seuls obligeraient à tenir les listes à jour à la main, ce qui est
   exactement ce que les bénévoles oublient.
