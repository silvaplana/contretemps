# AppBase — Module `saisons`

Version 0.1, 27 octobre 2026. Statut : **à valider par Seb** (fil « Core : groupes et droits »,
reprise de l'étude « Saisons en module optionnel » du 24 octobre). Maquette de la création :
« Créer une saison » (https://claude.ai/artifact/HBmtbMrhW3ec3GdAPCkzgz).

Une association vit par saisons ; une pizzeria ou un commerce, non. Le **core** garde toujours une
**période** ; le module **Saisons** apporte tout ce qui fait vivre plusieurs saisons. Éteint, le
client reste sur sa période unique et ne voit jamais le mot « saison ».

---

## 1. Ce qui reste dans le core : la période

Sans migration ni changement de table :
- la table `saisons` et `saison_id` sur les données (fiches, familles, cours, conversations,
  inscriptions, vidéos, ressources…) ;
- `saisons/portee.py` : chaque requête filtre la période affichée, seule la dernière est
  modifiable ;
- `saisons/automatique.py` : une organisation neuve reçoit sa première période ;
- une fiche par personne et par période, `compte_precedent_id`.

Sans le module, il n'y a qu'une période, sans fin affichée : rien ne change pour le client.

## 2. Ce que le module Saisons apporte

Déclaration `saisons/module.py` : `Module(key="seasons", label="Saisons", mount=mount)`, sans
`requires`, en tête de `app/modules.py`. Pas de `module.js` côté écran : il n'a pas d'onglet.

- Les routes de `saisons/receiver.py` : créer une saison (§3), renommer et changer les dates de la
  courante, supprimer une saison, lister les saisons.
- Le choix d'une ancienne saison (admins) : l'en-tête `X-Saison-Id`, le bandeau « lecture seule ».
- La section Saisons d'Admin > École (`SaisonsSection.jsx`).
- Le mot « saison » à l'écran (« Docs › Saison 2026-2027 », « cumul de la saison »…).

**Module éteint** (règles du core, core.md §11.3) : routes de saison « introuvable », en-tête
`X-Saison-Id` ignoré (`comptes/rbac.py` vide la saison demandée de `portee.py`), section Saisons
cachée, retour à la saison courante (le bandeau disparaît). **Éteindre n'efface rien** : les
anciennes saisons restent en base ; on travaille sur la dernière. Le mot « saison » encore écrit
ailleurs (Docs, Usage des ressources) : remplacé ou retiré au premier client sans saison.

Modules qui en ont besoin, `requires=("seasons",)` : Inscriptions (tarifs et formulaire par saison)
et Financier (Bilan, AG, Prévisionnel raisonnent par saison). Docs, module éteint : pas de dossier de
saison dans Privé, les dossiers réservés (Financier, Notes de frais) rangés dans Permanent
*(reportable au premier client sans saison)*.

## 3. Créer une saison : un seul écran

Comme la maquette « Créer une saison » (core.md §8), un écran prérempli, un bouton.

**L'écran** : titre « Créer une saison », flèche ← pour revenir.
- **Nom** (« 2027-2028 », l'année d'après), **Début** et **Fin** (un an après les dates de la
  courante).
- Une ligne par morceau, avec ce qui sera fait et « Changer… » :
  1. **L'école** : « Comme 2026-2027 · recopiés » (administrateurs, bureau, droits ; les tarifs
     avec l'étape 7). Pas de « Changer… » tant qu'il n'y a rien à choisir.
  2. **Les élèves** : « Comme 2026-2027 · sans les données de l'an dernier ».
  3. **Les profs** : « Comme 2026-2027 · recopiés ».
  4. **Les cours** : « Comme 2026-2027 · recopiés ».
  5. **Les documents** (module Documents allumé) : « Le dossier de la saison · recopié ».
- Bouton principal « Créer la saison 2027-2028 », sous lui : « 2026-2027 passe en lecture seule,
  telle qu'elle était. »
- Après la création, l'appli bascule sur la nouvelle saison (comme aujourd'hui), avec « Annuler »
  pendant 10 s (supprime la saison qui vient d'être créée).

**« Changer… »** ouvre le morceau, avec « La structure » puis « Les données », et OK :
- *La structure* (élèves seulement pour l'instant) : deux boutons, « Celle de 2026-2027 » (tous les
  champs de la fiche, y compris ceux ajoutés par l'école) ou « Structure de base » (les champs que
  l'appli sait lire — date de naissance, adresse, santé — et ceux des modules, sans les champs ajoutés
  par l'école). Dessous, un cadre « N champs » qui les résume et « Regarder… » : la liste des champs
  (Toujours là ; Choisis par Contretemps ; Ajoutés par vous), chacun avec un œil qui le masque dans
  la nouvelle saison (Annuler 10 s ; masqué = retiré de la fiche, ses valeurs gardées). Le choix
  « HelloAsso » viendra avec le module HelloAsso (étape 8).
- *Les données* : une case avec le vrai nombre, « Recopier les 142 élèves de 2026-2027, sans leurs
  paiements », « Recopier les 9 professeurs », « Recopier les 18 cours, avec leurs horaires et leurs
  profs », « Recopier le dossier de la saison ». Une case qui
  dépend d'une autre est grisée tant que l'autre n'est pas cochée, avec « Recopiez d'abord les
  profs. » (cours ← profs, élèves ← cours, comme aujourd'hui).

Par défaut : structure de l'an dernier partout ; profs, cours et documents recopiés ; élèves non
recopiés (ils se réinscrivent). L'organisation ne change que ce qu'elle veut.

**Côté serveur** : la route de création reçoit, en plus d'aujourd'hui, la structure des élèves
(`last` ou `base`) et les champs à masquer ; le reste (`Duplication`) ne change pas.

## 4. Étapes de code (core.md §13, étape 6)

a. **Module Saisons** : déclaration, routes et écrans derrière la case du module, `requires` de
   Inscriptions et Financier, tests module éteint *(faite le 27 octobre 2026)*.
b. **Créer une saison en un écran** (§3), à la place du panneau actuel de `SaisonsSection.jsx`.
