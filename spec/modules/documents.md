# AppBase — Module `documents`

Version 0.1, 14 octobre 2026. Statut : **brouillon à valider par Seb** (voir §12).

Destinataire : Claude Code. S'appuie sur `appbase/spec/01-architecture.md` (contrat de module §5 et §7,
façade du core §6, règle IHM §2.7). Maquette visuelle : Artifact « Documents AppBase » (lien dans le fil
du projet).

> **Vocabulaire (décision de Seb, 15 octobre)** : pour l'utilisateur comme dans nos échanges, il n'y a
> que des **dossiers** et des **fichiers**. Les « A-documents » de cette spec sont simplement des
> **fichiers** : des fichiers propres à l'application, qui savent faire des choses compliquées
> (formulaire, vote, collecte, paiement, PDF figé…). Un fichier importé (PDF, photo, Excel) est aussi un
> fichier ; seule son icône le distingue. Les termes « A-document », « A-modèle », « document vivant »
> restent dans ce texte comme noms techniques le temps de la réécriture ; dans l'appli on dit
> « fichier » et « modèle ».

---

## 1. Objectif

Donner à chaque organisation un **espace en arborescence**, très libre (chacun crée les dossiers qu'il
veut et y range ce qu'il veut), beau et rapide sur téléphone, complet sur ordinateur.

Principe central (précision de Seb du 14 octobre) : **tout élément de l'arborescence est un nœud typé**,
et n'importe quel module peut fournir des types. Un fichier ordinaire n'est qu'un type parmi d'autres.

1. **Fichier** (type `core.file`, fourni par le module documents lui-même) : n'importe quel fichier,
   Word, Excel, PDF, photo, vidéo courte, zip…
2. **Objet applicatif**, appelé « document vivant » dans cette spec : un objet complet fourni par un autre
   module, qui vit dans les tables de ce module et s'ouvre sur ses écrans. Ce peut être un document à
   fabriquer (présentation d'AG, bilan comptable, procuration) ou **une vraie fonction de l'appli posée
   dans un dossier** : une campagne d'inscription de l'association, avec son formulaire public, ses
   inscrits et ses paiements, est un nœud de l'arborescence comme un autre.

Le module documents ne sait rien de ces objets : il les **range** (déplacer, renommer, copier, corbeille),
les **reconnaît** (icône, couleur, badge, sous-titre), applique les **droits**, propose les **actions**
qu'ils déclarent, et délègue l'ouverture au module qui les fournit.

Le module documents est donc le « Finder » de l'organisation ; les autres modules y branchent leurs types.
Pour les associations, Seb les nomme « A-documents » (voir décision §12.7).

Critères de réussite :

- sur un téléphone de milieu de gamme, ouvrir l'onglet Documents et afficher un dossier de 200 éléments
  prend moins de 300 ms après réponse du serveur, sans saccade au défilement ;
- un module tiers déclare un nouveau type de nœud, avec ses actions, **sans toucher au module documents** (test
  avec un type factice `demo.note`) ;
- un membre ne voit jamais un élément qu'il n'a pas le droit de lire, y compris dans la recherche,
  les récents et les compteurs (test).

## 2. Ce qui existe dans Contretemps (commit `183795c`)

- **Docs** (`frontend/src/screens/DocsScreen.jsx`, `frontend/src/data/documents.js`) : prototype
  frontend seulement, sans serveur. Sélecteur `Public | Privé | Personnel`, documents écrits en JSON
  (sections, paragraphes), lecture et impression. **On garde l'idée des trois espaces**, le reste est
  remplacé. Les documents générés (procuration) deviennent des documents vivants (§5).
- **Vidéos** (`backend/src/videos/`) : seule vraie gestion de fichiers aujourd'hui, à reprendre dans le
  core :
  - un dossier par école sur disque (`stockage.py`, `VIDEOS_DIR/<ecole_id>/…`), chemin relatif en base ;
  - **envoi par blocs reprenable** (`Televersement`, `ecrire_bloc` avec contrôle du décalage, nettoyage
    des envois abandonnés), éprouvé en production sur mobile ;
  - vignette générée côté serveur (`poster.py`), parce que les navigateurs mobiles n'affichent pas la
    première image d'une vidéo ;
  - usage disque par école calculé à la demande.
  - Faiblesse à ne pas reproduire : fichiers servis en statique (`app.mount("/media/videos", StaticFiles…)`),
    donc **sans contrôle d'accès** : quiconque a l'URL lit le fichier.
- Icônes : `frontend/src/components/Icon.jsx`, SVG en ligne façon Tabler Icons, sans dépendance.

Conséquence : le stockage et l'envoi par blocs montent dans le **core** (`storage`, déjà prévu en 01 §3.1),
les vidéos et les documents s'appuient dessus.

## 3. Choix techniques

### 3.1 Frontend : on assemble, on n'installe pas un explorateur tout fait

Vérifié sur npm le 14 octobre 2026 :

| Bibliothèque | Dernière version | Licence | Verdict |
|---|---|---|---|
| Chonky | 2.3.2, janvier 2022 | MIT | abandonnée, écartée |
| SVAR React File Manager (`@svar-ui/react-filemanager`) | 2.6.0, juin 2026 | MIT | bien maintenue, mais pensée pour le bureau (barre latérale, menus contextuels) et avec son propre style ; elle imposerait son IHM et sa charte |
| `@cubone/react-file-manager` | 1.35.0, décembre 2025 | MIT | idem, rendu « Windows » |
| **`@headless-tree/react`** | 1.7.0, mai 2026 | MIT | **retenue** pour l'arbre du bureau : sans style, accessible clavier, glisser-déposer, virtualisation |
| `react-arborist` | 4.0.1, octobre 2026 | MIT | alternative valable si headless-tree déçoit |
| **`@dnd-kit/core`** | 6.3.1, décembre 2024 | MIT | **retenue** pour le glisser-déposer, souris **et doigt** (capteur tactile avec appui long), clavier ; la v6 est stable, `@dnd-kit/react` 0.5 (juin 2026) n'est pas encore en 1.0 |
| `@atlaskit/pragmatic-drag-and-drop` | 4.0.0, septembre 2026 | Apache-2.0 | écartée : repose sur le glisser natif HTML5, peu fiable au doigt sur mobile |
| **`@tabler/icons-react`** | 3.49.0, octobre 2026 | MIT | **retenue** pour les pictogrammes : même style que `Icon.jsx` actuel, 5 000+ icônes, import à l'unité |
| `react-file-icon` | 1.6.0, février 2025 | MIT | écartée : rendu « feuille cornée » daté, pas de types maison |
| **`yet-another-react-lightbox`** | 3.32.2, juillet 2026 | MIT | **retenue** : visionneuse photo, balayage et pincement sur mobile |
| **`react-pdf`** (pdf.js) | 11.0.0, septembre 2026 | MIT (pdf.js Apache-2.0) | **retenue** pour lire un PDF sur mobile, où l'aperçu PDF intégré des navigateurs est médiocre ; chargée à la demande |
| `@uppy/core` + `@uppy/tus` | 6.x, septembre 2026 | MIT | non retenue : il faudrait un serveur tus ; l'envoi par blocs maison existe et marche |

Raison principale : aucun explorateur tout fait n'est conçu « mobile d'abord », et la règle IHM AppBase
(barre du bas, onglets, sélecteur) doit rester maîtresse. Sur mobile l'arbre n'est **pas** affiché : on
navigue dossier par dossier comme dans l'app Fichiers d'iOS, avec un fil d'Ariane. L'arbre est en colonne sur ordinateur, en tiroir
sur téléphone, avec les mêmes fonctions des deux côtés (§6.0).

### 3.2 Backend : stockage derrière une interface, disque local d'abord

Vérifié sur PyPI le 14 octobre 2026 :

| Bibliothèque | Version | Licence | Usage |
|---|---|---|---|
| **`obstore`** | 0.11.1, août 2026 | MIT (selon le dépôt GitHub) | **retenue** : même API pour disque local (`LocalStore`), S3, Scaleway, OVH, R2, Azure ; flux, rapide (Rust) |
| `fsspec` | 2026.9.0 | BSD-3 | alternative, plus large mais plus lâche |
| `fs` (PyFilesystem2) | 2.4.16, mai 2022 | MIT | abandonnée, écartée |
| `boto3` | 1.43 | Apache-2.0 | inutile si obstore |
| **`puremagic`** | 2.2.0, avril 2026 | MIT | **retenue** : reconnaître le vrai type d'un fichier par ses premiers octets, sans libmagic |
| **`pypdfium2`** | 5.14.0, octobre 2026 | BSD-3 / Apache-2.0 | **retenue** : vignette de la 1re page d'un PDF |
| **`Pillow`** | 12.3.0 | MIT-CMU | **retenue** : vignettes d'images, rotation EXIF |
| `tuspyserver` | 4.4.2 | MIT | non retenue (voir Uppy) |

Décision par défaut : **disque local du VPS** (`STORAGE_URL=file:///data/storage`), sauvegardé avec le
reste, et passage à un stockage S3-compatible européen par simple changement de `STORAGE_URL` quand le
volume ou un deuxième serveur le demandera. obstore rend ce changement sans code.

Aperçus Office (Word, Excel, PowerPoint) : conversion en PDF par **LibreOffice sans écran**, dans le
worker (même image, autre commande, 01 §3.1), seulement à la demande et mise en cache. Voir décision §12.4.

## 4. Modèle de données

Toutes les tables héritent de `OrgScoped` (01 §5). Identifiants en anglais, libellés en français.

### 4.1 Core : `stored_files` (contenu binaire)

Le core stocke des **contenus**, pas des documents. Adressage par empreinte : deux versions identiques ne
prennent pas deux fois la place, la sauvegarde est simple.

| Colonne | Type | Remarque |
|---|---|---|
| `id` | bigint | |
| `organization_id` | fk | dossier `<org>/` dans le stockage, comme les vidéos aujourd'hui |
| `sha256` | char(64) | unique par organisation |
| `size` | bigint | octets |
| `mime` | text | détecté par puremagic, jamais celui annoncé par le navigateur |
| `storage_key` | text | `<org>/<sha256[:2]>/<sha256>` |
| `thumbnail_key` | text null | WebP 480 px |
| `preview_key` | text null | PDF de prévisualisation (Office) |
| `ref_count` | int | nombre de versions qui l'utilisent ; 0 → purgé par une tâche périodique |
| `created_at` | timestamptz | |

Façade du core (ajout à `StorageService`, 01 §4.1) :

```python
@runtime_checkable
class StorageService(Protocol):
    def begin_upload(self, db, *, organization_id: int, filename: str, size: int) -> UploadId: ...
    def write_chunk(self, db, upload_id: UploadId, offset: int, data: bytes) -> int:
        """Reprend `Videos.ecrire_bloc` : refuse un bloc qui ne commence pas à l'octet attendu
        (renvoie l'octet attendu, le client reprend de là)."""
    def finish_upload(self, db, upload_id: UploadId) -> StoredFileId:
        """Calcule le sha256, détecte le type, déduplique, planifie la vignette."""
    def open(self, db, file_id: StoredFileId) -> BinaryIO: ...
    def download_response(self, file_id: StoredFileId, *, filename: str, inline: bool) -> Response:
        """Réponse HTTP avec Range ; jamais d'URL statique publique."""
    def usage(self, db, organization_id: int) -> StorageUsage: ...   # total, par module, quota
```

La vidéo migre sur ces mêmes appels (étape 7 de 01, module `media`).

### 4.0 Les trois espaces (définition de Seb du 15 octobre)

| Espace | Qui voit | Usage | Garde-fous |
|---|---|---|---|
| **Public** | **tout le monde**, y compris un visiteur du web sans compte ; chaque élément a une adresse `https://<préfixe>.<appli>.silvaplana.cloud/docs/<chemin>` (préfixe choisi par l'organisation, §5.5) | vitrine de l'association : statuts, règlement intérieur, plaquette, tarifs, pages de l'A-site, formulaires d'inscription ouverts | déposer ou déplacer un élément vers Public demande une confirmation explicite (« Visible par tout le monde sur internet ») ; un A-document qui contient des données de membres (bloc Données en direct sur les membres, réponses nominatives) est refusé ou demande de masquer ces blocs ; modifier reste réservé aux rôles autorisés ; pages indexables par les moteurs de recherche seulement si l'organisation l'active |
| **Privé** | **certains membres seulement** : ceux à qui un dossier ou un document est partagé (membres, groupes, rôles, §4.4 bis) ; les admins voient tout | la vie interne : comptes, comptes rendus de bureau, documents d'un cours partagés à son groupe, documents pour tous les adhérents (partagés au groupe « Adhérents ») | rien n'est visible par défaut aux simples membres ; un lien de partage externe avec expiration reste possible (§4.5) |
| **Personnel** | **uniquement l'utilisateur**, même pas les admins | brouillons, notes, fichiers perso | aucun partage, aucun lien ; pour partager, on déplace vers Privé ou Public |

Conséquences : les trois espaces ont les mêmes fonctions (dossiers, A-documents, glisser-déposer) ; les
dossiers système Permanent et Saison (§4.7) existent dans Public et Privé ; un A-document « publié en
ligne » (§5.5) peut vivre dans Privé et n'exposer que sa page publique, alors que tout ce qui est dans
Public est lisible tel quel.

### 4.2 Module : `doc_nodes` (l'arborescence)

Une seule table pour dossiers, fichiers et documents vivants.

| Colonne | Type | Remarque |
|---|---|---|
| `id` | bigint | |
| `organization_id` | fk | |
| `space` | enum `public`, `private`, `personal` | les trois espaces (§4.0) |
| `owner_member_id` | fk null | obligatoire si `space = personal` |
| `parent_id` | fk null → `doc_nodes` | null = racine de l'espace |
| `path` | text | chemin matérialisé `/12/57/` pour lire un sous-arbre en une requête (index `text_pattern_ops`) |
| `kind` | enum `folder`, `file`, `living` | |
| `type_key` | text | `core.folder`, `core.file`, ou un type déclaré : `assembly.deck`, `accounting.balance`… |
| `name` | text | unique parmi les frères non supprimés (comparaison sans casse ni accents) |
| `current_version_id` | fk null | fichiers seulement |
| `ref_id` | bigint null | documents vivants : identifiant dans les tables du module propriétaire |
| `pinned` | bool | épinglé en tête de dossier |
| `restricted` | bool | dossiers seulement : accès restreint, arrête l'héritage (§4.4 règle 3), admins seuls |
| `created_by`, `updated_by` | fk members | |
| `created_at`, `updated_at` | timestamptz | |
| `deleted_at` | timestamptz null | corbeille, purge à 30 jours |

Profondeur maximale : 8 niveaux, refusée au-delà (lisibilité sur mobile).

### 4.3 `doc_versions`

| Colonne | Type | Remarque |
|---|---|---|
| `id`, `node_id` | | |
| `number` | int | 1, 2, 3… |
| `stored_file_id` | fk core | |
| `original_filename` | text | gardé pour le téléchargement |
| `comment` | text null | « Version votée en CA » |
| `created_by`, `created_at` | | |

Téléverser un fichier du même nom dans le même dossier propose « Nouvelle version » ou « Garder les
deux ». Les 20 dernières versions sont gardées, les plus anciennes purgées sauf si commentées.

Un document vivant peut être **figé** : le module propriétaire produit un fichier (PDF, PPTX) qui devient
une version du nœud. Le document reste vivant, la version figée sert d'archive et de partage.

### 4.4 Droits : `doc_acl` (modèle validé par Seb le 15 octobre, façon Google Drive)

**Trois niveaux**, donnés à une personne, à un groupe ou à un rôle :

| Niveau | Sur un **dossier** | Sur un **fichier** |
|---|---|---|
| `view` (Lecture) | voir le dossier et son contenu | ouvrir, télécharger, voir l'aperçu |
| `edit` (Écriture) | **ajouter, renommer, déplacer, supprimer** des éléments à l'intérieur | **modifier le contenu** (nouvelle version, édition, génération IA) |
| `manage` (Gestion) | Écriture + partager, changer les droits | Écriture + partager, changer les droits, modifier un fichier Validé |

Écrire dans un dossier et écrire dans un fichier ne portent pas sur la même chose (logique Unix) :
**renommer, déplacer ou supprimer un élément demande `edit` sur son dossier parent**, modifier son contenu
demande `edit` sur l'élément lui-même. Exemple de Seb : dossier en lecture seule, fichier en écriture à
l'intérieur → on peut modifier le fichier, mais pas le renommer, le supprimer ni le sortir du dossier.

| Colonne | Type |
|---|---|
| `node_id` | fk |
| `principal_type` | enum `role`, `group`, `member` |
| `principal_id` | text (`admin`, `bureau`) ou id |
| `level` | enum `view`, `edit`, `manage` |

Règles d'évaluation (une fonction pure `effective_level(member, node)`, testée à part, appliquée dans
l'ordre) :

0. **dossier de saison close** : niveau plafonné à `view` pour tout le monde, admin compris (§4.7) ;
1. superuser et rôle `admin` : `manage` partout sauf dans l'espace personnel des autres ;
2. espace `personal` : le propriétaire a `manage`, **personne d'autre, sans exception** (pas de partage, pas
   de lien) ; pour partager, on déplace l'élément vers Privé ou Public ;
3. **héritage par ajout** : on remonte tout le chemin, du nœud jusqu'à la racine de l'espace, et on retient
   le **maximum** des entrées trouvées pour le membre, ses groupes et ses rôles. Un droit posé sur un
   fichier ou un sous-dossier peut donc **ajouter** à celui du dossier ; il n'existe pas de refus.
   **Seule exception, comme Google Drive (Seb, 15 octobre) : un dossier « Restreint »** (`doc_nodes.restricted`,
   cadenas sur l'icône). La remontée s'arrête à ce dossier : seuls ceux listés sur lui (et en dessous) y ont
   accès. Seuls les **admins** peuvent restreindre ou dérestreindre, et ils gardent toujours `manage`
   (règle 1), donc rien ne devient introuvable. Pas de restriction fichier par fichier : on range le
   fichier dans un dossier restreint ;
4. défauts des racines : `public` → `view` pour tout le monde, **y compris un visiteur anonyme du web**,
   `edit` pour `admin` ; `private` → `edit` pour les rôles listés dans les réglages de l'organisation
   (défaut `admin` **et professeurs**, Seb 15 octobre), rien pour les autres membres tant qu'un dossier ou un fichier ne leur est pas
   partagé (membre, groupe, rôle).

**Le statut passe avant les droits** (contrôlé après `effective_level`) :

- **Brouillon** : modifiable par qui a `edit` ;
- **Validé** : modifiable seulement avec `manage` ; une modification par quelqu'un qui n'a que `edit` crée
  une nouvelle version qui repart en Brouillon ;
- **Officiel** : **figé pour tout le monde**, admin compris ; pour le changer, on crée une nouvelle version
  Brouillon (la version officielle reste consultable) ;
- **Archivé** : lecture seule.

Les **groupes** sont en base (étape 2 bis du plan Contretemps : automatiques, par règle, manuels) ; un
groupe ne donne aucun droit par lui-même, seulement via `doc_acl`.

Un **fichier de l'appli** applique en plus les droits de son module (`DocumentType.can_open`) : il faut les
deux.

Toutes les listes (dossier, recherche, récents) filtrent en SQL avec une CTE sur `path`, jamais en Python
après coup.

### 4.4 bis Écran « Qui a accès ? » (plus simple que Drive, Seb 15 octobre)

Ouvert par **Partager** (menu d'actions) ou **Modifier les accès** (Propriétés › Accès). Maquette :
https://claude.ai/artifact/UB76UY2UCdPg2HYRLk19oB (appui long sur un dossier › Partager).

- **Deux grandes options** en haut, à cocher : « **Comme le dossier « AG 2026 »** » (défaut, avec la phrase
  « Les professeurs et les admins peuvent modifier ») ou « **🔒 Restreint** » (seulement les personnes
  listées et les admins ; option grisée pour qui n'est pas admin, et absente sur un fichier).
- **Ont accès par le dossier** : les accès hérités, grisés, en lecture seule (masqués en mode Restreint).
- **En plus** (ou **Seulement** en mode Restreint) : une ligne par personne ou groupe avec un interrupteur
  à deux positions **Voir | Modifier** et une croix pour retirer. Deux niveaux seulement à l'écran :
  `manage` n'est pas proposé, il reste aux admins (simplification par rapport à Drive).
- **＋ Ajouter une personne ou un groupe** : recherche unique, avec en suggestions les groupes (Bureau, le
  cours, Bénévoles…) puis les personnes ; ajouté par défaut en « Voir ».
- **Pas de bouton Enregistrer** : chaque changement s'applique tout de suite avec un bandeau
  « Bureau ajouté : peut voir · Annuler » (10 s).
- **Prévenir** : case cochée par défaut ; chaque personne ajoutée reçoit une notification push et un
  email avec un lien vers le fichier dans l'appli.
- **Envoyer par email** : bouton qui ouvre un petit formulaire (destinataires membres ou adresses
  externes, message). Pour un membre, l'email contient un lien vers l'appli. Pour une adresse externe,
  il contient un **lien de partage** (§4.5) qui expire, et en option le **PDF** de la dernière version
  officielle en pièce jointe (ex : convocation d'AG). Envoi par `send_email` du core, donc tracé dans
  « Emails envoyés » ; la spec email devra accepter des pièces jointes (taille max 10 Mo, au-delà le lien
  seul).
- **Copier le lien** : lien interne (membres ayant le droit) ou lien de partage public si activé.

Un A-document qui passe **Officiel** peut déclencher un envoi prévu par son type (ex : le procès-verbal
envoyé à tous les adhérents) : action proposée, jamais automatique.

Les partages et envois sont inscrits dans `doc_activity`. Le panneau d'infos affiche « Partagé avec » en
pastilles d'avatars.

### 4.5 `doc_share_links` (liens externes)

Lien public en lecture seule vers un fichier ou un dossier : jeton aléatoire de 32 octets, date
d'expiration obligatoire (défaut 30 jours), mot de passe facultatif, compteur de téléchargements.
Utile pour envoyer la convocation d'AG à des non-membres.

### 4.6 `doc_activity`

Journal : qui a créé, renommé, déplacé, téléchargé, supprimé, restauré. Sert à l'écran « Activité » et
aux récents.

### 4.7 Dossiers obligatoires : Permanent et un par saison (demande de Seb du 14 octobre)

**Précision de Seb du 15 octobre : seulement dans Privé**, et **un dossier par saison définie dans l'appli**,
créé automatiquement avec la saison. Public et Personnel restent libres. Dans **Privé**, la racine contient
donc des **dossiers système** (Permanent créé avec l'organisation, confirmé par Seb le 15 octobre, et un
dossier par saison), impossibles à renommer, déplacer ou supprimer (`doc_nodes.system_kind` :
`permanent` ou `period`, et `period_id`) :

```
Privé
├── 📌 Permanent            statuts, règlement, logo, contrats longs… (toujours modifiable)
├── 📅 Saison 2026-2027     saison en cours : lecture-écriture
├── 🔒 Saison 2025-2026     saisons passées : lecture seule
└── 🔒 Saison 2024-2025
```

- **Source des saisons** : le module `periods` (01 §3.2), qui fait déjà la portée par saison et le verrou
  « lecture seule » des saisons passées (`saisons/portee.py` dans Contretemps). Libellé fourni par l'app :
  « Saison » pour Contretemps, « Exercice » ailleurs.
- **Le dossier de saison existe dès que la saison existe** (Seb, 15 octobre ; remplace « à la demande » du
  14 octobre) : les saisons déjà définies reçoivent leur dossier à l'installation du module. L'écran de
  création d'une nouvelle saison (module `periods`) contient une étape « Documents » (slot
  `periods.create.steps`) qui choisit seulement son **contenu de départ** :
  - **Dossier vide** ;
  - **Copie de la saison précédente** : les sous-dossiers et leur contenu, avec une liste à cocher pour
    exclure des sous-dossiers ; les fichiers sont copiés (même contenu stocké, aucune place en plus), les
    A-documents sont reconduits en **Brouillon** avec leur prompt, leurs documents liés et leurs consignes,
    prêts à être régénérés pour la nouvelle année ;
- **Lecture seule du passé** : dans un dossier de saison close, le niveau effectif de tout membre est
  plafonné à `view` (§4.4, règle 0, avant toutes les autres, admin compris) : ni ajout, ni
  modification, ni génération IA, ni déplacement vers ou depuis ce dossier, ni changement d'état.
  Les partages et liens publics existants restent valables en lecture.
- **Reprendre pour cette saison** : action sur tout élément d'une saison passée ; copie l'élément dans
  le même chemin de la saison en cours. Pour un A-document, la copie garde le prompt, les documents liés
  et les consignes, et passe en Brouillon : « Présentation AG 2026 » se refait en deux minutes à partir de
  celle de 2025. C'est la mémoire de l'association d'une année sur l'autre.
- **Correction exceptionnelle** : seul le superuser peut rouvrir temporairement une saison close
  (décision tracée dans `doc_activity`, avec motif), comme pour les autres données de saison.
- **Sans module `periods`** : seul le dossier Permanent existe, rien n'est verrouillé.
- **Public et Personnel** restent libres : pas de dossiers obligatoires, pas de verrou.
- Sur ordinateur et téléphone, les saisons passées sont regroupées sous un dossier repliable
  « Saisons précédentes » dès qu'il y en a plus de trois, avec le cadenas sur leurs tuiles.

### 4.8 Retour au dernier endroit (demande de Seb du 14 octobre)

L'explorateur **se souvient d'où l'on était** et y revient à la prochaine ouverture, sur téléphone comme
sur ordinateur, et d'un appareil à l'autre :

- table `doc_member_state` (une ligne par membre et par organisation) : espace actif, dernier dossier
  ouvert, élément sélectionné ou ouvert en aperçu, vue choisie (liste, détails, grandes icônes) et tri
  par dossier, branches de l'arbre dépliées ;
- enregistrée côté serveur (pas seulement `localStorage`), mise à jour sans attendre à chaque
  navigation (au plus une écriture toutes les 2 secondes) ;
- à l'ouverture de Documents, on revient dans ce dossier, avec l'aperçu ouvert s'il l'était ; le
  bouton retour et le fil d'Ariane fonctionnent normalement à partir de là ;
- si le dossier a été supprimé, déplacé hors de portée ou si le droit a été retiré, on revient au plus
  proche parent encore accessible, avec un bandeau discret qui dit pourquoi ;
- au changement de saison, si le dernier endroit était dans la saison qui vient de se clore, on
  propose « Aller à la saison en cours ».

## 5. Types de documents vivants

### 5.1 Déclaration côté backend

Un module ajoute à son manifeste (01 §5) une liste `document_types`. Le module documents les lit au
démarrage ; il ne dépend d'aucun d'eux.

```python
from appbase_modules.documents.api import DocumentType

module = Module(
    id="assembly",
    depends_on=["core", "documents"],
    document_types=[
        DocumentType(
            key="assembly.deck",              # préfixé par l'id du module
            label="Présentation d'AG",
            label_plural="Présentations d'AG",
            create=create_deck,               # (db, member, name) -> ref_id
            delete=delete_deck,               # (db, ref_id) -> None
            duplicate=duplicate_deck,         # facultatif
            freeze=export_deck_pptx,          # facultatif : (db, ref_id) -> (bytes, filename, mime)
            search_text=deck_text,            # facultatif : texte indexé pour la recherche
            can_open=None,                    # facultatif : droit supplémentaire du module
            content_schema=DeckContent,       # pydantic : contenu stocké en version (§5.4)
            ai_instructions=DECK_INSTRUCTIONS,  # consignes de génération propres au type
            default_prompts=[DEFAULT_AG_PROMPT],
            suggested_model_tier="best",      # "fast" | "balanced" | "best"
            statuses=("draft", "validated", "official"),
            subtitle=deck_subtitle,           # facultatif : (db, ref_id) -> "12 diapos · prête"
            actions=[                         # facultatif : actions en plus dans la feuille d'actions
                NodeAction("present", "Présenter", icon="player-play", level="view"),
                NodeAction("send", "Envoyer aux membres", icon="send", level="manage"),
            ],
            single_per_folder=False,
            allowed_spaces={"shared", "private"},
        ),
    ],
)
```

Exemples prévus : `assembly.deck` (présentation d'AG), `assembly.minutes` (procès-verbal),
`accounting.balance` (bilan), `registration.campaign` (campagne d'inscription en ligne : ouvrir le
nœud = voir les inscrits ; sous-titre « ouverte · 212 inscrits » ; actions « Copier le lien public »,
« Clore les inscriptions »), `forms.proxy` (procuration à remplir).

Le type `core.file` est déclaré exactement de la même façon par le module documents lui-même (ouverture =
visionneuse, actions Versions et Télécharger). Ainsi aucune branche « si c'est un fichier » ne traîne dans
l'IHM : la liste, la feuille d'actions, la recherche et les droits traitent tous les nœuds pareil.
Seul le dossier (`core.folder`) reste à part, parce qu'il contient d'autres nœuds.

Une action déclarée est appelée par `POST /api/documents/nodes/{id}/actions/{key}`, qui vérifie le
niveau de droit puis délègue au module (`DocumentType.run_action(db, member, ref_id, key)`), ou ouvre
un écran du module si l'action en déclare un côté frontend.

### 5.2 Façade publique du module documents

D'autres modules rangent leurs productions dans l'arborescence sans connaître ses tables :

```python
@runtime_checkable
class DocumentsApi(Protocol):
    def ensure_folder(self, db, *, space: Space, path: list[str],
                      acl: list[AclEntry] | None = None) -> NodeId:
        """Crée au besoin « Inscriptions / 2026-2027 » et renvoie le dossier. Idempotent."""
    def add_file(self, db, *, folder_id: NodeId, filename: str, data: bytes | BinaryIO,
                 author_id: MemberId, comment: str | None = None) -> NodeId:
        """Nouveau fichier, ou nouvelle version si le nom existe déjà."""
    def add_living(self, db, *, folder_id: NodeId, type_key: str, ref_id: int,
                   name: str, author_id: MemberId) -> NodeId: ...
    def node_for(self, db, *, type_key: str, ref_id: int) -> NodeId | None: ...
    def effective_level(self, db, member_id: MemberId, node_id: NodeId) -> Level | None: ...

# Événements publiés
class NodeCreated(BaseModel, frozen=True): node_id: int; kind: str; type_key: str; author_id: int
class NodeMoved(BaseModel, frozen=True): node_id: int; old_parent_id: int | None; new_parent_id: int | None
class NodeDeleted(BaseModel, frozen=True): node_id: int; type_key: str; ref_id: int | None
```

Exemple : le module `registration` appelle `ensure_folder(space="private", path=["Inscriptions", "2026-2027"])`
puis `add_file(...)` pour chaque dossier PDF généré. Les trésoriers les retrouvent dans Documents.

### 5.3 Déclaration côté frontend

Le manifeste web du module propriétaire contribue au slot `documents.types` :

```ts
contributes: {
  'documents.types': [{
    key: 'assembly.deck',
    label: "Présentation d'AG",
    icon: 'presentation',          // nom Tabler
    color: 'amber',                // une des 12 teintes de la charte, jamais un hex libre
    badge: 'AG',                   // 2-3 caractères affichés sur la tuile
    open: lazy(() => import('./DeckEditor')),       // écran plein, route /documents/n/:nodeId
    preview: lazy(() => import('./DeckPreview')),   // facultatif : panneau d'aperçu sur ordinateur
    createLabel: 'Nouvelle présentation d’AG',
    createRoles: ['admin', 'bureau'],
  }],
}
```

`SlotName` (01 §4.4) gagne `'documents.types'`. Un type déclaré côté backend sans pendant frontend
s'affiche avec une tuile grise « Type inconnu » et n'est pas ouvrable : erreur explicite en dev.

### 5.4 Socle commun des A-documents (précisions de Seb du 14 octobre)

Tout A-document (document vivant) a les mêmes six choses, fournies **par le module documents** et non
réécrites par chaque type : un état, un espace de génération par IA avec ses prompts, des modèles dont
s'inspirer, un choix du modèle d'IA, une version générée puis des versions modifiées, et le meilleur
aperçu possible. Le type n'apporte que ce qui lui est propre (schéma du contenu, éditeur, rendu).

#### État

Colonne `status` sur `doc_nodes` (A-documents seulement) : `draft` (Brouillon) → `validated` (Validé)
→ `official` (Officiel), plus `archived`.

| Passage | Qui | Effet |
|---|---|---|
| Brouillon → Validé | niveau `edit` | rien n'est figé, le document reste modifiable |
| Validé → Officiel | niveau `manage` (ex. bureau) | une version figée en PDF est créée automatiquement ; le document est **verrouillé** |
| Officiel → modifier | niveau `edit` | crée un nouveau brouillon à partir de l'officiel ; l'officiel reste en vigueur et visible tant que le brouillon n'est pas officialisé à son tour |
| → Archivé | niveau `manage` | lecture seule, masqué des récents |

L'état s'affiche en pastille sur la ligne (gris, bleu, vert) et se filtre dans la recherche. Le type
peut restreindre les états utiles (`statuses=("draft", "official")`) ; il ne peut pas en inventer.

#### Espace de génération par IA

Un panneau « Générer » sur chaque A-document contient :

- **le prompt** : ce que l'utilisateur demande, en langage courant (« Présentation de l'AG 2026, bilan de
  la saison, 3 projets pour l'an prochain, ton chaleureux ») ;
- **les modèles et sources** : les documents liés de l'A-document (voir « Documents de référence liés »
  ci-dessous), A-documents comme fichiers (la présentation de l'AG 2025, le bilan en .xlsx, le rapport
  moral en .docx), pré-cochés et décochables ;
- **le modèle d'IA** (voir plus bas) ;
- un bouton **Générer**, avec le coût estimé affiché avant de lancer.

Les prompts se **stockent** dans une bibliothèque, table `doc_prompts` :

| Colonne | Type | Remarque |
|---|---|---|
| `id`, `organization_id` | | |
| `type_key` | text | le type d'A-document concerné |
| `name` | text | « AG annuelle, ton chaleureux » |
| `body` | text | le prompt, avec variables `{{organisation}}`, `{{saison}}`, `{{date}}` |
| `default_references` | list[node_id] | modèles proposés d'office |
| `default_model` | text null | |
| `scope` | enum `personal`, `organization` | un prompt personnel peut être partagé avec l'organisation |
| `created_by`, `created_at`, `use_count` | | |

Chaque type livre aussi des prompts par défaut (`DocumentType.default_prompts`), copiables et
modifiables, jamais modifiés en place.

Chaque génération est tracée dans `doc_generations` : nœud, prompt (texte réel envoyé, y compris si le
prompt de bibliothèque a changé depuis), modèles de référence, modèle d'IA, jetons et coût, durée,
auteur, version produite. On peut donc toujours répondre à « d'où vient ce texte ? ».

#### Écran de fabrication (description de Seb du 14 octobre)

C'est le contenu du panneau « Fabrication » : discret, fermé par défaut, mais complet. De haut en bas :

```
┌ Fabrication · Présentation AG 2026 ──────────── ✕ ┐
│ État  [Brouillon ▾]     Partage  [👥 Bureau, Tous ▾] │  en-tête compact
│ Documents liés                                      │
│  [A] PV AG 2025      Inspiration                    │  pastilles, lettre
│  [B] Bilan 2025-2026.xlsx   Référence               │  attribuée dans
│  [C] Statuts.pdf     Référence        + Ajouter     │  l'ordre d'ajout
│ ─────────────────────────────────────────────────── │
│  Vous : Présentation de l'AG à partir du bilan [B], │  fil de discussion
│         même plan que [A], 12 diapos max.           │  façon ChatGPT
│  IA : ✓ Version 1 générée · 12 diapos · 0,08 €      │  chaque réponse =
│  Vous : Raccourcis la diapo 4, ajoute les chiffres  │  une version IA
│         d'adhérents de [B].                         │  (cliquable)
│  IA : ✓ Version 2 générée · 0,05 €                  │
│ ─────────────────────────────────────────────────── │
│ ┌ Votre demande… tapez @ pour citer un document ┐   │  champ de prompt
│ └───────────────────────────────────────────────┘   │  multi-lignes
│ [📎] [📚 Prompts]  Modèle [Équilibré ▾]  ≈ 0,06 €  [Générer] │
│ Coût cumulé : 0,13 € · 2 générations                │
└─────────────────────────────────────────────────────┘
```

- **Prompt en dialogue** : chaque message part avec tout l'historique de la discussion et le contenu de
  la version courante, et l'IA modifie le document au lieu de repartir de zéro (« raccourcis la diapo 4 »).
  La première demande, ou « Repartir de zéro », génère un document complet. Chaque réponse crée une
  version `ai` ; toucher la ligne de réponse affiche cette version dans l'aperçu. La discussion est
  stockée (`doc_generations` gagne `conversation_turn`) et reste attachée à l'A-document.
- **Documents liés repérés A, B, C** : chaque document lié (§ documents de référence) reçoit une lettre
  stable dans l'ordre d'ajout (après Z : AA, AB…). Dans le prompt, on écrit `[B]` ou on tape `@` pour
  choisir dans la liste ; la référence s'affiche en pastille colorée. Le bouton 📎 ouvre le sélecteur
  d'arborescence et ajoute le document comme lien (lettre suivante). À l'envoi, `[B]` est remplacé pour
  le modèle par le titre, le rôle et le contenu extrait du document B.
- **📚 Prompts** : insère un prompt de la bibliothèque, ou enregistre le message courant comme prompt.
- **État et Partage** dans l'en-tête : le sélecteur d'état (§ états) et un résumé du partage qui ouvre
  l'écran Partager (§4.4 bis).
- **Modèle** et **coût estimé** à côté de **Générer** ; le **coût cumulé** en pied de panneau.
- Sur téléphone, le panneau est plein écran ; le champ de prompt reste collé au-dessus du clavier, comme
  dans une messagerie.

#### Édition à la main (demande de Seb du 14 octobre)

Tout A-document est **modifiable à la main**, sans passer par l'IA. Trois gestes séparés, trois boutons
en haut de l'aperçu : **regarder** (l'aperçu, par défaut), **Modifier** (édition à la main),
**Fabrication** (la baguette, l'IA).

- **Aperçu et édition sont le même composant React** (`<DocumentView content mode="read" | "edit" />`, BlockNote `editable`), pas une image figée : en lecture seule par défaut et pour tout lecteur sans droit `edit`, en édition sur demande. Seuls la page publiée, le PDF et les miniatures sont des rendus figés produits côté serveur.
- **Modifier sur place** : le bouton bascule l'aperçu en mode édition, **dans le même rendu** (même
  mise en page, mêmes couleurs) ; on clique dans un texte et on tape. Pas d'écran de formulaire à part.
  Enregistrement automatique, une version `human` par session d'édition, bouton Terminé pour revenir à
  l'aperçu.
- **Éditeur de blocs** pour le document libre, les pages et l'A-site : **BlockNote**
  (`@blocknote/react` 0.55, septembre 2026, MPL-2.0, bâti sur TipTap/ProseMirror). Choisi parce qu'il
  est **par blocs avec identifiant** (exactement le modèle des opérations IA et des cadenas ci-dessus),
  qu'il accepte des **blocs personnalisés** (nos blocs Paiement, Signature, Calcul… §5.8), et qu'il a
  le menu « / », les poignées pour déplacer un bloc et le glisser-déposer. MPL-2.0 permet l'usage dans
  un produit commercial : seules les modifications des fichiers de BlockNote eux-mêmes devraient être
  publiées. **Ne pas utiliser** les paquets « XL » de BlockNote (IA, export PDF/Word), sous GPL ou
  licence payante : nos exports et notre IA sont à nous.
- **Contenu hétéroclite, un seul éditeur** (question de Seb) : texte, tableau et formulaire
  d'inscription sont tous des **blocs** dans le même éditeur React. Le contenu stocké n'est **jamais du
  HTML** : c'est la liste de blocs (JSON) ; le HTML de la page publiée, le PDF et l'aperçu en sont
  produits. Modifier une page d'inscription, c'est modifier ses blocs, exactement comme un texte.
  - texte, titres, listes, images : blocs natifs de BlockNote ;
  - **tableau** : bloc tableau natif de BlockNote (cellules modifiables, ajout de lignes et colonnes) ;
    un bloc Calcul (§5.8) peut s'y référer ; pas de classeur Excel complet en première version ;
  - **formulaire, paiement, signature…** : blocs personnalisés ; chacun fournit son petit éditeur
    affiché dans le bloc (pour le formulaire : liste des champs, libellé, type, obligatoire, glisser
    pour réordonner) et son rendu final ;
  - effort : texte et tableau sont fournis ; chaque bloc interactif est un composant React de taille
    modeste ; le constructeur de formulaire est le plus gros morceau.
  - Les types très mis en page (présentation à diapositives) gardent leur propre éditeur, mais chaque
    diapo reste une suite de blocs pour que l'IA et l'humain travaillent pareil.
  - **Présentation de l'AG = un vrai PowerPoint (décision de Seb du 14 octobre).** On ne recrée pas un
    éditeur de diapositives. L'A-document « Présentation » garde son plan et son contenu en blocs (une
    diapo = un titre + quelques blocs), l'IA le fabrique et le modifie comme les autres, puis le serveur
    produit un **.pptx** à partir d'un gabarit PowerPoint à la charte de l'association, avec
    `python-pptx` (MIT, 1.0.2, août 2024) : chiffres des blocs de données en direct, photos, graphiques.
    On le télécharge et on le retouche dans PowerPoint ou LibreOffice si on veut ; le PDF figé est produit
    à partir du .pptx par LibreOffice (déjà prévu pour les aperçus Office). Un .pptx déposé tel quel
    reste un simple fichier (`core.file`).
- **Mise en page : flux de blocs, pas de placement libre** (question de Seb) : les blocs se suivent de
  haut en bas et se **réordonnent** à la main (poignée, glisser-déposer, au doigt aussi) ou par l'IA ; on
  ne place pas un bloc à des coordonnées x/y comme dans Canva. Raisons : le même document doit s'afficher
  bien sur téléphone, en PDF et en page web ; l'IA manipule facilement une liste ordonnée, pas des
  positions ; un placement libre casse dès que le texte change de longueur.
  Pour la richesse de mise en page, chaque bloc a des **options de disposition** (largeur pleine ou
  normale, alignement, image à gauche ou à droite du texte, encadré, fond de couleur de la charte) et
  un bloc **Colonnes** (2 ou 3 colonnes sur ordinateur et PDF, empilées sur téléphone), écrit par nous :
  l'extension multi-colonnes de BlockNote fait partie des paquets XL (GPL ou payante).
  Blocs de médias du socle : image (avec légende, recadrage), galerie, vidéo (stockage protégé, vignette),
  **lien enrichi** (titre, image et description de la page), vidéo YouTube ou Vimeo intégrée, fichier
  joint (tuile cliquable vers un nœud de l'arborescence), séparateur, citation, encadré « À retenir ».
- Alternative si BlockNote limite : **TipTap** (`@tiptap/react` 3.32, MIT), plus bas niveau.
- **Types packagés** : chacun fournit son éditeur (`open`, §5.3) ; pour une présentation, édition
  diapo par diapo dans l'aperçu. Leur contenu reste des blocs avec identifiants pour que l'IA et
  l'humain travaillent sur la même structure.
- **Sur téléphone** : même édition sur place ; la barre de mise en forme se colle au-dessus du clavier ;
  un appui long sur un bloc ouvre ses actions (déplacer, dupliquer, verrouiller, supprimer).
- **Deux personnes en même temps** : première version, un seul éditeur à la fois (verrou d'édition
  visible : « Marie modifie ce document ») ; édition simultanée (Yjs) en phase 2 si le besoin apparaît.

#### Un seul document, modifié par l'IA ou à la main (question de Seb du 14 octobre)

Il n'y a **qu'un document** : la version courante (`content_json`). L'IA et l'humain modifient le même
contenu, chacun leur tour ; chaque modification crée une version (`ai` ou `human`). Règles :

1. **L'IA part toujours de la version courante**, jamais de sa propre dernière réponse. Si quelqu'un a
   corrigé un chiffre à la main, la demande suivante part du document corrigé.
2. **Les modifications à la main entrent dans la discussion.** À chaque enregistrement manuel, le module
   calcule la différence avec la version précédente et ajoute au fil un événement visible :
   « Seb a modifié à la main : diapo 3, titre ; diapo 5, montant 1 200 € → 1 250 € ». L'IA reçoit ces
   événements avec l'historique : elle sait ce qui a été changé, par qui, et le respecte.
3. **L'IA modifie par opérations, pas en réécrivant tout.** Sauf demande « Repartir de zéro », elle
   renvoie une liste d'opérations sur les blocs (`replace(block_id, …)`, `insert_after(block_id, …)`,
   `delete(block_id)`, `move(…)`), en sortie structurée. Ce qu'elle ne touche pas reste identique au
   caractère près, y compris les corrections manuelles.
4. **Blocs verrouillés.** Un bloc modifié à la main est marqué « retouché » ; l'utilisateur peut le
   **verrouiller** (cadenas). L'IA ne modifie jamais un bloc verrouillé ; si la demande l'exige, elle le
   dit dans sa réponse (« la diapo 5 est verrouillée, je ne l'ai pas changée »).
5. **Voir ce que l'IA a changé.** Après chaque génération, l'aperçu surligne les blocs modifiés pendant
   quelques secondes, et la ligne de réponse du fil propose « Voir les changements » (comparaison avant
   / après) et « Annuler cette génération » (retour à la version précédente, sans perte).
6. **Discussions longues.** Ce qui fait foi est le document courant, pas le fil : au-delà de 20
   échanges, les plus anciens sont résumés automatiquement (décisions prises, consignes de ton,
   préférences) et le résumé remplace le détail dans l'appel au modèle. Le fil complet reste lisible.
7. **Consignes durables.** L'utilisateur peut épingler une consigne dans le fil (« toujours tutoyer »,
   « jamais plus de 12 diapos ») : elle est envoyée à chaque génération, même après résumé, et peut être
   reprise dans un A-modèle (§5.6).

Ce que reçoit le modèle à chaque génération : consignes du type, consignes épinglées, résumé des
anciens échanges, échanges récents (demandes, réponses, modifications manuelles), document courant
avec identifiants de blocs et marques retouché/verrouillé, contenu des documents liés cités.

#### Documents de référence liés

Un A-document garde une liste **permanente** de documents de référence, liés à lui (et pas seulement
choisis le temps d'une génération) : les statuts et le PV de l'an dernier pour le PV de l'AG, le bilan
.xlsx pour la présentation, etc. Table `doc_links` :

| Colonne | Type | Remarque |
|---|---|---|
| `node_id` | fk | l'A-document |
| `target_id` | fk | le document lié, n'importe quel nœud (fichier, A-document, ou dossier entier) |
| `role` | enum `reference`, `inspiration`, `annex` | *Référence* : source de faits ; *Inspiration* : modèle de forme et de ton ; *Annexe* : jointe au document final et à ses envois |
| `version_mode` | enum `latest`, `pinned` | suivre la dernière version, ou figer celle du moment (`pinned_version_id`) |
| `note` | text null | « reprendre le plan de celui-ci » |
| `position` | int | ordre affiché |

- **Sélection dans l'arborescence** : bouton « Ajouter des documents liés » qui ouvre **le même
  explorateur** (§6.0) en mode *sélection* : arbre, recherche, cases à cocher, sélection multiple,
  dans tous les espaces auxquels le membre a accès. Le même mode sert à « Déplacer… » et à tout module
  qui a besoin de choisir un document (`<NodePicker multiple types={[...]} />` dans la façade web).
  On peut aussi glisser un fichier de l'explorateur sur la zone « Documents liés ».
- **Utilisation par l'IA** : à chaque génération, les documents liés sont pré-cochés comme sources (§
  génération), avec leur rôle transmis au modèle (« faits » ou « inspiration ») ; on peut en décocher
  pour une génération sans les délier.
- **Affichage** : dans l'aperçu, une section discrète « Documents liés » (tuiles cliquables) ; dans le
  document lié, une section « Utilisé par » (liens inverses). Les annexes apparaissent en fin de PDF
  figé et en pièces jointes ou liens dans les envois par email (§4.4 bis).
- **Droits** : un lien ne donne aucun droit. Un lecteur qui n'a pas accès au document lié voit
  « 1 document lié non accessible », sans nom.
- **Robustesse** : les liens suivent les déplacements et renommages (liés par id). Un document lié mis
  à la corbeille s'affiche barré avec « Restaurer » ; purgé, le lien disparaît et l'activité le note.

#### Comment la génération fonctionne

Le module documents fait la génération pour tous les types ; un type ne code rien pour être générable :

1. il déclare `content_schema` (modèle pydantic du contenu : pour une présentation, une liste de
   diapositives avec titre, points, notes) et `ai_instructions` (consignes propres au type) ;
2. le module documents extrait le texte des modèles de référence : un A-document fournit son contenu
   JSON, un fichier passe par **`markitdown`** (MIT, septembre 2026 : Word, Excel, PowerPoint, PDF vers
   Markdown), images envoyées telles quelles au modèle ;
3. il appelle l'API Claude via le SDK `anthropic` déjà utilisé par Contretemps
   (`inscriptions/lecture_fiche.py`), en **sortie structurée** conforme à `content_schema` ;
4. le résultat est validé par pydantic puis enregistré comme version « Générée par IA ».

La génération tourne dans le worker (elle peut prendre une minute), l'écran suit la progression en
temps réel (`documents.generation.{id}`) et l'utilisateur peut quitter l'écran.

#### Choix du modèle d'IA

- La liste des modèles proposés et leur prix viennent de la **configuration de l'app**, jamais du code
  du module (`AI_MODELS` dans les réglages, un modèle par défaut), pour suivre les sorties de nouveaux
  modèles sans redéployer de code.
- L'organisation choisit dans ses réglages les modèles autorisés et un plafond mensuel de dépense ;
  l'écran Admin > Documents > Stockage gagne la consommation IA du mois.
- À la génération, l'utilisateur choisit parmi les modèles autorisés, présentés par usage plutôt que par
  nom technique : « Rapide et économique », « Équilibré », « Meilleure qualité », avec le coût estimé.
- Défaut : le prompt de bibliothèque peut imposer un modèle, sinon le type suggère le sien
  (`DocumentType.suggested_model_tier`), sinon le défaut de l'organisation.

#### Aperçu d'abord, fabrication cachée

Principe posé par Seb : **l'important est le résultat final bien présenté.** Ouvrir un A-document montre **son aperçu**, en grand, et rien d'autre de la fabrication. Le prompt, les
modèles, le choix du modèle d'IA, l'historique des générations et le coût sont regroupés dans un
**panneau « Fabrication »** qui reste fermé par défaut :

- accès discret : une petite icône baguette dans la barre de l'aperçu et l'entrée « Fabrication » du menu
  ⋯ ; jamais de bloc de prompt affiché sous le document ;
- ouverture : tiroir à droite sur ordinateur (l'aperçu reste visible à gauche), feuille plein écran sur
  mobile ; il se referme seul après une génération réussie pour revenir à l'aperçu ;
- le bouton **Générer** (ou **Régénérer**) est dans ce panneau, avec le coût estimé à côté ;
- seule exception : un A-document tout juste créé et encore vide ouvre directement le panneau, puisqu'il
  n'y a rien à prévisualiser ;
- le panneau n'est visible que pour le niveau `edit` ; un lecteur ne voit que l'aperçu et l'état.

**Coût cumulé** : chaque A-document affiche dans son panneau Fabrication et dans ses Infos le coût total
de toutes ses générations (somme de `doc_generations.cost`), avec le détail par génération. Admin >
Documents montre le cumul du mois par organisation, par type et par membre, face au plafond mensuel.

#### Versions : générée, puis modifiée

`doc_versions` (§4.3) gagne deux colonnes : `origin` (`ai`, `human`, `frozen`) et `content_json`
(contenu de l'A-document à cette version, conforme à `content_schema` ; null pour un fichier).

Forme stockée (question de Seb du 14 octobre) : `content_json` vaut `{"schema": <n>, "blocks": [...]}`,
la liste de blocs, jamais du HTML ni du code React. **Ce format est le nôtre** : il reprend la forme
des blocs BlockNote d'aujourd'hui (paragraphe, titre, liste, tableau, image) parce que c'est l'éditeur
retenu, mais il est décrit et validé côté serveur par nos propres schémas Pydantic, et nos blocs
(signature, vote, données en direct…) sont définis par nous. Si BlockNote change de format ou si l'on
change d'éditeur (TipTap), on écrit un convertisseur à l'entrée de l'éditeur, sans toucher à la base.
Le serveur, l'IA et le rendu PDF lisent ce JSON sans dépendre de BlockNote. Les fichiers n'y figurent que par
référence (`node:<id>`) ; ce que les gens remplissent (signatures, réponses, votes) vit dans
`doc_responses`, rattaché au bloc par son `id` ; un bloc de données en direct ne contient que la
référence de sa source. `schema` est le numéro de format des blocs : un changement de format s'accompagne
d'une migration des versions existantes.

- Une génération crée une version `ai`, **jamais modifiée ensuite**.
- Les modifications de l'utilisateur dans l'éditeur du type créent des versions `human` (enregistrement
  automatique, une version par session d'édition).
- On peut comparer la version modifiée avec la version IA d'origine, revenir à n'importe quelle version,
  ou régénérer : la nouvelle version `ai` s'ajoute, rien n'est écrasé.
- Le passage en Officiel crée la version `frozen` (PDF), cf. tableau des états.

#### Version figée en PDF : même rendu que le web (question de Seb du 14 octobre)

**« Imprimer en PDF » pour chaque fichier de l'appli (Seb, 15 octobre).** Les fichiers sont pensés en A4
pour que l'impression ressemble à l'écran. Par défaut, le PDF reprend ce qu'on voit, page A4 par page A4.
**Chaque nature (modèle de fiche) déclare ce qu'elle imprime** quand ce n'est pas évident, sous forme d'une
ou plusieurs « versions imprimables » nommées : sondage ou convocation → « Version vierge » / « Avec les
réponses » ; inscription → « Formulaire à remplir » / « Liste des inscrits » ; PowerPoint d'AG → une diapo
par page. Bouton « Imprimer en PDF » dans le menu du fichier ; un choix n'apparaît que si la nature en
déclare plusieurs. Fichiers importés : un PDF reste tel quel ; Word et Excel se téléchargent (conversion
en PDF plus tard).

**Principe : on ne réécrit pas le document pour le PDF, on imprime la page web elle-même.** Le serveur
ouvre la page de rendu de la version (`/render/{version_id}?print=1`, jeton interne à usage unique) dans
**Chromium sans écran**, avec les mêmes composants React, le même CSS et les mêmes polices que l'écran,
et l'imprime en PDF A4. Contretemps le fait déjà pour la facture (`backend/src/inscriptions/facture_html.py`,
Chromium `--print-to-pdf` sur un HTML statique). Pour une page React, il faut attendre la fin du rendu :
**Playwright Python** (`page.pdf()`, après un signal `data-ready` posé par `DocumentView`), avec le
Chromium déjà installé dans l'image. Aucune seconde mise en page (pas de WeasyPrint, pas de react-pdf
renderer), donc pas de dérive entre web et PDF.

Ce qui est garanti : le texte, les titres, les tableaux, les images, les couleurs, la charte et les polices
(auto-hébergées, intégrées au PDF), les liens qui restent cliquables. Ce qui change, par nature, et qui
est décidé une fois pour toutes dans le CSS d'impression (`@media print`) :

| Élément | À l'écran | Dans le PDF |
|---|---|---|
| Largeur | téléphone : colonnes empilées | largeur A4 : la disposition ordinateur (colonnes côte à côte) |
| Pages | un long défilement | coupure en pages A4 ; un bloc n'est pas coupé (`break-inside: avoid`), numéro de page et pied de page |
| Blocs interactifs | champs, boutons | l'état au moment du gel : réponses saisies, image de la signature avec horodatage, résultat du vote, « payé le … » |
| Vidéo, audio | lecteur | vignette, lien et QR code |
| Données en direct, Calcul | valeur actuelle | valeur au moment du gel, avec la date |
| Sections repliées, onglets | repliés | tout déplié |

Chaque bloc déclare son rendu d'impression à côté de son rendu écran (§5.8, `render` sert aux deux).

**Trois rendus, un seul document (précision de Seb du 14 octobre : « ça doit être toujours joli »).**
Le même A-document doit être beau sur téléphone, sur ordinateur et en A4 ; le PDF n'est qu'une preuve,
un gel. Le compromis retenu :
- **La colonne de lecture a la largeur du texte d'une page A4** (environ 17 cm, soit ~650 px), centrée,
  sur ordinateur comme dans le PDF. L'ordinateur et le PDF sont donc quasi identiques, sans écran
  « façon Word » : seuls les sauts de page s'ajoutent dans le PDF.
- **Sur téléphone**, la même colonne se resserre : colonnes empilées, images pleine largeur, tableaux
  larges défilables ou transformés en fiches. On peut aussi concevoir et modifier depuis le téléphone.
- **Un bouton « Aperçu PDF »** montre les vraies pages A4 à tout moment, sur téléphone (zoom au doigt)
  comme sur ordinateur.
- **Chaque bloc est dessiné et testé aux trois largeurs** (téléphone 390 px, colonne 650 px, A4) : c'est
  une condition d'acceptation de tout nouveau bloc. Les blocs n'ont pas de position libre ni de taille
  fixe en pixels, c'est ce qui rend le résultat joli partout.
- L'IA connaît ces contraintes (longueur, une page pour une procuration, pas de tableau à huit colonnes).

**Ce qu'on valide est ce qu'on fige.** Avant le passage en Officiel, l'appli produit le PDF et le montre
(`react-pdf`) ; c'est ce fichier exact, et pas une nouvelle impression, qui devient la version `frozen`,
avec son empreinte sha256. Un bouton « Aperçu PDF » est disponible à tout moment pour vérifier la mise
en page. *Acceptation* : un document de test par bloc, rendu en PDF dans les tests, comparé à une image
de référence (Playwright, comparaison de captures).

Conséquence pour le contrat (§5.1) : le contenu d'un A-document vit dans `content_json` de sa version
courante, géré par le module documents. Un type n'a plus besoin de ses propres tables pour un contenu
simple ; il garde des tables seulement pour ce qui vit en dehors du document (les inscrits et paiements
d'une campagne d'inscription, par exemple).

#### Le meilleur aperçu possible selon le type

L'aperçu apparaît dans le panneau de droite sur ordinateur, en plein écran sur mobile, et en miniature
dans la vue grandes icônes.

| Type | Aperçu | Outil (vérifié le 14 octobre) |
|---|---|---|
| A-document | rendu fourni par le type (`preview`), en HTML ; miniature et PDF produits côté serveur par Chromium sans écran, déjà dans la stack Contretemps | composant du type |
| PDF | pages défilables | `react-pdf` 11.0 (MIT) |
| Word | rendu fidèle dans le navigateur, sans serveur | `docx-preview` 0.4.1 (Apache-2.0, septembre 2026) |
| Excel, CSV | tableau avec onglets de feuilles | `exceljs` 4.4 (MIT, octobre 2023, peu actif) pour xlsx ; `papaparse` 5.7 (MIT) pour csv |
| PowerPoint, OpenDocument | PDF converti par LibreOffice dans le worker (phase 2), sinon miniature et téléchargement | LibreOffice |
| Image | visionneuse plein écran | `yet-another-react-lightbox` |
| Vidéo, audio | lecteur natif avec vignette | — |
| Texte, Markdown, code | texte mis en forme | `react-markdown` 10.1 (MIT) |
| Autre | grande tuile, infos, bouton Télécharger | — |

### 5.5 Publication en ligne d'un A-document (question de Seb du 14 octobre)

Certains types produisent une **page publique** : un formulaire d'inscription, une convocation, une
page d'événement. Ils déclarent `publishable=True`. L'action « Publier en ligne » rend la page
accessible immédiatement, **sans déploiement** :

- adresse : `https://<préfixe>.<appli>.silvaplana.cloud/<slug>`, ex.
  `https://le-beausset.contretemps.silvaplana.cloud/inscription`. Le **préfixe** est choisi par
  l'organisation dans sa Personnalisation (« Adresse web de l'appli », colonne `sous_domaine`, déjà en
  place dans Contretemps, SPEC §2.7) ; le `slug` de la page est proposé à partir du nom et modifiable,
  unique dans l'organisation ;
- le DNS `*.<appli>.silvaplana.cloud` et le TLS à la demande de Caddy amènent déjà tous les
  sous-domaines à l'app ; le serveur reconnaît l'organisation par l'en-tête `Host` (routes publiques
  seulement), puis une route publique du core `GET /{page_slug}` cherche la publication et demande au
  module du type de rendre la page. Changer de préfixe : l'ancien redirige 6 mois (déjà en place).
  Publier, dépublier ou changer de version = une ligne en base, effet immédiat ;
- table `doc_publications` : nœud, `slug`, version publiée (`pinned_version_id`, jamais le brouillon en
  cours), `published_by`, `published_at`, `unpublished_at`, compteur de visites ;
- seule une version **Validée ou Officielle** peut être publiée, par le niveau `manage` ; modifier le
  document ne change pas la page en ligne tant qu'on ne republie pas ;
- **sécurité** : l'IA ne produit pas de HTML brut mis en ligne tel quel. Elle produit le contenu
  structuré du type (`content_schema` : champs du formulaire, textes, tarifs), et c'est le gabarit du
  module, écrit et relu une fois, qui le rend en HTML avec la charte de l'organisation. Pas de script ni
  de lien arbitraire injecté, pas de page d'hameçonnage possible sous le domaine ;
- les envois du formulaire vont à l'API du module (`registration`), qui crée les inscriptions et les
  paiements HelloAsso ; ouvrir l'A-document dans l'appli montre les inscrits ;
- le panneau Fabrication et l'aperçu affichent l'état « En ligne » avec l'adresse, un bouton Copier et un
  QR code (affiche, flyer).

Contretemps a déjà une page publique d'inscription, mais comme appli séparée et déployée à part
(`frontend-inscription/`, routée par Caddy sous `/contretemps-inscription/`, voir `DEPLOY.md`). Le type
`registration.campaign` la remplace par une publication dynamique.

### 5.6 A-document libre et A-modèles (décision de Seb du 14 octobre)

Deux façons de créer un A-document, qui coexistent :

- **packagé** : un type fourni par un module (présentation d'AG, procuration, campagne d'inscription),
  avec son schéma, son éditeur, son rendu soignés ;
- **libre** : le type `documents.free` (« Document libre »), fourni par le module documents. Son
  `content_schema` est générique (blocs : titre, paragraphe, liste, tableau, citation, image, saut de
  page), son rendu est soigné à la charte de l'organisation, il s'exporte en PDF et en .docx. Toute la
  fabrication (§5.4) marche pareil : prompt, documents liés, versions, états, partage.

**A-modèle** : un A-document réussi, packagé ou libre, peut être **promu en A-modèle** (action « Créer un
modèle à partir de ce document », niveau `manage`). Table `doc_templates` :

| Colonne | Type | Remarque |
|---|---|---|
| `id`, `organization_id` | | |
| `source_node_id` | fk null | l'A-document d'origine (pour « mettre à jour le modèle » plus tard) |
| `base_type_key` | text | type de l'A-document d'origine (`documents.free`, `assembly.deck`…) |
| `name`, `description` | text | « Compte rendu de réunion de bureau » |
| `icon`, `color`, `badge` | text | choisis à la promotion, dans les pictogrammes et teintes de la charte |
| `prompt` | text | prompt de départ, repris de la discussion de fabrication et modifiable |
| `skeleton_json` | json | structure du document d'origine (plan, mise en forme) sans ses données |
| `link_slots` | list | documents liés à fournir à la création : soit un document fixe (les statuts), soit une case à remplir (« Le bilan de l'année ») |
| `default_status`, `default_acl` | | état et partage de départ des documents créés |
| `suggested_model_tier` | text null | |
| `scope` | enum `organization`, `catalog` | `catalog` : proposé à toutes les organisations AppBase (phase 2, validé par nous) |
| `version`, `use_count`, `created_by`, `created_at` | | |

Utilisation :

- les A-modèles apparaissent dans le menu + sous **« Modèles de l'association »**, juste après les types
  packagés, avec leur tuile (même tuile pleine, plus un petit coin plié pour dire « modèle ») ;
- créer depuis un modèle demande d'abord les cases à remplir (« Choisir le bilan de l'année » via le
  sélecteur d'arborescence), puis lance la première génération avec le prompt du modèle : on arrive
  directement sur un aperçu rempli ;
- le document créé garde un lien vers son modèle ; si le modèle est amélioré, ses futurs documents en
  profitent, les anciens ne changent pas ;
- un écran « Modèles » (onglet Admin > Documents) liste, modifie, duplique, archive les A-modèles ;
- phase 2 : les meilleurs A-modèles d'une organisation peuvent être proposés au **catalogue AppBase** ;
  validés par nous, ils deviennent disponibles pour toutes les associations (sans les données d'origine).

#### Parcours guidés : des modèles avec questions, créés par l'utilisateur (demande de Seb du 14 octobre)

Un parcours comme « Convoquer l'AG » (maquette https://claude.ai/artifact/1Ptq5myAcGYw8d6rsmjBRj) n'est
**pas codé en Python** : c'est un A-modèle enrichi, donc une donnée. **Le code fournit les briques, les
données assemblent les parcours.**

Briques (code, socle et modules) : types de question (date, lieu, texte, liste à cocher, choix, membres
ou groupe), blocs (signature, vote, émargement et quorum, paiement…), diffusion (destinataires, canal,
relances), collecte des réponses, indicateurs de suivi.

Un A-modèle peut porter, en plus de son contenu :

```json
{ "questions": [
    {"id": "date", "label": "Quand a lieu l'assemblée ?", "kind": "datetime",
     "default": {"from": "previous_instance"}, "rule": {"min_days_before_send": 15}},
    {"id": "lieu", "label": "Où ?", "kind": "place", "default": {"from": "previous_instance"}},
    {"id": "odj", "label": "L'ordre du jour", "kind": "checklist", "default": {"from": "previous_instance"}} ],
  "documents": [ {"template": "convocation"}, {"template": "procuration", "attached": true} ],
  "diffusion": {"audience": {"group": "adherents_a_jour"}, "channels": ["email", "app"],
                "reminder": {"days_before": 7, "to": "non_respondents"}},
  "collect": {"options": ["Je viens", "Je donne procuration", "Je ne viens pas"]},
  "tracking": ["opened", "answers", "quorum"] }
```

Le contenu des documents utilise les réponses comme variables (`{{date}}`, `{{lieu}}`, `{{odj}}`).
`previous_instance` reprend la valeur de la dernière fois où le parcours a servi : c'est ce qui rend le
parcours court.

**Trois façons de créer un parcours, sans code :**
1. **Depuis un document réussi** : « Faire un modèle de ce document ». L'IA repère ce qui change d'une
   fois à l'autre (date, lieu, liste) et propose d'en faire des questions ; l'utilisateur coche.
2. **En le demandant à l'assistant** : « crée un parcours pour inviter les familles au gala, avec
   réservation de places ». L'IA assemble les briques existantes ; elle ne peut pas inventer de brique.
3. **À la main**, dans l'éditeur du modèle, un sélecteur à trois positions `Contenu | Questions | Envoi` :
   - *Contenu* : les documents du parcours dans l'éditeur habituel. Sélectionner un passage
     (« 21 novembre ») puis **Transformer en question** crée la question et met la variable à sa place,
     affichée comme une pastille colorée `Date de l'AG` ; `/` → *Réponse à une question* insère une
     variable existante.
   - *Questions* : une carte par question, glisser pour réordonner ; **+ Ajouter une question** propose
     les types avec leur icône. Chaque carte : libellé, aide, obligatoire ou non, valeur par défaut
     (vide, fixe, **reprise de la dernière fois**, ou calculée simplement : « aujourd'hui + 15 jours »).
     Les conditions (« ne poser cette question que si… ») viennent en phase 2.
   - *Envoi* : destinataires (membres, groupe, rôle), canaux, relances, réponses proposées, indicateurs
     de suivi à afficher.
   - **Essayer** joue le parcours tel que l'utilisateur le verra, en mode test : l'envoi ne part qu'à
     soi-même.

Le **kit AG** livré avec l'appli est fait de ces mêmes modèles, au même format : ce sont des données
installées avec l'application, modifiables par l'association, pas du code. Une association peut donc
corriger le parcours AG fourni ou en écrire un pour son vide-grenier.

### 5.7 A-site web de l'association (idée de Seb du 14 octobre)

Le site public de l'association est lui aussi un A-document, de type `website.site` (module `website`),
rangé où l'on veut dans l'arborescence (par défaut à la racine de l'espace Public, un par organisation).

- **Adresse** : `https://<préfixe>.<appli>.silvaplana.cloud/` (la racine de l'organisation) ; les pages publiées
  du §5.5 deviennent ses sous-pages (`/inscription`, `/ag-2026`, `/spectacle`).
- **Contenu** : l'A-site contient le thème (logo, couleurs, police de la charte), l'en-tête, le pied de
  page (adresse, contact, réseaux) et le **menu**. Chaque entrée du menu pointe vers un A-document
  publiable : une page libre (`website.page`, blocs : texte, image, galerie, carte, horaires, bouton),
  la campagne d'inscription, un événement, ou un dossier de documents publics (règlement, statuts),
  affiché comme une liste de téléchargements.
- **Fabrication** : comme tout A-document (§5.4). Exemple de prompt : « Site de l'école de danse : accueil,
  cours et horaires depuis [A], tarifs depuis [B], inscription, contact. » L'IA produit le contenu
  structuré (pages, blocs, textes), jamais du HTML libre ; les gabarits du module le rendent, rapides et
  lisibles sur téléphone.
- **Données vivantes** : un bloc peut afficher des données de l'appli à jour sans republier (planning des
  cours, prochains événements, places restantes d'une inscription).
- **Publication** : état Officiel + « Publier » met en ligne la version ; le site en ligne ne change qu'à
  la republication. Aperçu du site complet dans l'appli, sur téléphone et ordinateur.
- **Référencement** : titre, description et image de partage par page, `sitemap.xml`, adresses lisibles.
- **Phase 2** : nom de domaine propre à l'association (`www.contretemps-danse.fr`), certificat HTTPS
  automatique par Caddy (« on-demand TLS »), après vérification que le domaine pointe bien vers nous.

### 5.8 Blocs tout faits (idée de Seb du 14 octobre)

Le contenu des A-documents libres, des pages et de l'A-site est fait de **blocs**. À côté des blocs de
mise en page (texte, image, tableau), des **blocs interactifs** apportent une fonction prête à
l'emploi.

**Règle (Seb, 14 octobre) : tous les documents applicatifs sont des A-documents, donc les blocs utiles
à tous font partie du socle A-document**, fournis par le module documents lui-même et disponibles dans
**tout** A-document, quel que soit le type ou le module qui le fournit : Signature, Formulaire, Paiement,
Vote, Émargement et quorum, Événement, Dépôt de fichier, Sondage, Créneaux, Calcul, Contact, Données en
direct. Un type packagé n'a donc rien à recoder : une procuration, c'est un texte et le bloc Signature du
socle. Ce qui dépend d'un service extérieur passe par un port (Paiement → `PaymentProvider`, implémenté
pour HelloAsso ; Données en direct → sources déclarées par les modules). Les modules peuvent **en plus**
déclarer des blocs spécialisés à leur métier (ex. Billetterie, Planning des cours), avec le même
contrat :

```python
BlockType(
    key="payment.helloasso",          # préfixé par l'id du module
    label="Paiement",
    icon="credit-card", color="green",
    config_schema=PaymentConfig,       # pydantic : montant ou barème, libellé, compte HelloAsso
    render=render_payment,             # gabarit HTML (aperçu, PDF, page publique)
    on_submit=handle_payment,          # facultatif : reçoit les réponses, écrit dans les tables du module
    needs_public_page=False,           # vrai si le bloc n'a de sens qu'en ligne
    ai_hint="Bloc de paiement : propose-le quand le document demande de régler une somme.",
)
```

- Dans l'éditeur : menu « / » ou bouton « + bloc » avec la liste des blocs disponibles, en tuiles.
- L'IA peut **proposer** un bloc (le schéma de contenu les accepte, avec `ai_hint`), mais un bloc qui
  engage de l'argent ou une signature reste **à vérifier** (pastille orange) tant qu'un humain n'a pas
  relu sa configuration ; impossible de publier ou d'officialiser avant.
- Les réponses d'un bloc (paiements, signatures, votes) sont stockées par son module et apparaissent
  dans un onglet **« Réponses »** de l'A-document, exportable en .xlsx.

Blocs prévus (entre parenthèses : `documents` = socle A-document, sinon module qui fournit le bloc spécialisé ou la donnée) :

| Bloc | Usage | Remarque |
|---|---|---|
| **Paiement** (`documents`, port `PaymentProvider` → HelloAsso) | cotisation, inscription, spectacle, don | montant fixe, barème (réduction famille) ou libre ; reçu automatique |
| **Signature électronique** (`documents`) | procuration, autorisation parentale, droit à l'image, contrat d'intervenant | signature simple maison : tracé au doigt + code reçu par email + horodatage + PDF scellé avec empreinte. Suffit pour une procuration ou une autorisation ; un contrat à fort enjeu passerait par un prestataire (signature avancée) |
| **Formulaire** (`documents`) | inscription, questionnaire, candidature au bureau | champs typés, conditions d'affichage, champs pré-remplis pour les membres connectés |
| **Vote** (`documents`) | résolutions d'AG, élection du bureau | vote à main levée ou à bulletin secret, procurations comptées, résultat en direct |
| **Émargement et quorum** (`documents`) | feuille de présence d'AG | pointage sur place (QR code), procurations, quorum calculé et affiché |
| **Créneaux** (`documents`) | bénévoles pour le spectacle, permanences, covoiturage | « 3 places restantes » |
| **Billetterie** (`ticketing`) | spectacle, gala | jauge, tarifs, billet avec QR code contrôlé à l'entrée |
| **Dépôt de fichier** (`documents`) | certificat médical, justificatif | le fichier arrive dans un dossier choisi, droits restreints |
| **Événement** (`documents`) | date, lieu, « Ajouter à mon agenda » (.ics), carte d'accès | |
| **Données en direct** (`documents`, sources fournies par `activities`, `attendance`…) | planning des cours, chiffres de la saison | lu à l'affichage, jamais recopié |
| **Sondage** (`documents`) | choix d'une date, avis des adhérents | |
| **Calcul** (`documents`) | totaux, répartitions, bilan, quorum, prix | voir ci-dessous : l'IA écrit la formule, le moteur calcule |
| **Contact** (`documents`, envoi par le core) | « Écrire au bureau » | envoyé à `contact_email` de l'organisation, sans exposer l'adresse |

#### Bloc Calcul (idée de Seb du 14 octobre)

Pour les chiffres d'un document (total des cotisations, répartition par discipline, solde du bilan,
quorum, prix avec réduction famille). Fourni par le module documents (`documents.compute`).

Principe : **l'IA écrit le calcul, elle ne donne jamais le résultat.** Un modèle de langage peut se
tromper sur un nombre ; une formule exécutée ne se trompe pas, et on peut la relire.

- **Demande en français** dans le bloc : « total des cotisations encaissées par discipline à partir de
  [B] ». L'IA produit une formule, affichée sous le résultat (repliée par défaut, comme la fabrication).
- **Sources** : les documents liés (feuilles et colonnes d'un .xlsx/.csv, tableaux d'un A-document, par
  leur lettre : `B.Cotisations[Montant]`), les données de l'appli exposées par les modules (nombre
  d'adhérents, présences), les réponses des blocs (paiements, votes), d'autres blocs Calcul nommés.
- **Résultat** : nombre, tableau ou graphique simple, mis en forme (€, %, séparateurs français).
  Recalculé à chaque affichage ; figé avec la version quand le document passe Officiel (un PV garde les
  chiffres du jour du vote).
- **Moteur, première version** : formules façon tableur évaluées côté serveur par **`simpleeval`**
  (MIT, septembre 2026), qui n'exécute que des expressions autorisées (opérations, `SUM`, `AVG`,
  `COUNT`, `IF`, `ROUND`, `GROUPBY`, `FILTER`…), sans accès au disque, au réseau ni au reste du serveur.
- **Mode Python, phase 2** : pour les calculs qu'une formule ne sait pas faire, du vrai Python exécuté
  dans **Pyodide** (Python compilé en WebAssembly, MPL-2.0, septembre 2026), dans un bac à sable du
  worker sans réseau ni fichiers, avec limite de temps et de mémoire. **Jamais** de Python exécuté
  directement sur le serveur : un code écrit par un membre ou par l'IA pourrait lire les données de
  toutes les associations.
- `HyperFormula` (moteur de formules Excel complet) est écarté : licence GPL-3.0 ou payante.

Exemples d'assemblage : un **A-document procuration** = texte + bloc Signature ; une **campagne
d'inscription** = Formulaire + Dépôt de fichier (certificat) + Signature (droit à l'image) + Paiement ;
un **kit AG** = convocation (texte + Événement), procuration (Signature), feuille d'émargement
(Émargement et quorum), résolutions (Vote), PV (texte, rempli avec les résultats des votes).

### 5.9 Lien entre formulaires et membres (demande de Seb du 14 octobre)

Une inscription crée ou met à jour des **membres**. Chaque champ d'un bloc Formulaire (§5.8) peut donc
être **relié** à un champ de la base : fiche membre du core (nom, prénom, email, téléphone, date de
naissance, groupe), extension de membre de l'app (01 §6.4 : pour Contretemps, profil élève, santé,
contacts d'urgence), ou rien (réponse gardée seulement dans les réponses du formulaire).

- **Ce que l'IA voit** : le core expose la description des champs membres
  (`members.schema()` : nom technique, libellé, type, obligatoire, valeurs permises, extensions
  comprises). Elle est envoyée au modèle quand il fabrique un formulaire.
- **L'IA propose les liaisons** : en créant le formulaire, elle relie chaque champ (« Date de naissance
  de l'enfant » → `member.birth_date` du profil enfant ; « Allergies » → `student_profile.allergies`)
  et indique sa confiance.
- **Si elle ne sait pas, elle demande.** Pour un champ ambigu ou sans équivalent, l'IA ne devine pas :
  elle pose la question dans le fil de fabrication (§5.4), sous forme de **carte à choix** : « Le champ
  "Responsable légal" : le relier au contact d'urgence 1, créer un profil parent, ou le garder seulement
  dans les réponses ? ». La sortie structurée du modèle a pour cela un type `question` à côté des
  opérations. Le formulaire reste en état « liaisons à vérifier » tant qu'une question est ouverte.
- **Vérification humaine** : un écran « Liaisons » (tableau champ du formulaire → champ membre, avec
  menu déroulant) permet de corriger ; aucun formulaire relié à des membres ne peut être publié sans
  qu'un humain ait validé ce tableau (comme les blocs d'argent et de signature).
- **À la réception d'une inscription** :
  1. recherche d'un membre existant (même email et même nom et prénom, ou même email et même date de
     naissance) ;
  2. trouvé avec certitude : la fiche est mise à jour avec les champs reliés, l'ancienne valeur est
     gardée dans l'historique ;
  3. aucun : un membre est créé (profil rattaché à l'email du payeur, comme les familles de
     Contretemps), invitation envoyée selon les réglages ;
  4. doute (même nom, email différent ; plusieurs candidats) : rien n'est fusionné automatiquement ;
     l'inscription va dans une file **« À rapprocher »** où un admin choisit « c'est cette personne » ou
     « nouvelle personne ».
- **Champs personnalisés (base « fixe » mais extensible)** (question de Seb) : un formulaire peut
  demander une information que la base ne connaît pas (taille de costume, allergie précise, moyen de
  transport). On ne modifie jamais les tables par organisation (`ALTER TABLE` en multi-organisation =
  migrations impossibles à suivre). À la place, le **core** fournit des champs personnalisés :
  - table `member_custom_fields` : organisation, clé, libellé, type (texte, nombre, date, oui/non, choix
    unique, choix multiple, fichier), options, obligatoire, visibilité (admin seulement, membre, public),
    créé par (formulaire ou admin) ;
  - valeurs dans une colonne `custom` **JSONB** de `members` (Postgres, index GIN), validées contre les
    définitions ; elles s'affichent dans la fiche membre, se filtrent dans les listes, s'exportent, et
    sont utilisables par le bloc Calcul et par les autres formulaires ;
  - l'IA, devant un champ sans équivalent, **propose** dans sa carte de question : « créer le champ
    personnalisé "Taille de costume" (choix : XS à XL) » ; c'est un humain qui confirme ;
  - un écran Admin > Membres > « Champs personnalisés » liste, renomme, archive (jamais de suppression
    silencieuse de données) ;
  - si un même champ personnalisé revient dans beaucoup d'organisations, il pourra devenir un vrai champ
    d'un module dans une version suivante d'AppBase (migration de la valeur JSON vers la colonne).
  - c'est bien un système **clé-valeur générique** (idée de Seb), mais en JSONB plutôt qu'en table
    « entité-attribut-valeur » (`member_id, key, value`) : une seule ligne par membre, types vérifiés,
    index et filtres simples, pas de jointure par champ. Le même mécanisme (`custom` + définitions) peut
    servir à d'autres tables du core et des modules (groupes, événements, inscriptions).
  - Les réponses brutes de chaque formulaire restent de toute façon gardées telles quelles (JSON) avec
    l'inscription, même pour les champs non reliés.
- **Réutilisation** : le même moteur de liaison sert à l'import Excel des membres (module
  `member_import`, 01 §3.2), où l'IA propose de la même façon la correspondance des colonnes et demande
  quand elle hésite.

