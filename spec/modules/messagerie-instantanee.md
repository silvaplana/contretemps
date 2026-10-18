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

## 3. Hors de cette étape

- La ligne « Vous — Envoyez-vous un message » de WhatsApp (conversation avec soi-même, pour se garder des
  notes) : pas dans cette étape.
- Les lettres A, B, C… en bord de liste pour sauter dans l'alphabet.

## 4. Écarté

- **Nouveau contact** et **Nouvelle communauté** de WhatsApp : pas repris (Seb, 18 octobre). La messagerie
  est fermée, réservée aux membres de l'organisation, qui sont déjà tous dans la liste.
