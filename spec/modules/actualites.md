# AppBase — Module `news` (Actualités)

Version 0.1, 6 novembre 2026. Statut : **spec à valider** (fil « Module : Actualités »). Écrans
validés par Seb sur maquette le 6 novembre : [`spec/maquettes/actualites.html`](../maquettes/actualites.html)
(tout est cliquable). Les écrans suivent la maquette exactement.

Code : `backend/src/news/` (déjà créé par le core avec le droit « Publier les actualités », PR #147)
et `frontend/src/modules/news/`. Module générique : rien de propre à Contretemps.

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
| A le droit 🔒 Publier les actualités | Deux onglets en haut : **Édition** \| **Visualisation** (d'abord nommés Atelier et Aperçu sur la maquette ; renommés par Seb le 8 novembre) |
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
- **L'appli Meta** (une fois, par Seb, sur un ordinateur, avec un compte Facebook quelconque) :
  developers.facebook.com › Mes applis › Créer une appli (« Autre » › « Entreprise ») › ajouter le
  produit **Instagram** › « Configuration de l'API avec connexion Instagram » › « Configurer la
  connexion professionnelle Instagram » : adresse de redirection
  `https://silvaplana.cloud/contretemps/api/news/instagram/return`. Y relever l'**identifiant** et la
  **clé secrète de l'appli Instagram**, à mettre dans `backend/.env` du VPS (DEPLOY.md §4 :
  `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_REDIRECT_URL`). Tant que l'appli Meta est
  en mode Développement, seuls les comptes Instagram ajoutés dans Rôles de l'appli › **Testeurs
  Instagram** (et qui ont accepté l'invitation dans Instagram) peuvent se connecter ; pour tout le
  monde, il faut la faire valider par Meta (permission `instagram_business_basic`).
- **Sans l'appli Meta sur le serveur** (variables absentes) : à la place du bouton, on colle une clé
  d'accès générée dans l'appli Meta (« Générer des jetons d'accès »), puis « Relier ».
- **Le retour** arrive sur une seule adresse (`GET /news/instagram/return`, publique) ; `state`, signé
  par le serveur et valable 30 minutes, dit quelle école et qui. Le serveur échange le code contre la
  clé, relie le compte, puis renvoie vers l'adresse de l'école (`?instagram=ok|annule|erreur`), comme
  la connexion bancaire du Financier.
- **Relais** : toutes les 5 minutes (`app/relance_worker.py`), chaque post publié **après** la liaison
  devient une actu **Normal**, publiée, sans notification, signée du prénom de qui a relié le compte :
  le texte du post, puis sa photo ou sa vidéo ; un carrousel Instagram arrive entier, en carrousel. Une seule fois par
  post (`instagram_id`). Elle se modifie ou se supprime ensuite comme les autres.
- Instagram ne prévient pas d'un nouveau post (pas de webhook pour les posts) : d'où les 5 minutes.
- Une erreur (clé refusée, compte devenu personnel…) s'affiche sous « Relié à @compte ».

Code : `news/instagram.py` (« Instagram API with Instagram Login », graph.instagram.com).

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
`last_sync_at`, `last_error`. Et sur `news_items` : `instagram_id` (le post relayé). Migration
`b81f2c6d9e47`.

**`news_settings`** : `org_id` (clé), `open_on_news` (bool, vrai par défaut ; pas de ligne = vrai),
`media_first` (bool, faux par défaut : texte en haut ; migration `d5f2b8c1e604`, colonne ajoutée à la
table existante plutôt qu'une nouvelle table : c'est un réglage de plus de l'école), `visible_to_all`
(bool, vrai par défaut et pour les lignes existantes ; §2 bis ; migration `b6e2d9f4a1c7`, qui supprime
aussi les groupes 🔒 `right.news.read` et leurs membres).

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

Aucune pour l'instant.