#### Forme du document et diffusion (question de Seb du 14 octobre)

On ne choisit pas « la forme » d'un A-document à sa création : c'est toujours la même liste de blocs, et
**dans tous les cas les gens reçoivent une page sur laquelle ils cliquent** (remarque de Seb). Deux
choses varient, et elles sont indépendantes :

1. **Lire ou remplir** : déduit du contenu (voir ci-dessous), pas un réglage.
2. **Pour qui** : c'est le seul choix, dans un écran unique **« Diffuser »** (remplace « Partager »), avec
   un sélecteur à deux positions :

| Position | Qui reçoit la page | Ce que ça donne |
|---|---|---|
| **Des personnes choisies** | membres, groupes, rôles, adresses externes | un **lien personnel** par personne : on sait qui a lu ou répondu, réponses pré-remplies avec sa fiche, relances aux retardataires, date limite, droits de lecture ou de modification dans l'appli ; export PDF ou Word possible |
| **Tout le monde** | n'importe qui ayant l'adresse | une **adresse publique** `https://<préfixe>.<appli>.silvaplana.cloud/<page>` (§5.5), à mettre sur le site, une affiche (QR code), les réseaux ; les répondants s'identifient en remplissant (nom, email) ; réservé aux versions Validées ou Officielles |

Si le document contient des blocs à remplir, les deux positions alimentent **le même tableau de réponses**
(§5.10) : une inscription peut être envoyée aux anciens adhérents par lien personnel **et** publiée pour
les nouveaux, toutes les réponses arrivent au même endroit, avec une colonne « Provenance ».

