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
| A le droit 🔒 Publier les actualités | Deux onglets en haut : **Atelier** \| **Aperçu** |
| Tous les autres | Directement les actus (l'écran Aperçu, sans onglets) |

Le Super User passe toujours ; l'Administrateur principal se coche lui-même s'il veut publier
(spec/core.md §5.3).

## 3. Les actus (Aperçu)

Ce que voient tous les membres ; l'onglet Aperçu des personnes qui publient montre exactement le même
écran.

### 3.1 Trois niveaux

| Niveau | Rendu | Usage |
|---|---|---|
| **Important** | Tout en haut, fond rouge clair, mention « ⚠ IMPORTANT », texte plus gros | Ce qui ne doit pas être manqué |
| **Normal** | Grande carte, la photo ou la vidéo en premier, le texte dessous | Le cas courant |
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
- Au plus **un média** : une photo ou une vidéo (pas les deux). Plus, au besoin, **un document** de
  Docs, montré comme un bouton fichier qui l'ouvre comme dans Docs (PDF dans la visionneuse, Word/Excel
  dans OnlyOffice).
- La vidéo se lit sur place : image d'attente, ▶ au centre, durée en bas à droite.
- Sous le texte : « **Prénom** · 6 novembre », jamais d'heure.
- Pastille **« Nouveau »** sur les actus publiées depuis la dernière visite de la personne sur Actus.
  Elle s'efface à la visite suivante. Pas de badge sur l'onglet (les badges sont réservés à ce que la
  personne a à faire).

## 4. L'Atelier *(droit 🔒 Publier les actualités)*

### 4.1 Liste

- Toutes les actus, brouillons compris, de la plus récente à la plus ancienne. Chaque ligne : une barre
  de couleur pour le niveau (rouge Important, orange Normal, beige Brève), le début du texte, une
  pastille **Publiée** (vert) ou **Brouillon** (jaune), puis « Niveau · date ».
- Toucher une ligne ouvre l'actu dans l'éditeur.
- Bouton principal en bas : **Nouvelle actu**.
- Section **Options** sous la liste : interrupteur **« Ouvrir l'appli sur les actus »** (§6).

Toute personne qui a le droit peut modifier ou supprimer toutes les actus, pas seulement les siennes
(le bureau se relaie).

### 4.2 Éditeur (Nouvelle actu / Modifier l'actu)

De haut en bas :

1. **Niveau** : trois grands boutons Important / Normal / Brève (Normal par défaut), avec une ligne
   d'explication sous le choix.
2. **Texte** (obligatoire).
3. *(étape 2)* **Photo**, **Vidéo**, **Document** (cachés pour une Brève). Photo : galerie ou appareil photo.
   Vidéo : jusqu'à 100 Mo avant compression, comme dans la Messagerie. Document : choisi dans Docs.
4. **En haut jusqu'au** (Important seulement) : une date, proposée à J+7.
5. **Envoyer une notification** : interrupteur, allumé d'office pour Important, éteint pour Normal et
   Brève ; on peut le changer à chaque actu (Seb, 6 novembre).
6. **Ce que verront les autres** : l'actu telle qu'elle sortira, mise à jour à chaque lettre.
7. En bas : bouton secondaire **Brouillon**, bouton principal **Publier** (**Enregistrer** pour une
   actu déjà publiée), grisé tant que le texte est vide. ← revient sans rien enregistrer.
8. Pour une actu existante : lien « Supprimer cette actu ».

Après Publier : retour sur l'onglet Aperçu, l'actu en haut, et « Actu publiée · Annuler » pendant
10 s (Annuler la remet en brouillon et n'envoie pas la notification). Supprimer : « Actu supprimée ·
Annuler » pendant 10 s.

## 5. Notification

Si l'interrupteur est allumé, la publication envoie une notification push à tous les membres de
l'organisation, sauf l'auteur, avec le système existant (`notifications`, comme la Messagerie) :

- titre : le nom de l'organisation ; corps : le début du texte (100 caractères) ;
- la toucher ouvre l'appli (sur Actus si l'option du §6 est allumée).

La notification part **à la fin des 10 s d'Annuler**, pas avant (minuteur du serveur, `news/news.py`),
et une seule fois. Modifier une actu publiée ne renvoie pas de notification.

## 6. Option « Ouvrir l'appli sur les actus »

Par organisation, **allumée par défaut**. Allumée : à chaque ouverture de l'appli (lancement, pas
retour d'arrière-plan), tout le monde arrive sur Actus. Éteinte : l'appli s'ouvre comme aujourd'hui sur
le dernier onglet utilisé (`ongletDeDepart` dans App.jsx). Une notification d'un autre module garde
son propre écran.

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

Étape 2 (médias) : `photo_path` (stockage partagé `storage/`, dossier de l'organisation), `video_id`
(FK `videos.id`, module Vidéos : compression, image d'attente, lien signé), `document_id`
(FK `doc_nodes.id`, fichier de Docs).

Supprimer est définitif : l'écran attend la fin des 10 s d'Annuler avant d'appeler le serveur, comme
Sparring.

**`news_seen`** : `compte_id` (clé), `seen_at`. Sert à la pastille « Nouveau ». La fiche change à
chaque saison : « Nouveau » repart de zéro à la rentrée.

**`news_settings`** : `org_id` (clé), `open_on_news` (bool, vrai par défaut ; pas de ligne = vrai).

Pourquoi des colonnes et pas une table de pièces jointes : une actu a au plus un média et un document
(§3.3), c'est plus simple. Pas de lien avec les saisons : une actu appartient à l'organisation.

## 8. API

Toutes sous `/ecoles/{ecole_id}/news` (code : `news/receiver.py`).

| Route | Qui | Rôle |
|---|---|---|
| `GET …/news` | tous | `can_publish` et les actus publiées, dans l'ordre du §3.2, avec `is_new` ; met à jour `news_seen` |
| `GET …/news/atelier` | droit | Toutes, brouillons compris |
| `POST …/news` · `PUT …/news/{id}` | droit | Créer, modifier ; `publish` : publier ou garder en brouillon |
| `POST …/news/{id}/unpublish` | droit | Annuler d'une publication (repasse en brouillon) |
| `DELETE …/news/{id}` | droit | Supprimer |
| `GET …/news/settings` · `PUT …/news/settings` | tous · droit | Option d'ouverture |

Étape 2 : envoi d'une photo, d'une vidéo par blocs comme la Messagerie.

Module éteint dans l'organisation : onglet caché, routes en 404 (spec/core.md §9 bis.3).

## 9. Assistant

Un bouton de l'écran = un outil de l'assistant : actions « Publier une actu » (niveau, texte,
notification ; `publish_news`) et « Supprimer une actu » (`delete_news`) dans `news/actions.py`,
réservées au droit, carte Faire/Annuler comme les autres.

Le guide de l'assistant (`news/guide.md`) ne se lit, comme pour tout module à droit, que par qui a le
droit (`assistant/guide.py`).

## 10. Étapes

Chaque étape part sur le « vas-y » de Seb, une PR chacune, avec le `guide.md` du module.

1. **Actus en texte** : tables, API, onglet Actus, Atelier | Aperçu, trois niveaux, En haut jusqu'au,
   brouillon, supprimer/Annuler, « Nouveau », notification, option d'ouverture, actions de l'assistant.
   **Fait** (6 novembre 2026, PR de l'étape 1). L'onglet s'ouvre sur Aperçu, même pour qui publie.
2. **Médias** : photo, vidéo (lecture sur place), document de Docs.

## 11. Questions ouvertes

Aucune pour l'instant.
