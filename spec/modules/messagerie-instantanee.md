# AppBase — Module `messagerie-instantanee`

Version 0.1, 18 octobre 2026. Statut : **brouillon, en cours de validation avec Seb** (fil « Module :
Messagerie instantanée » du projet AppBase).

La messagerie instantanée permet aux membres de l'organisation de s'écrire entre eux, façon WhatsApp :
conversations à deux et groupes. **À ne pas confondre avec le module Assistant IA** (le chat qui aide à
utiliser l'appli), qui est un autre module, avec sa propre spec.

Écrit comme un module AppBase, comme `documents.md` et `notes-de-frais.md` : ce qui ne vaut que pour
Contretemps est marqué *(Contretemps)*.

---

## 1. Ce qui existe déjà

La messagerie est codée dans Contretemps et décrite dans `spec/SPEC.md` §5.5 (écrans) et §6.9 (données).
Ce fichier ne la recopie pas : il décrit les **changements** décidés à partir du 18 octobre 2026. Quand
AppBase existera, §5.5 et §6.9 y seront rapatriés ici.

En bref, aujourd'hui :

- trois écrans, jamais deux à la fois : la liste des conversations, la conversation en plein écran, la
  carte d'une personne ou d'un groupe (`frontend/src/screens/MessagerieScreen.jsx` et
  `frontend/src/screens/messagerie/`) ;
- coches envoyé / reçu / vu, « en ligne », « X écrit… », notifications sur le téléphone ;
- chaque cours a sa conversation de groupe automatique ; l'admin crée d'autres groupes par « Nouveau
  groupe » dans le menu ⋯ de l'en-tête (`NouveauGroupeModal.jsx`) ;
- recherche dans la liste : « Discussions » puis « Contacts », tout le monde peut écrire à n'importe qui
  de l'organisation ;
- côté serveur : `backend/src/messagerie/`.

## 2. Bouton + et écran « Nouvelle discussion » (Seb, 18 octobre)

Modèle : l'écran « Sélectionner un contact » de WhatsApp, ouvert par son bouton de nouvelle discussion.

### 2.1 Le bouton +

- Sur la **liste des conversations**, un gros bouton **+** orange rond en bas à droite, le même que
  celui de Docs, au-dessus de la barre du bas et de la barre système Android / iPhone (« gros et
  simple », SPEC §6.0 bis).
- Visible pour **tous les rôles** : tout le monde peut démarrer une discussion.
- Toucher le + ouvre l'écran « Nouvelle discussion » en plein écran (§2.2). Pas de menu intermédiaire.
- Il n'apparaît pas dans une conversation ouverte ni sur une carte de profil, seulement sur la liste.
- En consultation d'une ancienne saison (lecture seule), il n'apparaît pas.

### 2.2 L'écran « Nouvelle discussion »

En-tête :

- flèche ← qui revient à la liste des conversations ;
- titre **« Nouvelle discussion »**, et en dessous le nombre de contacts (« 48 contacts ») ;
- loupe à droite : la toucher transforme l'en-tête en champ de recherche (§2.4).

Puis, de haut en bas :

1. **Nouveau groupe**, une ligne avec une icône dans un rond de la couleur d'accent : ouvre la
   création de groupe qui existe déjà (`NouveauGroupeModal.jsx`). Réservée à ceux qui peuvent déjà créer
   un groupe (aujourd'hui : les admins) ; les autres ne voient pas la ligne.
2. Un titre de section **« Contacts »**.
3. **Tous les contacts de l'organisation**, une ligne par personne, par ordre alphabétique (§2.3).

L'écran défile en entier (actions comprises), comme WhatsApp.

### 2.3 La liste des contacts

- Contient **tous les comptes de l'organisation** (admins, profs, élèves), sauf soi-même : la même
  population que la section « Contacts » de la recherche actuelle.
- Ordre alphabétique sur le prénom puis le nom, sans tenir compte des accents ni des majuscules.
- Chaque ligne : avatar (couleur distincte pour admins et profs, comme dans la liste des conversations),
  « Prénom Nom » en gros, et en petit dessous le rôle *(Contretemps : « Professeur », « Admin », ou les
  cours de l'élève)*.
- Lignes de 76 px, texte ≥ 17 px (SPEC §6.0 bis).
- **Toucher le nom** ouvre la conversation à deux avec cette personne, ou la crée si elle n'existe pas :
  toujours la même conversation unique par paire de personnes (SPEC §6.9). On arrive directement dans la
  conversation ; un retour arrière ramène à la liste des conversations, pas à cet écran.
- **Toucher l'avatar** ouvre la carte de la personne, comme dans la liste des conversations, sans créer
  la conversation.

### 2.4 La recherche

- La loupe remplace le titre par un champ de saisie, avec le clavier ouvert ; la flèche ← efface la
  recherche et revient au titre.
- Filtre les contacts sur le prénom et le nom, sans accents ni majuscules (même règle que la recherche
  actuelle, `utils/recherche.js`).
- Pendant une recherche, la ligne « Nouveau groupe » est masquée : seuls les contacts qui
  correspondent restent.
- Aucun résultat : « Aucun contact ne correspond. »

### 2.5 Ce qui disparaît

- « Nouveau groupe » dans le menu ⋯ de l'en-tête de la messagerie : remplacé par la ligne de l'écran
  « Nouvelle discussion », pour n'avoir qu'un seul chemin.

### 2.6 Plus de choix du cours dans l'en-tête (Seb, 18 octobre)

- La messagerie instantanée **n'a rien à voir avec les cours** : le badge « Éveil 1 ⌄ » en haut à gauche
  (choix du cours, `components/Header.jsx`, mode `course`) disparaît dans l'onglet Messagerie.
- À sa place, le titre simple **« Messagerie »**, comme dans Docs ou Administration (mode `simple` de
  l'en-tête, liste `headerMode` dans `App.jsx`).
- Rien d'autre ne change : la liste des conversations ne dépendait déjà pas du cours choisi. Les
  conversations de cours restent dans la liste comme les autres.

## 3. Nouveau groupe : voir tout le monde (Seb, 18 octobre)

La fenêtre « Nouveau groupe » existante (`NouveauGroupeModal.jsx` : Nom, Personnes, Ajouter un membre,
Créer le groupe) est gardée telle quelle. On y ajoute un moyen de voir **qui sera vraiment dans le
groupe**.

Le problème : un groupe se compose de personnes (admins, profs, élèves) mais aussi de **cours**, et un
cours compte tous ses élèves et ses profs (SPEC §6.9). Dans la liste « Personnes », on voit « Éveil 1 »
sans savoir qui il y a derrière.

### 3.1 Le bouton œil

- À droite du titre « Personnes », un bouton **œil** avec le nombre total de personnes touchées
  (« 👁 23 »).
- Grisé tant que la liste est vide.
- Le toucher ouvre l'écran « Qui est dans le groupe ? » (§3.2), par-dessus la fenêtre ; la flèche ←
  y revient sans rien perdre de ce qui était saisi.

### 3.2 L'écran « Qui est dans le groupe ? »

- Titre « Qui est dans le groupe ? », et en dessous le nombre de personnes.
- **Toutes les personnes à plat**, une ligne par personne, par ordre alphabétique (prénom puis nom, sans
  accents ni majuscules) : chaque cours est remplacé par ses élèves et ses profs.
- Une personne présente plusieurs fois (ajoutée seule et aussi par un cours, ou dans deux cours)
  n'apparaît **qu'une fois**.
- Chaque ligne : avatar (couleur admins et profs comme ailleurs), « Prénom Nom », et en petit dessous
  **par où elle est dans le groupe** : « Ajoutée directement », « Par Éveil 1 », « Par Éveil 1, Jazz
  ados ».
- Le créateur du groupe y figure aussi, puisqu'il en fait toujours partie (« Vous, créateur du
  groupe »).
- Le calcul suit la même règle que le serveur (`membres_resolus` dans
  `backend/src/messagerie/conversations.py`) : ce qu'on voit est exactement qui recevra les messages.
- Écran en lecture seule : on n'y retire personne (on retire un cours ou une personne dans la
  fenêtre).

### 3.3 La recherche dans cet écran

- Un champ de recherche en haut de la liste.
- En tapant, la liste ne garde que les personnes qui correspondent, et **la partie qui correspond est
  surlignée** dans le nom (« **Stel**lina Revelles »).
- Même règle que les autres recherches : sans accents ni majuscules, sur le prénom et le nom.
- Aucun résultat : « Personne de ce nom dans le groupe. »

### 3.4 Ajouter le Super User *(remplace « Tous » le 2026-10-18)*

- Dans « Ajouter un membre », le sélecteur a une première position **Super User**, à gauche d'Admin :
  Super User | Admin | Prof | Élève | Cours.
- Avec **Super User**, le bouton devient **« Ajouter le Super User »** : il l'ajoute à la liste « Personnes »,
  comme une personne choisie à la main (retirable par sa croix, jamais ajouté deux fois).
- Le Super User n'est pas de l'organisation et n'apparaît dans aucune autre liste (Admin, Prof, Élève) :
  ce bouton et la recherche des contacts sont les seuls moyens de l'ajouter (`spec/core.md` §6.1).
- « Tous » (ajouter tout le monde d'un coup) est retiré : il ne servait à rien (Seb, 18 octobre).

### 3.5 Choisir plusieurs personnes d'un coup

Aujourd'hui on ajoute une personne à la fois (liste déroulante puis « Ajouter »). On passe à une
sélection multiple.

- Toucher **Admin**, **Prof**, **Élève** ou **Cours** dans le sélecteur ouvre un écran de choix en plein
  écran, par-dessus la fenêtre : « Choisir des admins », « Choisir des profs », « Choisir des élèves »,
  « Choisir des cours ». La liste déroulante et le bouton « Ajouter » disparaissent.
- Une ligne par personne (ou par cours), par ordre alphabétique, avec une **case à cocher** ; toucher la
  ligne coche ou décoche.
- **Tout en haut, « Tout sélectionner »** : coche tous les admins, tous les profs, tous les élèves ou
  tous les cours de la liste. Retouché, il décoche tout.
- Un champ de recherche sous « Tout sélectionner », pour les longues listes (élèves) ; la recherche ne
  décoche rien.
- Ceux qui sont déjà dans « Personnes » arrivent **déjà cochés** ; les décocher les retire.
- **Bouton « Valider (N) » toujours visible en bas**, fixé au-dessus de la barre système, quelle que
  soit la position dans la liste : la liste défile derrière lui. Il reporte les choix dans « Personnes »
  et revient à la fenêtre.
- La flèche ← en haut revient à la fenêtre sans rien changer.
- Revenu dans la fenêtre, un bouton « Choisir des admins » (ou profs, élèves, cours) sous le sélecteur
  rouvre le même écran.
- **Super User** (§3.4) reste un bouton direct « Ajouter le Super User », sans écran de choix.

## 4. Liens, actions sur un message, pièces jointes (Seb, 19 octobre)

Modèle : WhatsApp (capture de Seb du 19 octobre : barre d'actions en haut après un appui long, trombone et
appareil photo dans la zone de saisie). Trois étapes, une PR chacune : §4.1-4.2, puis §4.3-4.4, puis §4.5.

### 4.1 Liens

- Une adresse web dans un message (`https://…`, `http://…`, `www.…`) devient **cliquable** dans la bulle,
  soulignée, et s'ouvre dans un nouvel onglet.
- Rien à faire pour l'écrire : on la tape ou on la colle.
- Pas d'aperçu de la page (image, titre) dans cette étape.

### 4.2 Actions sur un message

- **Appui long** sur une bulle (clic droit sur ordinateur) : la bulle est sélectionnée (fond teinté) et
  l'en-tête du fil est remplacé par une **barre d'actions**, comme WhatsApp : ← pour annuler, le nombre de
  messages sélectionnés, puis les actions.
- Toucher d'autres bulles pendant ce mode les ajoute ou les retire de la sélection.
- Un bouton **⋯** visible sur chaque bulle au survol (ordinateur) double l'appui long (« gros et simple »).
- Actions (icône + mot en bulle à l'appui long, touches ≥ 48 px) :
  - **Copier** : copie le texte (plusieurs messages : l'un sous l'autre).
  - **Transférer** : ouvre la liste des conversations et des contacts (même écran que « Nouvelle
    discussion », avec cases à cocher et « Envoyer (N) » toujours visible en bas) ; le message part dans
    chaque conversation choisie, marqué **« Transféré »** au-dessus du texte, avec ses pièces jointes.
  - **Modifier** : seulement ses propres messages, un seul à la fois, et pendant **24 heures**. Le texte
    revient dans la zone de saisie, « Modifier » remplace « Envoyer » ; le message garde sa place et
    affiche **« modifié »** à côté de l'heure.
  - **Supprimer** : seulement ses propres messages (un admin peut supprimer n'importe quel message d'une
    conversation de groupe, pour la modération). Chez tout le monde, la bulle devient « Ce message a été
    supprimé ». **Annuler 10 s** en bas de l'écran plutôt qu'une confirmation. Les pièces jointes sont
    effacées du disque si plus rien ne les utilise.
- Une action impossible pour la sélection (Modifier sur deux messages, Supprimer le message d'un autre)
  n'apparaît pas.
- Modifier et Supprimer arrivent **en direct** chez les autres (comme les nouveaux messages).
- Données : `messages.modifie_at` et `messages.supprime_at` (le texte d'un message supprimé est vidé en
  base), `messages.transfere` (booléen).

### 4.3 Photos et fichiers

- Dans la zone de saisie, à droite du texte : un **trombone** (Fichier) et un **appareil photo** (Photo),
  comme WhatsApp. Sur téléphone, l'appareil photo propose « Prendre une photo » ou « Choisir dans mes
  photos » (choix du téléphone).
- On peut joindre **plusieurs** fichiers ; ils s'affichent en vignettes au-dessus de la zone de saisie,
  avec une croix pour les retirer, et un texte facultatif part avec eux.
- **Photo** : réduite sur le téléphone avant l'envoi (côté le plus long 1 600 px, JPEG), soit environ
  300 Ko au lieu de 4 Mo. Dans la bulle : la photo elle-même ; la toucher l'ouvre en plein écran, avec
  « Télécharger ».
- **Fichier** (PDF, Word, Excel…) : une carte avec l'icône, le nom et la taille ; la toucher l'ouvre ou le
  télécharge. Limite : 25 Mo par fichier.
- Barre de progression pendant l'envoi ; en cas d'échec, la bulle reste « Échec, toucher pour réessayer »
  comme pour le texte.

### 4.4 Où sont rangés les fichiers (Seb, 19 octobre)

- Un **dossier à part, à côté de celui des vidéos de chorégraphie** : `uploads/messagerie/<école>/` à côté de
  `uploads/videos/<école>/` (réglable par `MESSAGERIE_DIR`, comme `VIDEOS_DIR`). Même disque, mêmes
  sauvegardes, et l'on voit d'un coup d'œil ce que pèse la messagerie.
- Dans ce dossier, chaque contenu est rangé par son empreinte, comme dans Documents : un même fichier
  envoyé deux fois (une photo transférée dans trois groupes) n'est gardé qu'une fois. On réutilise pour cela
  la classe de stockage déjà écrite (`documents/storage.py`), sortie dans le core pour que la messagerie ne
  dépende pas du module Documents.
- **Jamais servi en direct** : un fichier ne sort que par une route de la messagerie, après vérification que
  la personne fait partie de la conversation.
- Table `message_pieces_jointes` : message, empreinte, nom d'origine, nature (photo, vidéo, fichier),
  taille, largeur et hauteur pour une photo.
- **Compression, comme WhatsApp**, pour que ça circule vite : la photo est réduite sur le téléphone avant
  l'envoi (§4.3), la vidéo est compressée sur le serveur juste après (§4.5). Les fichiers (PDF, Word…) ne
  sont pas touchés.
- Plus tard, quand le disque sera trop petit : un stockage en ligne (de l'ordre d'un centime par Go et par
  mois) prend la place du dossier sans changer le reste.

### 4.5 Vidéos

- Choisies par le trombone ou l'appareil photo (« Filmer » / « Choisir une vidéo »).
- Même chaîne que le module Vidéos : envoi en morceaux (reprend après une coupure), compression sur le
  serveur après coup (H.264, 1080p au plus), image d'aperçu. La bulle montre l'aperçu avec ▶ et la durée ;
  la vidéo se lit dans l'appli.
- Limite : **100 Mo** par vidéo avant compression.
- L'espace utilisé par la messagerie de chaque école s'affiche dans Admin, à côté de celui des vidéos.

### 4.6 Ce qui se télécharge, et quand (Seb, 19 octobre)

WhatsApp ne télécharge pas tout : selon le réglage (Wi-Fi ou données mobiles, par nature de média), il
montre une vignette floue avec la taille et un bouton de téléchargement. Ici, sans réglage à faire :

- **Photo** : la bulle charge une **vignette** légère (environ 20 Ko, faite à l'envoi) ; la photo réduite
  (§4.3) n'est chargée qu'en la touchant pour l'ouvrir en plein écran.
- **Vidéo** : la bulle montre l'image d'aperçu, ▶, la durée et la taille ; la vidéo ne se charge qu'en
  touchant ▶, et se lit au fur et à mesure (pas besoin d'attendre la fin du téléchargement).
- **Fichier** : une carte avec le nom et la taille ; il ne se télécharge qu'en le touchant.
- Une conversation pleine de photos s'ouvre donc vite, même en 4G : on ne paie que les vignettes.
- Pas de réglage « télécharger automatiquement » dans cette étape.

### 4.7 Partager depuis une autre appli (Seb, 19 octobre)

Depuis YouTube, la galerie photos, Chrome…, le bouton **Partager** du téléphone propose Contretemps dans
la liste des applis, comme WhatsApp.

- Techniquement, deux façons d'installer l'appli existent, et chacune a sa porte :
  - **appli web installée** (écran « Installez l'application » → icône sur l'écran d'accueil, manifeste
    par école servi par `personnalisation/`, `public/sw.js`) : le manifeste se déclare « cible de partage »
    (`share_target`) et le service worker reçoit ce qui est partagé. C'est ce qu'utilisent les membres
    aujourd'hui (le README, qui dit « pas de PWA », est en retard sur le code) ;
  - **appli Android Capacitor** (`frontend/android/`, ANDROID.md) si elle est un jour distribuée : un filtre
    d'intent `ACTION_SEND` dans `AndroidManifest.xml` et un greffon de partage entrant, qui ouvrent le même
    écran.
- Partager ouvre l'écran **« Envoyer à… »** : le même que pour Transférer (§4.2), conversations et contacts
  avec cases à cocher et recherche, et en haut un aperçu de ce qui part (le lien, le texte, la photo).
  « Envoyer (N) » toujours visible en bas ; on arrive ensuite dans la conversation si un seul destinataire,
  sinon dans la liste.
- Pas connecté : on se connecte d'abord, puis l'écran « Envoyer à… » s'ouvre avec ce qui a été partagé.
- Ce qui peut être partagé : un lien et du texte (première PR, avec §4.1-4.2), puis des photos, vidéos et
  fichiers (avec §4.3-4.5).
- **Limite** : fonctionne sur **Android** quand l'appli est installée. **Pas sur iPhone** tant qu'il n'y a
  qu'une appli web : Apple ne le permet pas. Le jour où une appli iPhone Capacitor existera, une extension
  de partage iOS le permettra. D'ici là, sur iPhone, on continue par copier-coller.

## 5. Hors de cette étape

- La ligne « Vous — Envoyez-vous un message » de WhatsApp (conversation avec soi-même, pour se garder des
  notes) : pas dans cette étape.
- Les lettres A, B, C… en bord de liste pour sauter dans l'alphabet.
- Le même œil dans les Infos d'un groupe déjà créé (carte du groupe) : à décider.
- Répondre à un message précis (citation), réactions par emoji, épingler, étoile, notes vocales,
  aperçu des liens : pas dans cette étape.

## 6. Écarté

- **Nouveau contact** et **Nouvelle communauté** de WhatsApp : pas repris (Seb, 18 octobre). La messagerie
  est fermée, réservée aux membres de l'organisation, qui sont déjà tous dans la liste.