Exemples : sondage du bureau → personnes choisies ; inscriptions de la saison → les deux ; règlement
intérieur → personnes choisies (lecture) ; page du spectacle → tout le monde.

Seb résume la distinction ainsi : un A-document est soit **à lire** (navigable : liens, sommaire, vidéos,
fichiers joints), soit **à remplir** (interactif : il contient au moins un bloc à remplir). Ce n'est pas un
réglage : c'est déduit du contenu, et la tuile d'un A-document à remplir porte une petite pastille
« à remplir » (avec le compteur de réponses quand une collecte est ouverte).


Un fichier Word ou Excel **téléversé** reste un fichier (`core.file`) : il se partage et se lit, mais
ne se remplit pas et ne se publie pas. Pour le rendre interactif, action « Convertir en A-document » :
markitdown en extrait le contenu, l'IA le transforme en blocs (les champs à compléter deviennent un bloc
Formulaire), et l'original reste en document lié.

### 5.10 Collecte de réponses : bloc, type ou autre chose ? (question de Seb du 14 octobre)

Procuration, sondage, inscription, autorisation parentale, vote ont un point commun : on **envoie un
lien**, chacun **remplit**, et on obtient **un tableau commun des résultats**. Ce n'est ni un bloc ni un
type : c'est une **capacité du socle A-document**, la **collecte**.

