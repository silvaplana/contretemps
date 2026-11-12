# AppBase — Module `news` (Blog ; d'abord « Actualités »)

> **12 novembre 2026 : le module devient « Blog » (§12).** Une organisation a un ou plusieurs blogs ;
> « Actus » est un blog, « Techniques » un autre. Le §12 fait foi là où il contredit les §2 à §10
> (onglets Édition | Visualisation retirés, réglages par blog, catégories). Tant que les étapes du
> §12.9 ne sont pas codées, l'appli en ligne suit les §2 à §10.

Version 0.1, 6 novembre 2026. Statut : **spec à valider** (fil « Module : Actualités »). Écrans
validés par Seb sur maquette le 6 novembre : [`spec/maquettes/actualites.html`](../maquettes/actualites.html)
(tout est cliquable). Les écrans suivent la maquette exactement.

Code : `backend/src/publications/` (ex-`news/`, renommé le 12 novembre, §12) (déjà créé par le core avec le droit « Publier les actualités », PR #147)
et `frontend/src/modules/publications/`. Module générique : rien de propre à Contretemps.

---

## 1. Objectif

Une page d'actualités commune à toute l'organisation, pour passer des messages, certains importants,
avec photos et vidéos. Elle se voit : elle doit être agréable à regarder (Seb, 6 novembre).

- Tout le monde la lit. Seules les personnes qui ont le droit **🔒 Publier les actualités**
  (`news.publish`, spec/core.md §5.3, même niveau qu'« Accès au Financier ») écrivent.
- Une option permet d'ouvrir l'appli sur les actus.
- Pas de titre, pas d'encadré inutile : un texte, et au besoin une photo, une vidéo ou un document.

## 2. Place dans l'appli

Barre du bas › **Actus**, juste après Admin (premier onglet pour qui n'a pas Admin). Icône : un
journal. Visible par tous les rôles (Membre, Admin, Admin principal, Super User).

| Qui | Ce qu'il voit en touchant Actus |
|---|---|
| A le droit 🔒 Publier les actualités *(remplacé par le §12.5)* | Deux onglets en haut : **Édition** \| **Visualisation** (d'abord nommés Atelier et Aperçu sur la maquette ; renommés par Seb le 8 novembre) |
| Tous les autres | Directement les actus (l'écran Visualisation, sans onglets) |

Le Super User passe toujours ; l'Administrateur principal se coche lui-même s'il veut publier
(spec/core.md §5.3).

### 2 bis. Visibles par tout le monde (fin du test, Seb, 10 novembre 2026)

Le test est fini : le droit 🔒 « Voir les actualités » (`news.read`) et la liste « Qui voit les actus
(pendant le test) » sont retirés, avec leurs groupes 🔒 (migration `b6e2d9f4a1c7`). À la place, un
interrupteur dans les Paramètres d'édition des actus (§4.1), sous-partie « Visibilité » :
**« Les actus sont visibles par tout le monde »**, allumé par défaut. Éteint, seuls ceux qui ont
🔒 Publier les actualités voient l'onglet Actus ; les autres ne le voient pas, l'appli ne s'ouvre pas
sur les actus pour eux, et ils ne reçoivent pas les notifications. Qui publie peut le changer.

## 3. Les actus (Visualisation)

Ce que voient tous les membres ; l'onglet Visualisation des personnes qui publient montre exactement le même
écran.

### 3.1 Trois niveaux

| Niveau | Rendu | Usage |
|---|---|---|
| **Important** | Tout en haut, fond rouge clair, mention « ⚠ IMPORTANT », texte plus gros | Ce qui ne doit pas être manqué |
| **Normal** | Grande carte, le texte puis la photo ou la vidéo dessous (Seb et les testeurs, 8 novembre) ; l'inverse si le réglage « En haut de chaque actu » est sur Photo, vidéo (§4.1) | Le cas courant |
| **Brève** | Une ligne précédée d'une pastille, sans image | Les petites infos |

Une actu Important a une date **« En haut jusqu'au »** : jusqu'à ce jour inclus elle reste en haut en
rouge ; ensuite elle redescend à sa place parmi les autres, rendue comme une actu Normal.

### 3.2 Ordre

1. Les actus Important encore « en haut », de la plus récente à la plus ancienne.
2. Toutes les autres, de la plus récente à la plus ancienne (date de publication), groupées sous
   « Aujourd'hui », « Cette semaine », « Plus tôt ».
3. En bas : « C'est tout pour le moment. » Liste vide : « Pas encore d'actu. »

Pas de pagination au début : toutes les actus publiées, en faisant défiler.

### 3.3 Une actu

- Le texte (retours à la ligne gardés, liens cliquables).
- Jusqu'à **10 photos et vidéos**, mêlées, dans l'ordre choisi. À partir de deux, un **carrousel**
  comme sur Instagram : on fait glisser du doigt, des points disent où l'on est (Seb,
  8 novembre). Les points sont posés sur le bas de la photo ou de la vidéo et restent collés en bas de
  l'écran tant qu'on voit le carrousel : toujours visibles, même avec une photo haute (Seb, 9 novembre). Plus, au besoin, **un document** de
  Docs, montré comme un bouton fichier qui l'ouvre comme dans Docs (PDF dans la visionneuse, Word/Excel
  dans OnlyOffice).
- La vidéo se lit sur place : image d'attente, ▶ au centre, durée en bas à droite.
- **Un lien** peut aussi être une case du carrousel (Seb, 9 novembre ; compte dans les 10). Un lien
  **YouTube** (watch, youtu.be, shorts) se lit dans la case : l'image de la vidéo avec ▶, et la vidéo
  YouTube (youtube-nocookie) ne se charge qu'au toucher, pour que le carrousel glisse encore du
  doigt. Un **autre site** : son image, son titre, son nom (ex. contretemps.fr) et un bouton
  « Ouvrir le lien » (nouvel onglet). Titre et image sont lus **une fois**, quand on ajoute le lien
  (YouTube : oEmbed ; autre site : balises `og:title` / `og:image`, sinon `<title>`) ; l'image est
  gardée comme une photo de l'actu, rien n'est relu ensuite. Le serveur ne lit que des adresses
  publiques (pas le VPS lui-même ni un réseau privé).
- Sous le texte : « **Prénom** · 6 novembre », jamais d'heure.
- Pastille **« Nouveau »** sur les actus publiées depuis la dernière visite de la personne sur Actus.
  Elle s'efface à la visite suivante. Pas de badge sur l'onglet (les badges sont réservés à ce que la
  personne a à faire).

## 4. L'onglet Édition *(droit 🔒 Publier les actualités)*

### 4.1 Liste

- Toutes les actus, brouillons compris, de la plus récente à la plus ancienne. Chaque ligne : une barre
  de couleur pour le niveau (rouge Important, orange Normal, beige Brève), le début du texte, une
  pastille **Publiée** (vert) ou **Brouillon** (jaune), puis « Niveau · date ».
- Toucher une ligne ouvre l'actu dans l'éditeur.
- Bouton principal en bas : **Nouvelle actu**.
- Sous la liste, **« Paramètres d'édition des actus »**, repliés par défaut (on touche le titre pour les
  dérouler ; Seb, 8 novembre) : interrupteur **« L'appli affiche toujours les actus à son ouverture »** (§6) et le compte
  **Instagram** relié (§6 bis). Même présentation que les volets d'Admin › École (titre en capitales,
  flèche ›/⌄ à gauche, sous-parties « Ouverture de l'appli », « Visibilité » (§2 bis), « Instagram » ;
  Seb, 9 novembre). En tête, **« En haut de chaque actu : Texte | Photo, vidéo »** (Seb, 9 novembre ;
  Texte par défaut) : un seul réglage pour toute l'école, que suivent toutes les cartes Normal et
  Important, l'aperçu de l'éditeur compris. Le menu ⋯ du bandeau (qui publie, onglets Édition et Visualisation) a l'entrée
  **« Paramètres d'édition des actus »** : elle passe sur Édition, déplie les paramètres et y descend.

Toute personne qui a le droit peut modifier ou supprimer toutes les actus, pas seulement les siennes
(le bureau se relaie).

### 4.2 Éditeur (Nouvelle actu / Modifier l'actu)

De haut en bas :

1. **Niveau** : trois grands boutons Important / Normal / Brève (Normal par défaut), avec une ligne
   d'explication sous le choix.
2. **Texte** : obligatoire pour une Brève ; facultatif dès qu'il y a une photo, une vidéo, un lien ou un
   document (Seb, 10 novembre). Sans texte, la carte n'a pas de ligne vide et la notification dit
   « Nouvelle actu ».
3. **Photo**, **Vidéo**, **Lien**, **Document** (cachés pour une Brève), sur deux lignes. Lien : un
   champ « Collez le lien (YouTube ou autre site) » et **Ajouter** (sans `https://`, on l'ajoute) ;
   le lien rejoint les vignettes comme une photo. Photo : galerie ou appareil photo.
   Vidéo : jusqu'à 100 Mo avant compression, comme dans la Messagerie. Document : choisi dans Docs
   (on descend dans les dossiers, on touche le fichier). Photo et Vidéo **ajoutent** (plusieurs photos
   d'un coup), 10 au plus ; les vignettes s'alignent sous les boutons, chacune avec ✕ pour la
   retirer. Toucher à nouveau Document le retire. Passer en Brève retire tout.
4. **En haut jusqu'au** (Important seulement) : une date, proposée à J+7.
5. **Envoyer une notification** : interrupteur, allumé d'office pour Important, éteint pour Normal et
   Brève ; on peut le changer à chaque actu (Seb, 6 novembre).
6. **Ce que verront les autres** : l'actu telle qu'elle sortira, mise à jour à chaque lettre.
7. En bas : bouton secondaire **Brouillon**, bouton principal **Publier** (**Enregistrer** pour une
   actu déjà publiée), grisé tant que le texte est vide. ← revient sans rien enregistrer.
8. Pour une actu existante : lien « Supprimer cette actu ».

Après Publier : retour sur l'onglet Visualisation, l'actu en haut, et « Actu publiée · Annuler » pendant
10 s (Annuler la remet en brouillon et n'envoie pas la notification). Supprimer : « Actu supprimée ·
Annuler » pendant 10 s.

## 5. Notification

Si l'interrupteur est allumé, la publication envoie une notification push à tous les membres de
l'organisation, sauf l'auteur, avec le système existant (`notifications`, comme la Messagerie) :

- titre : le nom de l'organisation ; corps : le début du texte (100 caractères) ;
- la toucher ouvre l'appli (sur Actus si l'option du §6 est allumée).

La notification part **à la fin des 10 s d'Annuler**, pas avant (minuteur du serveur, `news/news.py`),
et une seule fois. Modifier une actu publiée ne renvoie pas de notification.

## 6. Option « L'appli affiche toujours les actus à son ouverture »

Libellé à l'écran (Seb, 9 novembre 2026, à la place d'« Ouvrir l'appli sur les actus », pas clair) :
interrupteur « L'appli affiche toujours les actus à son ouverture », et dessous en petit « Sinon, elle
affiche le dernier onglet ouvert. »

Par organisation, **allumée par défaut**. Allumée : à chaque ouverture de l'appli (lancement, pas
retour d'arrière-plan, ni page rechargée par F5 ou par la mise en ligne d'une nouvelle version : Seb,
10 novembre), tout le monde arrive sur Actus. Tant qu'**aucune actu n'est publiée**, l'appli s'ouvre
comme si l'option était éteinte : un onglet vide à l'ouverture, c'est déprimant (Seb, 10 novembre). Éteinte : l'appli s'ouvre comme aujourd'hui sur
le dernier onglet utilisé (`ongletDeDepart` dans App.jsx). Une notification d'un autre module garde
son propre écran.

## 6 bis. Relayer un compte Instagram (Seb, 8 novembre 2026)

Les testeurs publient déjà sur Instagram : les nouveaux posts d'un compte Instagram arrivent tout
seuls dans les actus, sans rien ressaisir.

- **Condition d'Instagram** : un compte professionnel (Créateur conseillé, ou Entreprise), donc public.
  Instagram ne laisse aucune appli lire un compte personnel.
- **Relier** (Paramètres d'édition des actus › Instagram, droit 🔒 Publier les actualités) : bouton **« Se
  connecter avec Instagram »** (Seb, 8 novembre au soir : coller une clé était trop pénible). Instagram
  demande de se connecter au compte et d'accepter, puis revient dans l'appli, Paramètres d'édition des actus
  ouverts : « Relié à @compte », ou la raison de l'échec. La clé obtenue (60 jours, renouvelée seule
  chaque semaine) est gardée chiffrée (`securite/chiffrement.py`, comme la clé HelloAsso). « Délier »
  l'oublie ; les actus déjà relayées restent.
- **L'appli Meta** (une fois, sur un ordinateur ; faite le 11 novembre 2026 avec le compte Meta de
  Jacqueline, appli « Contretemps Actus », portefeuille business « Ecole de danse Contretemps », non
  vérifié) : developers.facebook.com › Créer une application › cas d'utilisation « Gérer les messages et
  le contenu sur Instagram » › Personnaliser › **API setup with Unified login** (les nouvelles applis
  Meta n'ont plus la connexion Instagram seule) › portefeuille business › « Créer une nouvelle
  configuration » (modèle : token utilisateur système, sans expiration) › URL de redirection
  `https://silvaplana.cloud/contretemps/api/news/instagram/return`. Dans `backend/.env` du VPS
  (DEPLOY.md §4) : `INSTAGRAM_APP_ID` (Paramètres › Général), `INSTAGRAM_APP_SECRET`,
  `INSTAGRAM_REDIRECT_URL`, `INSTAGRAM_CONFIG_ID` (l'ID de configuration). Tant que l'appli n'a pas passé
  le Contrôle app de Meta, seuls les comptes qui ont un rôle dans l'appli (Rôles › **Testeur(se)
  Instagram**, invitation acceptée dans Instagram › Paramètres › Applications et sites web) peuvent se
  connecter ; pour tout le monde (AppBase), Contrôle app et vérification du portefeuille.
- **Connexion unifiée** : le bouton ouvre la fenêtre de connexion de Facebook avec la configuration
  (`facebook.com/dialog/oauth`, `config_id`, `prompt=login` : on peut choisir Instagram) ; pas de Page
  Facebook nécessaire. Le code s'échange sur graph.facebook.com contre une clé qui n'expire pas (jamais
  renouvelée) ; le compte est celui que la personne a autorisé (`me/assigned_instagram_accounts`, sinon
  par une Page), ses posts se lisent par son identifiant (`{id}/media`).
- **Quels posts** (Seb, 11 novembre, maquette validée `spec/maquettes/actualites-instagram.html`) : sous
  Instagram, une question « Quels posts Instagram mettre dans les actus ? » à trois réponses, une seule
  cochée, réglable avant de relier (réglage de l'école) ; c'est la personne qui relie (droit Publier)
  qui choisit :
  - « Tous mes posts » : chaque nouveau post arrive, publié.
  - « Seulement ceux avec un hashtag » : ouvre un champ « # » ; seuls les posts dont le texte porte ce
    hashtag arrivent, publiés (#contretemps, pas #contretempsdanse ; majuscules indifférentes), les
    autres restent sur Instagram. Champ vide : tous.
  - « Je les choisis un par un » : chaque post arrive en **Brouillon** dans Édition, à publier ou non.
  En base : `instagram_hashtag` (vide sauf pour la 2e réponse) et `instagram_publish` (faux pour la 3e).
- **Sans l'appli Meta sur le serveur** (variables absentes) : à la place du bouton, on colle une clé
  d'accès générée dans l'appli Meta (« Générer des jetons d'accès »), puis « Relier ».
- **Le retour** arrive sur une seule adresse (`GET /news/instagram/return`, publique) ; `state`, signé
  par le serveur et valable 30 minutes, dit quelle école et qui. Le serveur échange le code contre la
  clé, relie le compte, puis renvoie vers l'adresse de l'école (`?instagram=ok|annule|erreur`), comme
  la connexion bancaire du Financier.
- **Relais** : toutes les 5 minutes (`app/relance_worker.py`), chaque post publié **après** la liaison
  (et portant le hashtag s'il y en a un) devient une actu **Normal**, publiée (ou en brouillon, voir
  ci-dessus), sans notification, signée du prénom de qui a relié le compte :
  le texte du post, puis sa photo ou sa vidéo ; un carrousel Instagram arrive entier, en carrousel. Une seule fois par
  post (`instagram_id`). Elle se modifie ou se supprime ensuite comme les autres.
- Instagram ne prévient pas d'un nouveau post (pas de webhook pour les posts) : d'où les 5 minutes.
- Une erreur (clé refusée, compte devenu personnel…) s'affiche sous « Relié à @compte ».

Code : `news/instagram.py` (bouton : « Instagram API with Unified Login », graph.facebook.com ; clé collée :
« Instagram API with Instagram Login », graph.instagram.com).

## 7. Données

Tables préfixées `news_`, avec `org_id` (= `ecoles.id`) et filtre par organisation sur chaque requête.

**`news_items`**

| Colonne | Type | Note |
|---|---|---|
| `id` | int | |
| `org_id` | int, FK `ecoles.id` | |
| `level` | str | `important` / `normal` / `brief` |
| `body` | text | |
| `on_top_until` | date, nul | Important seulement |
| `notify` | bool | |
| `notified_at` | datetime, nul | la notification est partie (une seule fois) |
| `author_id` | int, FK `comptes.id`, nul | la fiche de la personne qui a publié |
| `author_name` | str | son prénom, gardé pour les saisons suivantes |
| `published_at` | datetime, nul | nul = brouillon |
| `created_at`, `updated_at` | datetime | |

Étape 2 (médias, migration `a7d3e91c4b20`) :

| Colonne | Type | Note |
|---|---|---|
| `document_id` | int, FK `doc_nodes.id`, nul | fichier de Docs (pas un dossier) de la même organisation |

Carrousel (migration `c4e8a1f7b352`, qui y recopie la photo ou la vidéo de chaque actu existante) :
table **`news_media`**, une ligne par photo ou vidéo. Une table plutôt qu'une liste dans une colonne :
la clé étrangère vers `videos` reste, et une vidéo supprimée ailleurs ne laisse rien derrière.

| Colonne | Type | Note |
|---|---|---|
| `id` | int, PK | |
| `item_id` | int, FK `news_items.id` (cascade) | l'actu |
| `position` | int | l'ordre dans le carrousel, à partir de 0 |
| `photo_sha` | str, nul | empreinte de la photo, rangée par `storage/` dans `NEWS_DIR` (par défaut `actualites/` à côté des vidéos), dossier de l'organisation ; on garde l'original et une copie JPEG de 1600 px au plus, la seule montrée |
| `video_id` | int, FK `videos.id`, nul | module Vidéos : compression, image d'attente, lien signé ; rangée dans « Actualités » du panneau Usage |
| `link_url` | str(2000), nul | lien de la case (http ou https), migration `e7a4c2d9b815` (Seb, 9 novembre) ; son image, s'il y en a une, est dans `photo_sha` |
| `link_title` | str(300), nul | titre du lien, lu quand on l'ajoute |

Une ligne a soit une photo, soit une vidéo, soit un lien (avec ou sans photo, son image). Deux
colonnes nulles plutôt qu'une table : un lien est une case du carrousel comme les autres, et son
image, rangée comme une photo, est effacée par le même chemin. Retirer une photo ou une vidéo d'une actu, ou supprimer
l'actu, les efface. Une vidéo
supprimée ailleurs (panneau Usage) laisse l'actu sans vidéo. Le document n'est qu'un lien : le
supprimer de Docs fait disparaître le bouton. Le dossier des photos est compté dans « Usage
ressources » (Admin › École).

Supprimer est définitif : l'écran attend la fin des 10 s d'Annuler avant d'appeler le serveur, comme
Sparring.

**`news_seen`** : `compte_id` (clé), `seen_at`. Sert à la pastille « Nouveau ». La fiche change à
chaque saison : « Nouveau » repart de zéro à la rentrée.

**`news_instagram`** (§6 bis) : `org_id` (clé), `token_encrypted`, `username`, `linked_by`,
`linked_by_name`, `linked_at` (seuls les posts d'après comptent), `token_refreshed_at`,
`last_sync_at`, `last_error`, `ig_user_id` (compte relié par la connexion unifiée : ses posts se
lisent par cet identifiant ; vide pour une clé collée), `refreshes` (faux pour la connexion unifiée :
clé sans expiration). Et sur `news_items` : `instagram_id` (le post relayé). Migrations
`b81f2c6d9e47`, puis `c8f1a3e5d7b2`.

**`news_settings`** : `org_id` (clé), `open_on_news` (bool, vrai par défaut ; pas de ligne = vrai),
`media_first` (bool, faux par défaut : texte en haut ; migration `d5f2b8c1e604`, colonne ajoutée à la
table existante plutôt qu'une nouvelle table : c'est un réglage de plus de l'école), `visible_to_all`
(bool, vrai par défaut et pour les lignes existantes ; §2 bis ; migration `b6e2d9f4a1c7`, qui supprime
aussi les groupes 🔒 `right.news.read` et leurs membres), `instagram_hashtag` (texte, vide par défaut =
tous les posts) et `instagram_publish` (bool, vrai par défaut ; faux : brouillons) ; §6 bis ; migration
`c8f1a3e5d7b2` ; dans les réglages de l'école plutôt que sur
`news_instagram`, pour se régler avant de relier et survivre à « Délier »).

Le document reste une colonne : une actu en a au plus un (§3.3). Pas de lien avec les saisons : une actu appartient à l'organisation.

## 8. API

Toutes sous `/ecoles/{ecole_id}/news` (code : `news/receiver.py`).

| Route | Qui | Rôle |
|---|---|---|
| `GET …/news` | qui voit les actus (§2 bis) | `can_publish`, `media_first` et les actus publiées, dans l'ordre du §3.2, avec `is_new` ; met à jour `news_seen` |
| `GET …/news/atelier` | droit | Toutes, brouillons compris |
| `POST …/news` · `PUT …/news/{id}` | droit | Créer, modifier ; `publish` : publier ou garder en brouillon |
| `POST …/news/{id}/unpublish` | droit | Annuler d'une publication (repasse en brouillon) |
| `DELETE …/news/{id}` | droit | Supprimer |
| `GET …/news/settings` · `PUT …/news/settings` | tous · droit | Option d'ouverture, `has_news` (au moins une actu publiée), `media_first` (le `PUT` ne change que ce qu'on lui donne) ; `visible_to_all` et `can_read` (voit l'onglet ; §2 bis) |
| `POST …/news/photos` | droit | Envoi d'une photo (25 Mo au plus) ; rend son empreinte, à donner ensuite dans `media` (`{photo}`) |
| `POST …/news/videos` | droit | `upload_id` d'un envoi par blocs (module Vidéos, comme la Messagerie) : en fait une vidéo, à donner ensuite dans `media` (`{video_id}`) |
| `POST …/news/links` | droit | `url` : lit le titre et l'image du lien ; rend `link`, `title`, `photo` (l'image gardée, ou nul) et `preview` (la même en `data:` pour l'éditeur), à donner ensuite dans `media` (`{link, title, photo}`) ; 400 si le lien ne répond pas |
| `GET …/news/{id}/photos/{empreinte}` | tous | Une photo de l'actu (JPEG) ; brouillon : droit seulement |
| `GET · PUT · DELETE …/news/instagram` | droit | Compte Instagram relié (§6 bis) : état (`can_sign_in` : bouton possible), relier avec `token`, délier |
| `POST …/news/instagram/login` | droit | « Se connecter avec Instagram » : l'adresse de la page d'Instagram |
| `GET /news/instagram/return` | public | Retour d'Instagram (`code`, `state`) : relie, puis renvoie vers l'appli de l'école |

Les actus s'envoient et se rendent avec `media`, liste ordonnée (10 au plus) d'éléments `photo` ou
`video` (rendue avec ses liens signés), et `document` (`id`, `name`).

Module éteint dans l'organisation : onglet caché, routes en 404 (spec/core.md §9 bis.3).

## 9. Assistant

Un bouton de l'écran = un outil de l'assistant : actions « Publier une actu » (niveau, texte,
notification ; `publish_news`) et « Supprimer une actu » (`delete_news`) dans `news/actions.py`,
réservées au droit, carte Faire/Annuler comme les autres.

Le guide de l'assistant (`news/guide.md`) ne se lit, comme pour tout module à droit, que par qui a le
droit (`assistant/guide.py`).

## 10. Étapes

Chaque étape part sur le « vas-y » de Seb, une PR chacune, avec le `guide.md` du module.

1. **Actus en texte** : tables, API, onglet Actus, Édition | Visualisation, trois niveaux, En haut jusqu'au,
   brouillon, supprimer/Annuler, « Nouveau », notification, option d'ouverture, actions de l'assistant.
   **Fait** (6 novembre 2026, PR de l'étape 1). L'onglet s'ouvre sur Visualisation, même pour qui publie.
2. **Médias** : photo, vidéo (lecture sur place), document de Docs. **Fait** (7 novembre 2026, PR de
   l'étape 2). Carrousel de 10 photos et vidéos, et carrousels d'Instagram (8 novembre 2026).

## 11. Questions ouvertes

Voir §12.10.

## 12. Le module devient « Publications » : plusieurs blogs (Seb, 12 novembre 2026)

Statut : **codé** (PR #233, les trois étapes ensemble, Seb : « on ne met pas en ligne pour l'instant »). Écrans validés par Seb sur maquette le 12 novembre :
[`spec/maquettes/blog.html`](../maquettes/blog.html) (tout est cliquable ; le bouton « Écran » passe
d'Actus à Techniques et à Admin › École › Fonctionnalités). Les écrans suivent la maquette exactement.

### 12.1 Pourquoi

Seb veut, pour le club de combat d'abord, des techniques (un texte et des vidéos) publiées comme les
actus, rangées par catégorie. Plutôt qu'un module copié sur Actus, on généralise : c'est un **blog**,
des billets qui arrivent au fil de l'eau et qu'on retrouve aussi par catégorie. Le module s'appelle
**Publications** (Seb, 12 novembre : « Blog » et « Techniques » trop spécifiques), à l'écran comme dans
le code : `backend/src/publications/`, `frontend/src/modules/publications/`, clé `publications`,
tables `pub_`. Gardés tels quels pour ne rien casser : le dossier des photos (`actualites`, variable
`NEWS_DIR`), l'adresse de retour d'Instagram `/news/instagram/return` (déclarée chez Meta) et les noms
des actions de l'assistant (`publish_news`, `delete_news`). Dans ce §12, « blog » désigne un onglet du
module (Actus, Techniques).

### 12.2 Plusieurs blogs par organisation

- Une organisation a **un ou plusieurs blogs**. Chaque blog a son onglet dans la barre du bas, à la
  suite, juste après Admin, dans l'ordre de création. Contretemps : un blog « Actus ». Club de combat :
  « Actus » et « Techniques ».
- À la mise en ligne, chaque organisation garde ce qu'elle a : un blog « Actus », logo journal, avec
  niveaux, sans catégories, avec toutes ses actus et ses paramètres. Rien ne change à l'écran pour
  Contretemps, sauf le §12.5.
- Le mot « Cours » n'est pas proposé comme nom : il désigne déjà les groupes (spec/core.md §5).

### 12.3 Où ça se règle : Admin › École › Personnalisation de l'application › Fonctionnalités

Sous la case **Publications** (Administrateur principal et Super User, comme toute la partie Fonctionnalités),
la liste des blogs de l'organisation. Pour chaque blog :

| Réglage | Effet |
|---|---|
| **Nom** | Le nom de l'onglet et du droit de publier (§12.4). Obligatoire, unique dans l'organisation. |
| **Logo** | L'icône de l'onglet, à choisir parmi six (journal, livres, caméra, toque, étoile, coupe). |
| **Avec des catégories** | Éteint : un simple fil. Allumé : nom et catégorie sur chaque billet, onglets Fil \| Catégories (§12.6). |
| **Avec les niveaux Important, Normal, Brève** | Allumé : §3.1 et §4.2 comme aujourd'hui. Éteint : pas de boutons de niveau dans l'éditeur, tous les billets sont des cartes Normal. |

Dessous, **+ Ajouter un blog** : on tape son nom, il arrive sans catégories ni niveaux, logo journal.
La case Publications décochée cache tous les blogs sans rien effacer (spec/core.md §11.3). Chaque réglage
s'enregistre tout de suite. Éteindre les catégories ou les niveaux n'efface rien : les billets gardent
leur nom, leur catégorie et leur niveau, qui reviennent si on rallume.

Cet emplacement est le `settings` qu'un module déclare déjà dans son `module.js` (spec/core.md §11.1,
comme la connexion HelloAsso).

### 12.4 Qui lit, qui publie

- **Lire** : tout le monde par défaut. Chaque blog garde l'interrupteur « visibles par tout le monde »
  (§2 bis) dans ses paramètres.
- **Publier** : un droit 🔒 **par blog**, dont le nom suit celui du blog : « Publier dans Actus »,
  « Publier dans Techniques ». Il se coche dans Admin › École › Administrateurs, comme aujourd'hui.
  Renommer le blog renomme le droit. Le droit actuel « Publier les actualités » devient celui du blog
  Actus, avec les mêmes personnes.
- Les profs peuvent ainsi publier des techniques sans toucher aux actus.

### 12.5 Un seul écran : plus d'onglets Édition | Visualisation

Dans tous les blogs, Actus compris (remplace le §2 et le §4.1) : qui publie voit **le même fil que
tout le monde**, avec en plus :

- le bouton principal **+ Ajouter** en bas ;
- un **crayon** sur chaque billet, qui l'ouvre dans l'éditeur (§4.2, inchangé ; « Supprimer » y reste) ;
- **« Mes brouillons · vous seul les voyez »** en haut du fil, dans un cadre en pointillés, chaque
  brouillon avec la pastille Brouillon. Tous ceux qui ont le droit sur ce blog voient tous ses
  brouillons. Publier un brouillon le fait descendre à sa place ;
- le menu **⋯** du bandeau, entrée **« Paramètres de <nom du blog> »** (« Paramètres d'Actus »,
  « Paramètres de Techniques »), qui ouvre un écran avec ← : les mêmes parties qu'aujourd'hui (En haut
  de chaque billet, Ouverture de l'appli, Visibilité, Instagram). **Le même écran pour tous les
  blogs** : il n'y a qu'une sorte de blog, aucun paramètre n'est propre aux actus (Seb, 12 novembre). L'appli ne s'ouvre que sur un blog à la
  fois : allumer l'option dans un blog l'éteint dans les autres. Le relais Instagram (§6 bis) reste
  celui de l'organisation et alimente le blog où on l'a relié ; les autres blogs ne le proposent pas
  tant qu'il est relié ailleurs.

Après Publier, on revient sur le fil, le billet à sa place, « Publiée · Annuler » 10 s.

### 12.6 Blog avec catégories

**Le billet** a en plus :

- un **nom**, obligatoire (« Clé de bras en croix »), en titre de la carte ; il n'y a pas de réglage à
  part : le nom va avec les catégories, il en faut un pour lister les billets d'une catégorie ;
- une **catégorie**, obligatoire, et au besoin une **sous-catégorie** (un seul niveau, comme les
  groupes : jamais de 4e niveau). La carte la montre en pastille « # Projections › Balayages » ; la
  toucher ouvre cette catégorie.

**Deux onglets en haut, pour tout le monde : Fil | Catégories** (mots fixes, pas de réglage ; Seb,
12 novembre).

- **Fil** : les billets du plus récent au plus ancien, comme le §3.
- **Catégories** : les catégories par ordre alphabétique, sous des lettres A, B, C…, chacune avec son
  nombre de billets. Toucher une catégorie montre ses sous-catégories (ordre alphabétique, avec leur
  nombre), puis les billets rangés directement dedans, par ordre alphabétique de nom. Une ligne de
  billet : son nom et « Vidéo · 0:42 », « Photo » ou « Texte ». La toucher ouvre le billet seul. ←
  revient d'un cran. + Ajouter depuis une catégorie la propose déjà cochée.

**Gérer les catégories**, sans écran à part :

- Dans l'éditeur, sous le texte : **Catégorie**, les catégories existantes en gros boutons (ordre
  alphabétique) et **+ Nouvelle**, qui ouvre un champ et OK. Une catégorie choisie, la même chose pour
  **Sous-catégorie (facultatif)**. Pas de hashtag tapé à la main : pas de doublon par faute de frappe.
- **Jamais de catégorie vide** : une catégorie ou sous-catégorie existe tant qu'un billet (brouillon
  compris) y est rangé ; elle disparaît avec le dernier. C'est ainsi qu'on la supprime.
- **Renommer** : qui publie entre dans la catégorie (onglet Catégories) et touche « Renommer « … » ».
  Lui donner le nom d'une catégorie qui existe déjà au même niveau **réunit** les deux.
- Majuscules et accents ne distinguent pas deux catégories (« Clés » = « cles »).

### 12.7 Données

Migration `f3b9d2a6c8e1` : crée les tables `pub_`, recopie tout avec les mêmes numéros (INSERT … SELECT,
SQL portable), puis supprime les tables `news_`. Retour en arrière possible (titres et catégories
perdus).

- **`pub_blogs`** : `id`, `org_id`, `name`, `icon` (news, books, video, cap, star, cup), `position`,
  `with_levels`, `with_categories`, et les paramètres du blog `open_app_on`, `media_first`,
  `visible_to_all`. Nom unique dans l'organisation (sans tenir compte des majuscules ni des accents,
  vérifié par le code). La migration crée « Actus » (niveaux allumés, sans catégories) dans **chaque**
  organisation, avec les réglages de `news_settings` ; une organisation créée ensuite le reçoit à sa
  première visite.
- **`pub_posts`** (ex-`news_items`) gagne `blog_id`, `title`, `category_id` (la sous-catégorie quand il
  y en a une). **`pub_media`** (ex-`news_media`, `post_id`). **`pub_seen`** : clé (`compte_id`,
  `blog_id`). **`pub_categories`** : `id`, `blog_id`, `parent_id` (nul pour une catégorie), `name`.
- Instagram reste celui de l'organisation : **`pub_instagram`** (ex-`news_instagram`) gagne `blog_id`,
  le blog où ses posts arrivent ; **`pub_instagram_settings`** garde le hashtag et « publier tout de
  suite ».
- Le droit : le groupe `right.news.publish` devient `right.publications.publish.<id d'Actus>`, nommé
  « Publier dans Actus », mêmes membres (Stellina Revel chez Contretemps). `org_modules` : la ligne
  `news` devient `publications`, le module garde son état. Test : `tests/test_publications_blogs.py`.

### 12.8 Deux ajouts au core, à valider par Seb (spec/core.md §11.1)

Aujourd'hui un module déclare ses droits et ses onglets en dur. Un blog créé à l'écran demande que le
module puisse en déclarer **par organisation** :

1. **Droits** : en plus de `rights`, un module peut donner `org_rights(db, org_id)`, la liste des
   droits propres à cette organisation (`Right("publications.publish.<id du blog>", "Publier dans Techniques")`).
   Le core crée leur groupe 🔒 et les contrôle par le même `has_right` ; `GET /ecoles/{id}/droits`
   les liste avec les autres. Le libellé est recalculé à chaque lecture : renommer le blog suffit.
   Côté core : `groups/rights.py` (`provide`, `declared_for`, `rename`, `forget`), `registry`
   (`org_rights`, `rights_of`). Renommer le blog renomme aussi ses groupes.
2. **Onglets** : dans `module.js`, `tabs` peut être une fonction qui reçoit ce que le module a chargé
   pour l'organisation (ici la liste des blogs) et rend ses onglets (clé, libellé, icône) ; leurs clés
   commencent par `tabPrefix` (`blog-<id>`), pour retrouver l'onglet ouvert au démarrage
   (`data/nav.js` : `ongletsAvec`, `ongletCalcule`).

Rien d'autre ne change dans le core ; les autres modules ne sont pas touchés.

### 12.9 API, assistant, étapes

Routes sous `/ecoles/{ecole_id}/publications/blogs` : `GET` (les blogs, avec `can_read`,
`can_publish`, `open_app_on`, `has_posts`), `POST`, `PUT · DELETE /{blog_id}` (Administrateur
principal, Super User). Puis sous `/{blog_id}` : `GET` (le fil, et `drafts` à qui publie ;
`…/atelier` disparaît), `POST /posts`, `PUT · DELETE /posts/{id}`, `POST /posts/{id}/unpublish`,
`GET /posts/{id}/photos/{sha}`, `POST /photos · /videos · /links`, `GET · PUT /settings`,
`GET /categories`, `PUT /categories/{id}` (renommer ou réunir), `GET · PUT · DELETE /instagram`,
`POST /instagram/login`. Le retour d'Instagram ajoute `&blog=<id>` : l'appli rouvre ce blog sur ses
paramètres. Un billet donne sa catégorie par son nom (`category`, `subcategory`) : choisie ou
nouvelle, le serveur la trouve ou la crée. Les actions de l'assistant prennent le nom du blog (par
défaut le premier), et pour un blog à catégories le nom et la catégorie.

Choix faits au codage, à revoir si besoin :
- Un blog sans niveaux montre toutes ses cartes en Normal et garde le niveau enregistré ; nouveau billet
  = Normal.
- Supprimer un blog : seulement vide, jamais le dernier (« Supprimer ce blog » dans Fonctionnalités) ;
  son droit disparaît avec lui.
- Un post Instagram arrivé dans un blog à catégories n'a ni nom ni catégorie : il est dans le Fil, pas
  dans Catégories, jusqu'à ce qu'on le range au crayon.
- Paramètres : « En haut de chaque publication », « L'appli affiche toujours <blog> à son ouverture »,
  « <blog> est visible par tout le monde ». Instagram relié dans un autre blog : le texte dit lequel.

Chaque étape part sur le « vas-y » de Seb, une PR chacune, avec le `guide.md` du module.

1. **Actus en texte** : tables, API, onglet Actus, Édition | Visualisation, trois niveaux, En haut jusqu'au,
   brouillon, supprimer/Annuler, « Nouveau », notification, option d'ouverture, actions de l'assistant.
   **Fait** (6 novembre 2026, PR de l'étape 1). L'onglet s'ouvre sur Visualisation, même pour qui publie.
2. **Médias** : photo, vidéo (lecture sur place), document de Docs. **Fait** (7 novembre 2026, PR de
   l'étape 2). Carrousel de 10 photos et vidéos, et carrousels d'Instagram (8 novembre 2026).

## 11. Questions ouvertes

Voir §12.10.

## 12. Le module devient « Publications » : plusieurs blogs (Seb, 12 novembre 2026)

Statut : **codé** (PR #233, les trois étapes ensemble, Seb : « on ne met pas en ligne pour l'instant »). Écrans validés par Seb sur maquette le 12 novembre :
[`spec/maquettes/blog.html`](../maquettes/blog.html) (tout est cliquable ; le bouton « Écran » passe
d'Actus à Techniques et à Admin › École › Fonctionnalités). Les écrans suivent la maquette exactement.

### 12.1 Pourquoi

Seb veut, pour le club de combat d'abord, des techniques (un texte et des vidéos) publiées comme les
actus, rangées par catégorie. Plutôt qu'un module copié sur Actus, on généralise : c'est un **blog**,
des billets qui arrivent au fil de l'eau et qu'on retrouve aussi par catégorie. Le module s'appelle
**Publications** (Seb, 12 novembre : « Blog » et « Techniques » trop spécifiques), à l'écran comme dans
le code : `backend/src/publications/`, `frontend/src/modules/publications/`, clé `publications`,
tables `pub_`. Gardés tels quels pour ne rien casser : le dossier des photos (`actualites`, variable
`NEWS_DIR`), l'adresse de retour d'Instagram `/news/instagram/return` (déclarée chez Meta) et les noms
des actions de l'assistant (`publish_news`, `delete_news`). Dans ce §12, « blog » désigne un onglet du
module (Actus, Techniques).

### 12.2 Plusieurs blogs par organisation

- Une organisation a **un ou plusieurs blogs**. Chaque blog a son onglet dans la barre du bas, à la
  suite, juste après Admin, dans l'ordre de création. Contretemps : un blog « Actus ». Club de combat :
  « Actus » et « Techniques ».
- À la mise en ligne, chaque organisation garde ce qu'elle a : un blog « Actus », logo journal, avec
  niveaux, sans catégories, avec toutes ses actus et ses paramètres. Rien ne change à l'écran pour
  Contretemps, sauf le §12.5.
- Le mot « Cours » n'est pas proposé comme nom : il désigne déjà les groupes (spec/core.md §5).

### 12.3 Où ça se règle : Admin › École › Personnalisation de l'application › Fonctionnalités

Sous la case **Publications** (Administrateur principal et Super User, comme toute la partie Fonctionnalités),
la liste des blogs de l'organisation. Pour chaque blog :

| Réglage | Effet |
|---|---|
| **Nom** | Le nom de l'onglet et du droit de publier (§12.4). Obligatoire, unique dans l'organisation. |
| **Logo** | L'icône de l'onglet, à choisir parmi six (journal, livres, caméra, toque, étoile, coupe). |
| **Avec des catégories** | Éteint : un simple fil. Allumé : nom et catégorie sur chaque billet, onglets Fil \| Catégories (§12.6). |
| **Avec les niveaux Important, Normal, Brève** | Allumé : §3.1 et §4.2 comme aujourd'hui. Éteint : pas de boutons de niveau dans l'éditeur, tous les billets sont des cartes Normal. |

Dessous, **+ Ajouter un blog** : on tape son nom, il arrive sans catégories ni niveaux, logo journal.
La case Publications décochée cache tous les blogs sans rien effacer (spec/core.md §11.3). Chaque réglage
s'enregistre tout de suite. Éteindre les catégories ou les niveaux n'efface rien : les billets gardent
leur nom, leur catégorie et leur niveau, qui reviennent si on rallume.

Cet emplacement est le `settings` qu'un module déclare déjà dans son `module.js` (spec/core.md §11.1,
comme la connexion HelloAsso).

### 12.4 Qui lit, qui publie

- **Lire** : tout le monde par défaut. Chaque blog garde l'interrupteur « visibles par tout le monde »
  (§2 bis) dans ses paramètres.
- **Publier** : un droit 🔒 **par blog**, dont le nom suit celui du blog : « Publier dans Actus »,
  « Publier dans Techniques ». Il se coche dans Admin › École › Administrateurs, comme aujourd'hui.
  Renommer le blog renomme le droit. Le droit actuel « Publier les actualités » devient celui du blog
  Actus, avec les mêmes personnes.
- Les profs peuvent ainsi publier des techniques sans toucher aux actus.

### 12.5 Un seul écran : plus d'onglets Édition | Visualisation

Dans tous les blogs, Actus compris (remplace le §2 et le §4.1) : qui publie voit **le même fil que
tout le monde**, avec en plus :

- le bouton principal **+ Ajouter** en bas ;
- un **crayon** sur chaque billet, qui l'ouvre dans l'éditeur (§4.2, inchangé ; « Supprimer » y reste) ;
- **« Mes brouillons · vous seul les voyez »** en haut du fil, dans un cadre en pointillés, chaque
  brouillon avec la pastille Brouillon. Tous ceux qui ont le droit sur ce blog voient tous ses
  brouillons. Publier un brouillon le fait descendre à sa place ;
- le menu **⋯** du bandeau, entrée **« Paramètres de <nom du blog> »** (« Paramètres d'Actus »,
  « Paramètres de Techniques »), qui ouvre un écran avec ← : les mêmes parties qu'aujourd'hui (En haut
  de chaque billet, Ouverture de l'appli, Visibilité, Instagram). **Le même écran pour tous les
  blogs** : il n'y a qu'une sorte de blog, aucun paramètre n'est propre aux actus (Seb, 12 novembre). L'appli ne s'ouvre que sur un blog à la
  fois : allumer l'option dans un blog l'éteint dans les autres. Le relais Instagram (§6 bis) reste
  celui de l'organisation et alimente le blog où on l'a relié ; les autres blogs ne le proposent pas
  tant qu'il est relié ailleurs.

Après Publier, on revient sur le fil, le billet à sa place, « Publiée · Annuler » 10 s.

### 12.6 Blog avec catégories

**Le billet** a en plus :

- un **nom**, obligatoire (« Clé de bras en croix »), en titre de la carte ; il n'y a pas de réglage à
  part : le nom va avec les catégories, il en faut un pour lister les billets d'une catégorie ;
- une **catégorie**, obligatoire, et au besoin une **sous-catégorie** (un seul niveau, comme les
  groupes : jamais de 4e niveau). La carte la montre en pastille « # Projections › Balayages » ; la
  toucher ouvre cette catégorie.

**Deux onglets en haut, pour tout le monde : Fil | Catégories** (mots fixes, pas de réglage ; Seb,
12 novembre).

- **Fil** : les billets du plus récent au plus ancien, comme le §3.
- **Catégories** : les catégories par ordre alphabétique, sous des lettres A, B, C…, chacune avec son
  nombre de billets. Toucher une catégorie montre ses sous-catégories (ordre alphabétique, avec leur
  nombre), puis les billets rangés directement dedans, par ordre alphabétique de nom. Une ligne de
  billet : son nom et « Vidéo · 0:42 », « Photo » ou « Texte ». La toucher ouvre le billet seul. ←
  revient d'un cran. + Ajouter depuis une catégorie la propose déjà cochée.

**Gérer les catégories**, sans écran à part :

- Dans l'éditeur, sous le texte : **Catégorie**, les catégories existantes en gros boutons (ordre
  alphabétique) et **+ Nouvelle**, qui ouvre un champ et OK. Une catégorie choisie, la même chose pour
  **Sous-catégorie (facultatif)**. Pas de hashtag tapé à la main : pas de doublon par faute de frappe.
- **Jamais de catégorie vide** : une catégorie ou sous-catégorie existe tant qu'un billet (brouillon
  compris) y est rangé ; elle disparaît avec le dernier. C'est ainsi qu'on la supprime.
- **Renommer** : qui publie entre dans la catégorie (onglet Catégories) et touche « Renommer « … » ».
  Lui donner le nom d'une catégorie qui existe déjà au même niveau **réunit** les deux.
- Majuscules et accents ne distinguent pas deux catégories (« Clés » = « cles »).

### 12.7 Données

Migration `f3b9d2a6c8e1` : crée les tables `pub_`, recopie tout avec les mêmes numéros (INSERT … SELECT,
SQL portable), puis supprime les tables `news_`. Retour en arrière possible (titres et catégories
perdus).

- **`pub_blogs`** : `id`, `org_id`, `name`, `icon` (news, books, video, cap, star, cup), `position`,
  `with_levels`, `with_categories`, et les paramètres du blog `open_app_on`, `media_first`,
  `visible_to_all`. Nom unique dans l'organisation (sans tenir compte des majuscules ni des accents,
  vérifié par le code). La migration crée « Actus » (niveaux allumés, sans catégories) dans **chaque**
  organisation, avec les réglages de `news_settings` ; une organisation créée ensuite le reçoit à sa
  première visite.
- **`pub_posts`** (ex-`news_items`) gagne `blog_id`, `title`, `category_id` (la sous-catégorie quand il
  y en a une). **`pub_media`** (ex-`news_media`, `post_id`). **`pub_seen`** : clé (`compte_id`,
  `blog_id`). **`pub_categories`** : `id`, `blog_id`, `parent_id` (nul pour une catégorie), `name`.
- Instagram reste celui de l'organisation : **`pub_instagram`** (ex-`news_instagram`) gagne `blog_id`,
  le blog où ses posts arrivent ; **`pub_instagram_settings`** garde le hashtag et « publier tout de
  suite ».
- Le droit : le groupe `right.news.publish` devient `right.publications.publish.<id d'Actus>`, nommé
  « Publier dans Actus », mêmes membres (Stellina Revel chez Contretemps). `org_modules` : la ligne
  `news` devient `publications`, le module garde son état. Test : `tests/test_publications_blogs.py`.

### 12.8 Deux ajouts au core, à valider par Seb (spec/core.md §11.1)

Aujourd'hui un module déclare ses droits et ses onglets en dur. Un blog créé à l'écran demande que le
module puisse en déclarer **par organisation** :

1. **Droits** : en plus de `rights`, un module peut donner `org_rights(db, org_id)`, la liste des
   droits propres à cette organisation (`Right("publications.publish.<id du blog>", "Publier dans Techniques")`).
   Le core crée leur groupe 🔒 et les contrôle par le même `has_right` ; `GET /ecoles/{id}/droits`
   les liste avec les autres. Le libellé est recalculé à chaque lecture : renommer le blog suffit.
   Côté core : `groups/rights.py` (`provide`, `declared_for`, `rename`, `forget`), `registry`
   (`org_rights`, `rights_of`). Renommer le blog renomme aussi ses groupes.
2. **Onglets** : dans `module.js`, `tabs` peut être une fonction qui reçoit ce que le module a chargé
   pour l'organisation (ici la liste des blogs) et rend ses onglets (clé, libellé, icône) ; leurs clés
   commencent par `tabPrefix` (`blog-<id>`), pour retrouver l'onglet ouvert au démarrage
   (`data/nav.js` : `ongletsAvec`, `ongletCalcule`).

Rien d'autre ne change dans le core ; les autres modules ne sont pas touchés.

### 12.9 API, assistant, étapes

Les routes du §8 passent sous `/ecoles/{ecole_id}/news/blogs/{blog_id}/…` ; s'ajoutent
`GET · POST …/news/blogs`, `PUT · DELETE …/news/blogs/{blog_id}` (Administrateur principal, Super
User), `GET …/blogs/{blog_id}/categories` et `PUT …/categories/{id}` (renommer, droit du blog).
`GET …/news/atelier` disparaît : le fil rend aussi les brouillons à qui a le droit. Les actions de
l'assistant (§9) prennent le blog, et pour un blog à catégories le nom et la catégorie. Le `guide.md`
du module est mis à jour à chaque étape.

Chaque étape part sur le « vas-y » de Seb, une PR chacune :

1. **Un seul écran** (§12.5) dans Actus : + Ajouter, crayon, Mes brouillons, paramètres derrière ⋯.
   Aucune donnée ne change.
   **Fait** (12 novembre 2026, écran seulement : le serveur ne change pas, les brouillons viennent
   encore de `GET …/news/atelier`, retiré à l'étape 2). Le menu ⋯ dit « Paramètres d'Actus ».
2. **Plusieurs blogs** (§12.2 à §12.4, §12.7, §12.8) : table des blogs, liste dans Fonctionnalités
   (nom, logo, niveaux), un onglet et un droit par blog, les deux ajouts au core. **Codé** (PR #233).
3. **Catégories** (§12.6) : nom, catégorie, sous-catégorie, onglets Fil | Catégories, renommer.
   **Codé** (PR #233).

### 12.10 Questions ouvertes

- **Supprimer un blog** : non montré sur la maquette. Proposé : possible seulement quand il n'a plus
  aucun billet, depuis Fonctionnalités, avec Annuler 10 s ; son droit disparaît avec lui.
- Changer l'ordre des onglets des blogs : pas prévu (ordre de création).
- Recherche par mot dans un blog : pas prévue ; à voir quand un blog aura beaucoup de billets.
- **Les chorégraphies restent un module à part**, pas un blog (étude du 12 novembre, Seb d'accord) :
  rattachées à des cours, des élèves et une saison, gérées par les profs de leurs cours, et tout le
  monde y ajoute ses vidéos au fil de la saison. Le Blog ne connaît ni cours ni élèves ; le partage se
  fait par le module Vidéos.