- **Le bloc** est ce qui se **voit** dans le document : la question, la case à cocher, le cadre de
  signature, le bouton de paiement. Il dit *quoi* remplir.
- **La collecte** dit *qui* remplit, *jusqu'à quand*, et *où vont les réponses*. Elle s'active d'elle-même
  dès qu'un A-document contient au moins un bloc à remplir (Formulaire, Sondage, Signature, Vote,
  Paiement, Dépôt de fichier, Créneaux).
- **Le type** reste le métier : un « Sondage » ou une « Procuration » packagés ne sont qu'un A-modèle tout
  prêt (texte + bloc + réglages de collecte par défaut), sans code de collecte à eux.

La collecte, commune à tous, ajoute à l'A-document :

| Élément | Contenu |
|---|---|
| **Diffusion** | destinataires : membres, groupes (un cours, le bureau), rôles, ou adresses externes ; **lien personnel** par destinataire (pas de connexion nécessaire, la personne est reconnue par le lien) ou lien public anonyme ; envoi par email et notification ; date limite ; **relances** automatiques aux non-répondants (J-7, J-2, réglables) |
| **Réponses** | onglet « Réponses » : **tableau commun**, une ligne par personne, une colonne par champ des blocs (signé le…, montant payé, choix du vote, fichier déposé) ; statut *répondu / en cours / pas répondu* ; filtres ; compteurs en tête (« 48 / 63 ont répondu, 2 340 € encaissés ») ; export .xlsx |
| **Règles** | une réponse par personne ou plusieurs ; réponse modifiable jusqu'à la date limite ou non |
| **Visibilité des réponses** (Seb) | réglage à trois positions, choisi à l'envoi et affiché aux répondants avant qu'ils répondent : **Privée** (seuls l'envoyeur et les gestionnaires du document voient qui a répondu et quoi) ; **Résultats visibles** (les répondants voient les totaux, sans les noms) ; **Publique** (tous les destinataires voient qui a répondu et ses réponses, façon Doodle, utile pour choisir une date ou des créneaux de bénévoles). Le vote à bulletin secret force un mode à part : on voit qui a voté, jamais quoi, même pour l'envoyeur |
| **Suite** | à la clôture, le tableau est figé avec la version ; il peut servir de document lié (§5.4) : le PV d'AG lit les résultats des votes, le bloc Calcul fait les totaux |

Stockage : table `doc_collections` (réglages par A-document) et `doc_responses` (une ligne par
destinataire : personne ou email, jeton du lien, statut, dates, valeurs des blocs en JSON) ; chaque bloc
interactif écrit sa partie de la réponse, son module garde ses données propres (paiement HelloAsso,
preuve de signature) et la référence dans la ligne de réponse.

Côté IHM, une ligne discrète sous l'aperçu (« Collecte : 48 / 63 réponses · clôture le 20 nov. ») ouvre
l'onglet Réponses ; la diffusion se règle dans l'écran Partager (§4.4 bis), section « Faire remplir ».

## 6. IHM

### 6.0 Mêmes fonctions sur téléphone et sur ordinateur (décision de Seb du 14 octobre)

Un **seul composant explorateur**, le même code, qui fait **exactement les mêmes choses** sur les deux.
Seule la disposition s'adapte à la largeur. Inspiration : l'explorateur de fichiers de Windows.

| Fonction | Ordinateur | Téléphone |
|---|---|---|
| Glisser-déposer pour déplacer (vers un dossier, le fil d'Ariane, l'arbre) | souris | **appui long puis glisser** (dnd-kit, capteur tactile) ; le dossier survolé s'ouvre après 0,8 s, comme sous Windows |
| Sélection multiple | Ctrl / Maj + clic, rectangle de sélection | « Sélectionner » dans le menu de l'appui long, puis toucher les autres |
| Menu des actions (clic droit) | clic droit | **appui long = clic droit** (idée de Seb) : appui long sans bouger ouvre le même menu ; appui long puis glisser déplace ; bouton ⋯ en plus |
| Couper, copier, coller | Ctrl+X, C, V | barre d'actions de la sélection |
| Renommer | F2 ou clic lent | action Renommer |
| Vues liste, détails, grandes icônes | bouton de vue | même bouton (détails = deux lignes) |
| Arbre des dossiers | colonne à gauche | tiroir qui glisse depuis la gauche (bouton arbre dans l'en-tête) |
| Aperçu | panneau à droite | plein écran, balayage pour passer au suivant |
| Ajouter des fichiers | glisser depuis le bureau du système | bouton + (fichiers, appareil photo), partage depuis une autre appli |
| Annuler | Ctrl+Z | bandeau « Déplacé dans AG 2026 · Annuler » après chaque action |

Sur téléphone, « Déplacer… » reste aussi dans le menu, parce que glisser loin sur un petit écran est
moins précis.

Conséquence technique : **SVAR File Manager n'est pas retenu**. Il ne fonctionne qu'à la souris, et
il faudrait de toute façon écrire l'explorateur mobile à côté. On écrit un seul explorateur maison avec
`@headless-tree/react` (arbre), `@dnd-kit/core` (glisser-déposer souris et tactile) et le kit UI du core.

### 6.0 bis Gros et simple (exigence de Seb du 15 octobre)

Le public : des bénévoles d'association, souvent peu à l'aise avec l'informatique. Règles chiffrées,
vérifiées en revue :

- **Texte** : 17 px minimum pour les noms, 14 px pour les sous-lignes, jamais en dessous ; respecte le
  réglage de taille de texte du téléphone.
- **Cibles tactiles** : 48 × 48 px minimum ; lignes de liste de 76 px ; lignes de menu de 56 px ; tuiles de
  type 52 px.
- **Menu d'actions court** : 6 actions maximum, toujours dans le même ordre (Ouvrir, Partager, Renommer,
  Déplacer, Propriétés, Supprimer) ; le reste (Télécharger, Copier, Épingler) dans « Plus… ».
- **Des mots, pas seulement des icônes** : chaque bouton porte son libellé ; pas de geste caché sans
  équivalent visible (le bouton ⋯ double toujours l'appui long ; une bulle d'aide l'explique à la première
  visite).
- **Boutons flottants toujours atteignables** (retour de Seb sur téléphone Android) : le + et la bulle sont
  placés au-dessus de la barre du bas **et** de la barre système (`bottom: calc(var(--bottom-nav-height) +
  16px + env(safe-area-inset-bottom))`, manifeste `viewport-fit=cover`) ; test obligatoire sur un Android
  avec les trois boutons de navigation et sur un iPhone.
- **Contraste** AA minimum (4,5:1), y compris en mode sombre.
- **Erreurs rattrapables** : Annuler pendant 10 s plutôt que des confirmations ; corbeille 30 jours.
- **Test** : sur 2 ou 3 vrais membres du club, sur leur propre téléphone, avant de valider l'étape 2.

### 6.1 Place dans la navigation (règle IHM)

- **Barre du bas** : fonction « Documents », icône `folders`.
- **Onglets du haut** : aucun par défaut. Si l'app veut un onglet « Activité » ou « Corbeille » pour
  les admins, il passe en onglet ; sinon ces écrans sont dans le menu ⋯.
- **Sélecteur dans l'écran (3 positions)** : `Public | Privé | Personnel` (§4.0). Les élèves (simples
  membres) n'ont pas d'espace Personnel (Seb, 15 octobre) : ils voient `Public | Privé` ; dans Privé, il ne voit que ce qui lui est partagé, et un message l'indique si rien
  ne l'est encore.
- **L'arborescence n'est pas un niveau de navigation** : c'est du contenu, parcouru par fil d'Ariane
  dans le même écran, comme un fil de messages. Elle ne compte donc pas dans les trois niveaux. À
  confirmer, voir §12.1.

### 6.2 Mobile (référence de conception, 360-430 px)

Écran d'accueil d'un espace :

```
┌──────────────────────────────┐
│ Documents             🔍  ⋯  │  en-tête du core
│ [ Public | Privé | Personnel ]│  sélecteur
│ Récents  ▸ ▸ ▸ ▸             │  cartes horizontales, 6 derniers ouverts/modifiés
│ ─────────────────────────── │
│ 📌 AG 2026          12 élém. │  dossiers épinglés en tête
│ 📁 Comptabilité      8 élém. │
│ 📁 Communication     23      │
│ 🟧 Présentation AG 2026  ✦   │  document vivant (tuile pleine, §7)
│ 🟥 Statuts.pdf       240 Ko  │
│ 🟦 Règlement.docx    hier    │
│                         (+)  │  bouton flottant
├──────────────────────────────┤
│  barre du bas du core        │
└──────────────────────────────┘
```

Détails :

- **Ligne d'élément** : tuile de type 52 px (§7), nom sur une ligne (ellipse au milieu pour garder
  l'extension : `Compte-rendu-CA-…-mars.pdf`), sous-ligne grise « taille · date relative · auteur ».
  Hauteur 76 px, zone de toucher pleine largeur (§6.0 bis).
- **Vue grille** (bascule dans ⋯, mémorisée par dossier en `localStorage`) : vignettes 2 colonnes pour
  les dossiers de photos.
- **Dans un dossier** : fil d'Ariane sous l'en-tête, défilant horizontalement, retour par balayage
  depuis le bord gauche et par le bouton retour Android (l'historique du navigateur suit chaque dossier).
- **Appui long** ou bouton ⋯ de la ligne : **feuille d'actions** en bas d'écran (Ouvrir, Partager,
  Renommer, Déplacer, **Propriétés**, Supprimer, et « Plus… » pour Télécharger, Copier, Épingler ; Propriétés aussi dans le ⋯ de l'en-tête d'un fichier ouvert). Appui long puis toucher d'autres lignes =
  sélection multiple, barre d'actions en bas.
- **Bouton +** : feuille « Créer » en deux sections. *Ajouter* : Dossier, Fichier, Photo ou scan (ouvre
  l'appareil photo, `accept="image/*" capture`). *Créer dans l'appli* : un bouton par type vivant
  autorisé, avec sa tuile (Présentation d'AG, Bilan…).
- **Envoi** : bandeau de progression collant en bas, au-dessus de la barre ; l'envoi continue en
  changeant d'écran (comme les vidéos aujourd'hui). Partage depuis une autre appli Android vers
  AppBase via `share_target` du manifeste PWA (phase 2).
- **Déplacer** : feuille plein écran qui navigue dans les dossiers, bouton « Déplacer ici ».
- **Ouvrir** : image → visionneuse plein écran ; PDF → lecteur pdf.js ; Office → aperçu PDF converti
  si disponible, sinon téléchargement et ouverture dans l'appli du téléphone ; vidéo → lecteur natif
  avec vignette ; document vivant → écran du module propriétaire.
- **États vides illustrés** : un dossier vide montre une illustration légère et deux boutons
  (« Ajouter un fichier », « Créer un dossier »), jamais juste « Aucun élément ».
- **Recherche** : plein écran, résultats instantanés à partir de 2 caractères, filtres en pastilles
  (Type, Espace, Modifié), résultats avec leur chemin en sous-ligne.

### 6.3 Ordinateur (≥ 1024 px)

Trois colonnes : **arbre** à gauche (260 px, headless-tree, espaces en racines, glisser-déposer pour
déplacer), **liste** au centre (colonnes Nom, Modifié, Taille, Par ; tri au clic ; sélection Maj/Ctrl ;
raccourcis Suppr, F2, Entrée), **aperçu** à droite repliable (vignette ou rendu, infos, versions,
activité, droits). Déposer des fichiers depuis le bureau du système n'importe où sur la liste
téléverse dans le dossier affiché, avec surbrillance de la zone. Menu contextuel au clic droit avec les
mêmes actions que la feuille mobile.

Entre 600 et 1024 px : liste + aperçu en tiroir, arbre en tiroir comme sur téléphone.

### 6.3 bis Gestes et écran Propriétés (question de Seb du 15 octobre)

| Geste | Ordinateur | Téléphone |
|---|---|---|
| Sélectionner | clic simple (l'élément s'affiche dans le panneau de droite) | appui long → « Sélectionner » |
| Ouvrir | double clic ou Entrée | toucher |
| Menu des actions | clic droit | appui long sans bouger, ou bouton ⋯ |
| Déplacer | glisser | appui long puis glisser, ou menu → Déplacer… |
| Propriétés | panneau de droite, ou clic droit → Propriétés (Alt+Entrée) | menu → Propriétés (plein écran) |
| Copier / Coller | Ctrl+C puis Ctrl+V dans un autre dossier, ou clic droit → Copier, puis Coller | menu → Copier, puis bandeau « Coller ici » en bas du dossier où l'on va |
| Importer | glisser un PDF, un Word, une photo… depuis l'explorateur du PC : sur un dossier, il va dedans ; ailleurs, dans le dossier ouvert ; Ctrl+V colle une capture d'écran | + → Importer un fichier ou une photo |

Copier / Coller (Seb, 15 octobre) : copie le dossier ou le fichier avec tout son contenu ; la copie prend les
droits de son nouveau dossier, un élément Validé ou Officiel y redevient Brouillon ; collé au même endroit
il devient « Nom (2) ». Le presse-papier est celui de l'appli (on colle dans l'appli) : un navigateur ne
laisse pas déposer un fichier dans le presse-papier du PC ; pour sortir un fichier, c'est Télécharger.

**Propriétés** : un seul écran pour fichier et dossier, avec un sélecteur 3 positions
`Infos | Accès | Historique` :

- **Infos** : nom, emplacement (cliquable), statut (Brouillon / Validé / Officiel / Archivé) avec le
  bouton pour le changer si on en a le droit, taille, créé et modifié par qui et quand ;
- **Accès** : qui a accès et à quel niveau, les accès **hérités** grisés avec leur dossier d'origine, et
  une ligne « Vous : Écriture » qui dit ce que l'utilisateur peut faire lui-même. Le bouton « Partager »
  ouvre l'écran du §4.4 bis (seulement avec `manage`) ;
- **Historique** : versions et activité dans une seule liste chronologique, avec « Revenir à cette
  version ».

Les actions impossibles restent visibles mais grisées, avec la raison au toucher (« Le dossier AG 2026 est
en lecture seule pour vous », « Document officiel : créez une nouvelle version »).

### 6.4 Écrans d'administration

Contribution au slot `admin.tabs` : onglet « Documents » avec sélecteur `Stockage | Corbeille | Activité` :
espace utilisé par module (vidéos, documents) et quota, éléments supprimés restaurables, journal filtrable.

## 7. Icônes de types

Un seul composant `<FileTypeTile type={...} size={40} />` dans `@appbase/core/ui`, piloté par un registre.

### 7.1 Dossiers et fichiers : deux familles bien distinctes (demande de Seb du 15 octobre)

Une maquette les montre : https://claude.ai/artifact/UB76UY2UCdPg2HYRLk19oB.

- **Dossiers : un seul type, une seule apparence.** Vrai dessin de dossier jaune (pas de tuile), nom en
  gras, sous-ligne « 12 éléments », chevron › à droite qui dit « on entre dedans ». Toujours **en tête de
  liste, regroupés** sous l'intitulé « Dossiers » dans un bloc au fond jaune pâle. Pas de couleur au choix
  (une seule apparence, c'est plus simple) ; un dossier épinglé porte une punaise.
- **Fichiers : plusieurs types**, sous l'intitulé « Fichiers ». Forme de **feuille au coin corné**, avec
  en bas une étiquette de la couleur du type (`PDF` rouge, `W` bleu, `✦` orange pour les fichiers de
  l'appli…), bouton ⋯ à droite au lieu du chevron, et le **statut** (Validé, Brouillon, Officiel) en
  pastille devant la sous-ligne. Les types de fichiers sont à définir avec Seb (§7.2 et §7.3).

Dossier = on entre dedans ; fichier = on l'ouvre. Ni la forme, ni la couleur, ni le chevron ne se
ressemblent.

### 7.1 bis Trois familles de fichiers de l'appli (décision de Seb du 15 octobre)

À côté des **fichiers importés** (PDF, Word, Excel, photos, vidéos : chacun son type), les fichiers propres
à l'appli se rangent selon **ce qu'ils font dans la vie de l'asso** :

| Famille | Ce qui se passe | Exemples | Écrans en plus |
|---|---|---|---|
| **Informer** | on le lit, personne ne répond | page de cours, règlement, compte rendu, bilan financier, présentation d'AG | aucun (les chiffres d'un bilan viennent de la base ; Officiel le fige) |
| **Questionner** | chacun répond, les réponses restent **dans le fichier** | sondage, convocation AG (présent / procuration / absent), vote, appel à bénévoles, choix de créneaux | Réponses, liens personnels, relances, « 12/30 réponses » |
| **Agir** | on répond **et ça crée quelque chose dans l'appli** : membre, inscription, paiement | inscription aux cours, adhésion, cotisation, billetterie | inscrits, paiements, rapprochement avec les membres (§5.9) ; relecture humaine obligatoire si argent |

- Verbes affichés : **Informer, Questionner, Agir** (décidé par Seb le 15 octobre). Icône : la feuille du §7.1 avec une étiquette de couleur en **rond cerclé** : **ⓘ**
  (sarcelle, le symbole universel « information », idée de Seb), **?** (violet) ou **éclair ⚡** (orange, idée de Seb : « il se passe quelque chose ») ; « ? »
  plutôt que « q », reconnu par tout le monde. L'action Propriétés n'utilise donc pas ⓘ (icône liste ☰). Question et Action
  ajoutent le compteur dans la sous-ligne (« 12/30 réponses », « 48 inscrits »).
- « + Nouveau » montre les trois familles, chacune avec ses **modèles** (Convocation AG, Sondage,
  Inscription, Bilan financier, Présentation d'AG, Page de cours…) ; on en ajoute sans coder (§5.6).
- La famille découle des blocs : un bloc qui pose une question fait passer en Question ; un bloc qui écrit
  dans l'appli (inscription, paiement, adhésion) fait passer en Action. Elle est calculée, pas choisie.
- Page, diaporama ou tableau n'est que la **forme de sortie** (PDF A4, .pptx, .xlsx), indépendante de la
  famille.

### 7.1 ter Badges de statut, assistants et bouton Nouveau (demandes de Seb du 15 octobre)

**Dans les listes, le symbole seul** (Seb, 15 octobre) : crayon, coche, sceau, sans le mot « Brouillon », « Validé », « Officiel » ; le mot apparaît en bulle au survol ou à l'appui long, et en entier dans Propriétés.

**Badge de statut** dans la sous-ligne, sur les fichiers **et sur les dossiers** :

| Statut | Badge |
|---|---|
| Brouillon | crayon, contour en pointillés gris |
| Validé | coche, vert |
| Officiel | sceau (rosette avec coche), bleu plein |

Un dossier peut porter un statut : **Officiel** sur un dossier fige tout ce qu'il contient (par exemple
« AG 2025 » une fois l'AG passée) ; sans statut, pas de badge. Archivé : pas de badge, le dossier ou le
fichier est grisé.

**Filtres de statut** en haut de la liste, sous le fil d'Ariane : pastilles `Tout | ✎ Brouillon | ✓ Validé |
Officiel`, une seule active à la fois, appliquées au dossier affiché (dossiers et fichiers) ; message clair
si rien ne correspond. Le même filtre existe dans la recherche, sur tout l'espace.
**Filtres de famille** (Seb, 15 octobre), **indépendants** du statut et cumulables avec lui : ⓘ ? ⚡.
**Forme retenue (Seb, 15 octobre)** : une seule rangée de **boutons-icônes sans texte** `✎ ✓ sceau | ⓘ ? ⚡`,
sans bouton « Tout » : on touche pour filtrer, on retouche pour enlever ; rien de sélectionné = tout. Une
seule valeur par groupe (statut, famille). Le nom en français (« Brouillon », « Informer »…) s'affiche en
bulle au survol sur ordinateur et à l'appui long sur téléphone.

**Écran principal** : deux boutons flottants au-dessus de la barre du bas :

- **gros bouton + orange** en bas à droite (66 px, même style que le `.fab` de Contretemps, couleur
  `--accent` de l'appli) : ouvre « Que voulez-vous faire ? » avec trois sections
  dépliables **Informer / Questionner / Agir**, chacune avec ses modèles en tuiles, puis « Ou simplement » :
  **Créer un dossier** et **Créer un fichier** (fichier vierge : sa famille se déduit ensuite de ce qu'on y
  met, rien à choisir à la création), et un lien « Importer un fichier ou une photo ». Tuiles = modèles, libellées par un **verbe** (ce qu'on veut faire) :
  - *Informer* (Seb, 15 octobre) : **Préparer le PowerPoint d'AG**, **Préparer le bilan financier d'AG**,
    **Faire un cours**, **Faire un dossier de subvention**, **Faire un prévisionnel financier**, **Faire un plan marketing**, **Faire une étude marketing**, **Faire une publi de blog**, **Faire une publi de photos** (Seb, 15 octobre), **Faire le site web public de l'asso** (A-site du §5.7, un seul par organisation, à la racine
    `https://<préfixe>.<appli>.silvaplana.cloud/`), **Faire une publication web** (une page publiée, autant qu'on
    veut : un spectacle, un stage, un événement ; §5.5, adresse `https://<préfixe>.<appli>.silvaplana.cloud/<nom>`) ;
  - *Questionner* (Seb) : **Convoquer l'AG**, **Faire un sondage** (liste en cours) ;
  - *Agir* (Seb) : **Ouvrir les inscriptions annuelles**, **Ouvrir les inscriptions au spectacle**, **Faire une note de frais** (Seb, 15 octobre : crée une dépense à rembourser dans les finances) (libellés
    mis au verbe par Claude, à confirmer) ;
  - **d'où viennent les tuiles** (Seb, 15 octobre) : les modèles sont **livrés avec l'appli** pour toutes les
    écoles, et **chaque asso peut les modifier** ou en ajouter (un modèle modifié devient le sien ; le
    modèle livré d'origine reste disponible) ;
- **bulle d'assistant**, plus petite, empilée juste au-dessus du + (comme `.fab--secondary`) : l'**assistant général** de l'asso. Dans un fichier ouvert, la même
  bulle ouvre **l'assistant de ce fichier**, un agent distinct ; l'assistant général peut lui confier une
  tâche (carte « j'ai demandé à l'assistant de ce fichier »). Voir l'étape 5 bis du plan Contretemps.

### 7.2 Registre des fichiers (core)

Détection : type MIME réel côté serveur, extension en secours côté client.

| Famille | Extensions | Teinte | Pictogramme Tabler |
|---|---|---|---|
| PDF | pdf | rouge | `file-type-pdf` |
| Texte | doc, docx, odt, rtf | bleu | `file-text` |
| Tableur | xls, xlsx, ods, csv | vert | `table` |
| Présentation | ppt, pptx, odp, key | orange | `presentation` |
| Image | jpg, jpeg, png, webp, heic, gif, svg | violet | `photo` (ou vignette réelle) |
| Vidéo | mp4, mov, webm | rose | `movie` (ou vignette) |
| Audio | mp3, m4a, wav, ogg | cyan | `music` |
| Archive | zip, rar, 7z | ambre | `file-zip` |
| Code, données | json, xml, md, txt | ardoise | `file-code` |
| Autre | * | gris | `file` |

Quand une vignette existe (image, vidéo, PDF), elle remplace le pictogramme en vue grille ; en vue liste
la tuile reste, avec une mini-vignette carrée pour les images.

### 7.3 Types maison

Le module déclare `icon`, `color`, `badge` (§5.3) ; il ne fournit jamais d'image libre. Les teintes sont
celles de la charte de l'organisation (12 teintes nommées, contrastes vérifiés en clair et en sombre),
ce qui garantit une grille cohérente quel que soit le nombre de modules.

## 8. API REST (préfixe `/api/documents`)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/spaces` | espaces accessibles et compteurs |
| GET | `/nodes?parent_id=&space=` | contenu d'un dossier (tri, pagination par curseur, 200 par page) |
| GET | `/nodes/{id}` | détail, chemin (fil d'Ariane), niveau de droit effectif |
| POST | `/folders` | créer un dossier |
| POST | `/uploads` → `PUT /uploads/{id}?offset=` → `POST /uploads/{id}/finish` | envoi par blocs (façade core), `finish` crée le nœud ou la version |
| POST | `/living` | créer un document vivant (`type_key`, `name`, `parent_id`) : appelle `DocumentType.create` |
| PATCH | `/nodes/{id}` | renommer, couleur, épingler |
| POST | `/nodes/move` | déplacer une sélection (`ids`, `target_id`), refuse un cycle |
| POST | `/nodes/copy` | copier (fichiers : nouvelle version liée au même contenu ; vivants : `duplicate`) |
| DELETE | `/nodes/{id}` | corbeille ; `?permanent=true` pour `manage` |
| POST | `/nodes/{id}/restore` | restaurer depuis la corbeille |
| GET | `/nodes/{id}/download?version=` | fichier, `Content-Disposition` avec le nom d'origine, prise en charge de Range |
| GET | `/nodes/{id}/thumbnail` | WebP, cache navigateur long avec empreinte dans l'URL |
| GET | `/nodes/{id}/preview` | PDF de prévisualisation (Office) |
| GET | `/nodes/{id}/versions` · POST `/nodes/{id}/versions/{n}/restore` | versions |
| POST | `/nodes/{id}/freeze` | figer un document vivant en fichier |
| POST | `/nodes/{id}/actions/{key}` | action déclarée par le type du nœud (§5.1) |
| GET/PUT | `/nodes/{id}/acl` | droits |
| GET | `/search?q=&type=&space=&modified_after=` | recherche (pg_trgm + unaccent sur le nom, plus `search_text` des vivants) |
| GET | `/recent` | 20 derniers éléments ouverts ou modifiés par le membre |
| GET | `/trash` | corbeille |

Temps réel : canal `documents.folder.{id}` ; un ajout ou un renommage par un autre membre apparaît sans
recharger.

Sécurité :

- tout téléchargement passe par la route, qui vérifie le droit ; aucune URL statique (corrige la faiblesse
  des vidéos) ;
- réponses de fichiers avec `X-Content-Type-Options: nosniff` ; HTML, SVG et XML servis en
  `attachment`, jamais en ligne (pas de XSS par fichier déposé) ;
- taille max par fichier réglable par organisation (défaut 200 Mo), quota par organisation (défaut 5 Go) ;
- noms de fichiers nettoyés (pas de `/`, `\`, caractères de contrôle, 255 octets max) ; le nom n'est
  jamais utilisé comme chemin disque (stockage par empreinte).

## 9. Performance

- Listes virtualisées au-delà de 100 éléments (`@tanstack/react-virtual`, à ajouter).
- Vignettes générées en tâche de fond après l'envoi, servies en WebP 480 px, `loading="lazy"`.
- Le contenu d'un dossier est mis en cache côté client et rafraîchi en arrière-plan à l'ouverture.
- `react-pdf`, la visionneuse et l'arbre sont chargés à la demande (`lazy`), pas dans le paquet initial.

## 10. Sauvegarde

`backup_tables = ["doc_nodes", "doc_versions", "doc_acl", "doc_share_links", "doc_activity"]`. Le core
exporte les `stored_files` référencés avec l'organisation (01 §3.1). Les documents vivants sont
sauvegardés par leur propre module.

## 11. Découpage en PR

1. **Core `storage`** : `stored_files`, envoi par blocs repris de `videos/`, téléchargement contrôlé,
   vignettes images et PDF, obstore en `LocalStore`. Les vidéos migrent dessus, l'ancien montage statique
   disparaît. *Acceptation* : une URL de vidéo copiée ne fonctionne plus sans session.
2. **`FileTypeTile` et registre** dans le kit UI du core, avec une page de démonstration de toutes les
   tuiles en clair et en sombre.
3. **Module documents, lecture et rangement** : tables, droits, API, écrans mobile (liste, dossiers,
   feuilles d'actions, envoi, visionneuses). *Acceptation* : tests de droits (§1), parcours Playwright
   mobile « créer un dossier, envoyer une photo, la déplacer, la supprimer, la restaurer ».
4. **Ordinateur** : arbre, trois colonnes, glisser-déposer, raccourcis.
5. **Types vivants** : `document_types`, slot `documents.types`, type factice `demo.note` en test ; puis
   la procuration du prototype Contretemps comme premier vrai type.
6. **Versions, recherche, corbeille, activité, admin Stockage.**
6 bis. **Socle A-document** (§5.4), puis **Document libre et A-modèles** (§5.6) : états, bibliothèque de prompts, génération par IA en sortie
   structurée, choix du modèle, versions IA et modifiées, aperçus par type.
7. **Partage** : écran Partager (§4.4 bis), liens externes, envoi par email avec pièce jointe (dépend de la spec email).
8. Phase 2 : aperçus Office, partage depuis Android (`share_target`).

## 12. Décisions à trancher par Seb

1. **L'arborescence compte-t-elle comme un niveau de navigation ?**
   Recommandation : **non**. Les dossiers sont du contenu, comme les messages d'une conversation, et se
   parcourent par fil d'Ariane dans le même écran. Sinon le module ne pourrait pas avoir de sélecteur
   d'espaces, ni de sous-dossiers.

2. **Trois espaces fixes ou un seul arbre avec des droits par dossier ?**
   **Décidé par Seb le 15 octobre : trois espaces `Public | Privé | Personnel`**, définis au §4.0 (Public
   visible du web, Privé pour certains membres, Personnel pour soi seul).

3. **Disque local ou stockage S3 dès le départ ?**
   Recommandation : **disque local** derrière obstore. Zéro coût et zéro compte de plus aujourd'hui ;
   passage à un S3 européen (Scaleway, OVH) par variable d'environnement le jour où un deuxième serveur ou
   le volume le demande.

4. **Aperçus Word, Excel, PowerPoint dans l'appli ?**
   Recommandation : **pas en première version** ; on télécharge et le téléphone ouvre l'appli adaptée.
   En phase 2, conversion PDF par LibreOffice dans le worker (environ 500 Mo de plus dans l'image).

5. **Édition en ligne des fichiers Office (type Google Docs) ?**
   Recommandation : **non**. C'est un autre produit (Collabora ou OnlyOffice, serveur dédié). Les besoins
   d'édition dans l'appli passent par des documents vivants, plus simples et mieux adaptés au mobile.

6. **Liens de partage publics vers l'extérieur ?**
   Recommandation : **oui, avec l'envoi par email (§4.4 bis)**, avec expiration obligatoire : c'est le cas réel de la convocation
   d'AG envoyée aux non-membres.

7. **Comment nommer les objets applicatifs ?**
   Recommandation : dans le code, un nom générique en anglais (`node type`, `DocumentType`), parce
   qu'AppBase sert aussi hors des associations. À l'écran, le nom vient des libellés de l'app
   (`labels({"living": "A-document"})`, 01 §6.4) ; l'app association peut donc dire « A-document ». Mais
   l'utilisateur n'a pas besoin d'un mot pour s'en servir : la tuile pleine avec l'étincelle suffit à les
   reconnaître, et le menu + les range sous « Créer dans l'appli ». Je garderais le mot pour la doc et
   le marketing, pas dans les écrans.

8. **Où vit le contenu d'un A-document ?**
   Recommandation : **dans les versions, gérées par le module documents** (`content_json`, §5.4). Les
   versions IA/modifiées, la comparaison et la génération deviennent communes à tous les types ; un
   module ne garde ses propres tables que pour les données vivantes hors document (les inscrits).

9. **Qui peut passer un A-document en Officiel ?**
   Recommandation : le niveau `manage` sur le dossier (par défaut les admins et le bureau), et
   l'officialisation est **définitive** : pour changer un document officiel, on crée un nouveau brouillon.

10. **Pages publiées : rendu par gabarit ou HTML libre généré par l'IA ?**
    Recommandation : **gabarit du module** rempli par le contenu structuré que l'IA produit (§5.5).
    C'est aussi beau, toujours à la charte, et cela empêche qu'une page publiée sous `*.silvaplana.cloud`
    contienne du code dangereux.

11. **Catalogue d'A-modèles partagé entre associations ?**
    Recommandation : **oui, en phase 2**, avec validation par nous avant publication et sans aucune
    donnée de l'association d'origine. C'est un bon moteur d'adoption : une asso qui arrive trouve déjà
    des modèles faits par d'autres.

12. **Nom de domaine propre pour l'A-site web ?**
    Recommandation : **`<préfixe>.<appli>.silvaplana.cloud` en premier** (déjà en place dans Contretemps), domaine propre en phase 2 (Caddy sait
    émettre les certificats à la volée). Beaucoup d'associations ont déjà un nom de domaine et voudront
    le garder.

13. **Signature électronique : maison ou prestataire ?**
    Recommandation : **maison (signature simple)** pour les procurations, autorisations et droit à
    l'image, qui sont l'essentiel des besoins d'une association ; un prestataire (Yousign, eIDAS
    avancée) seulement plus tard, pour les contrats à fort enjeu.

14. **Les saisons passées sont-elles en lecture seule pour tout le monde, y compris les admins ?**
    Recommandation : **oui**, seul le superuser peut rouvrir une saison, avec un motif tracé. C'est ce
    qui donne sa valeur d'archive au passé (PV, bilans, votes) ; « Reprendre pour cette saison » couvre
    le besoin courant de repartir d'un document ancien.

15. **Une inscription crée-t-elle les membres automatiquement ?**
    Recommandation : **oui quand c'est certain** (personne inconnue, ou correspondance exacte), **file
    « À rapprocher »** dès qu'il y a un doute. Un doublon de membre est pénible à défaire (messagerie,
    présences, paiements rattachés) ; une fusion erronée est pire.

16. **Champs personnalisés des membres dans le core (JSONB) ?**
    Recommandation : **oui**, à ajouter à la spec du core (02). C'est ce qui permet à chaque association
    d'avoir ses propres informations sans toucher au schéma, et à l'IA de fabriquer des formulaires
    libres sans casser la base. Nécessite Postgres (décision 2 de la spec 01).


17. **Créer et modifier des fichiers Excel dans l'appli ? (question de Seb du 14 octobre)**
    Vérifié le 14 octobre. *Voir* : déjà prévu (`exceljs` 4.4, MIT). *Créer* : côté serveur avec
    `openpyxl` (MIT, 3.1.5, juin 2024) ; l'IA choisit les colonnes, les formules et la mise en forme,
    les données viennent de la base (export des membres, des comptes, des présences). *Modifier dans
    l'appli* : deux candidats. **Univer** (`@univerjs/presets` 1.0.4, Apache-2.0, octobre 2026, très
    actif, interface proche d'Excel) mais l'import/export .xlsx est dans la version Pro payante
    (`@univerjs-pro/exchange-client`, sans licence libre) : il faudrait écrire notre conversion
    .xlsx ↔ Univer avec exceljs. **Fortune-sheet** (`@fortune-sheet/react` 1.0.4, MIT, dernière version
    novembre 2025) avec `@corbe30/fortune-excel` (MIT, 2.3.4, septembre 2026) pour l'import/export,
    prêt à l'emploi mais moins actif. Dans les deux cas, un aller-retour perd ce qu'Excel seul sait faire
    (macros, tableaux croisés, graphiques complexes).
    Recommandation : **voir et créer tout de suite ; modifier dans l'appli pour les retouches simples
    (cellules, formules, mise en forme), après un essai des deux sur téléphone**, et garder « Ouvrir
    dans Excel » pour le reste. La modification en ligne est utile mais secondaire face au reste.