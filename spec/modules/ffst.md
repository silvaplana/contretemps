# AppBase — Module `ffst`

Version 0.1 du 18 novembre 2026. Décisions de Seb du 18 novembre 2026. Repris de Sambo Admin
(`silvaplana/test-python`, `backend/src/ffst/`, onglet Licences), à fonctions identiques. Étude :
https://claude.ai/artifact/7HPSBAeGZ5YrE4jahT213a. Maquette validée par Seb le 18 novembre :
https://claude.ai/artifact/4tizDZ6Br2WxGL5MYwSQfy. Étape 1 codée (§10).

## 1. Ce que fait le module

Une école affiliée à la FFST demande les licences de ses adhérents depuis l'appli : les adhérents
venus de HelloAsso deviennent des licenciés FFST. Le site de la fédération,
`ffst-licences.com`, n'a pas d'API : l'appli s'y connecte avec le compte du club et fait ce qu'un
bénévole ferait à la main.

Module optionnel, éteint par défaut, qui requiert le module HelloAsso (il lui faut le genre, la
date de naissance, l'adresse, le téléphone et l'email du formulaire).

L'appli ne fait que **mettre une demande dans le panier** du site, ou l'en retirer. Valider le
panier et payer la fédération restent faits à la main sur le site.

## 2. La connexion (Fonctionnalités, ligne FFST)

Comme HelloAsso (`modules/helloasso.md` §2) : l'identifiant du club en trois parties et le mot de
passe, bouton **Tester la connexion**, **Enregistrer**. Mot de passe chiffré en base, jamais
réaffiché. Réglages de l'école, aujourd'hui écrits dans le code de Sambo Admin pour ASC : la
discipline (« 0470-SAMBO »), la commune de naissance par défaut (« La Ciotat »), « Droit à l'image »
coché sur une nouvelle demande. Administrateur principal et Super User.

## 3. Lire le site

Trois listes, lues en se connectant puis en simulant le clic qui mène à chaque page ; le tableau
est dans la page :
- **Licenciés** de la saison ;
- **Demandes validées** (à payer) ;
- **Demandes brouillon** (le panier).

Le site reste la seule référence (Seb, 18 novembre). En base, seulement la **copie de la dernière
lecture** des trois listes, avec son heure, remplacée en entier à chaque lecture : l'écran s'ouvre
tout de suite et reste lisible si le site ne répond pas. On relit : par le bouton Rafraîchir,
après chaque action, et **toujours juste avant d'écrire**. Si à l'usage Seb préfère le
comportement de Sambo Admin, relire à chaque ouverture est un réglage.

## 4. Statut FFST d'un adhérent

Colonne **Statut FFST** du tableau des adhérents, par ordre de priorité : **Licence créée**,
**Validée, à payer**, **Brouillon**, **Inconnu**. Il n'y a aucun identifiant commun entre HelloAsso
et la FFST : le rapprochement se fait par nom et prénom, sans majuscules ni espaces en trop, comme
dans Sambo Admin.

## 5. Écrire sur le site

Colonne **Actions FFST**, mêmes boutons que Sambo Admin :
- Statut Inconnu : **Faire la demande Pratiquant** ; **Faire la demande Autre rôle** (liste des
  fonctions de la FFST, Valider / Annuler) ; si le genre manque : « Genre absent de HelloAsso :
  Choisir » (Homme / Femme) avant d'envoyer.
- Statut Brouillon : **Supprimer la demande**.
- Pendant l'action : « Le portail FFST est piloté automatiquement : ça peut prendre jusqu'à
  30 secondes » ; puis l'erreur ou l'avertissement sous le bouton.

Une demande pilote un vrai navigateur (Playwright, Chromium), une seule à la fois :
1. relire le site ; refuser si la personne est déjà en brouillon, validée ou licenciée ;
2. chercher l'ancien licencié par nom et prénom : un seul trouvé = renouvellement, coordonnées
   remplacées par celles de HelloAsso (un champ vide garde l'ancienne valeur) ; plusieurs = refus,
   à faire à la main ; aucun = nouvelle demande, où genre, date de naissance et adresse sont
   obligatoires ;
3. pour un rôle autre que Pratiquant, la commune de naissance est cherchée d'après la ville de
   l'adhérent, sinon la commune par défaut de l'école, avec un avertissement ;
4. cocher l'attestation d'assurance, enregistrer, et **vérifier le message « bien enregistrée »**
   du site : sans lui, la demande est déclarée refusée avec le message du site.

Corrections reprises avec leurs tests : apostrophe du nom remplacée par un espace (elle fait
planter le site), ville avec majuscule initiale sans accent, année de naissance sur deux chiffres
corrigée, téléphone mis dans fixe et mobile. La suppression vérifie que la ligne a disparu du
panier, deux tentatives.

Une demande n'est jamais faite automatiquement : toujours sur un bouton. Admins.

## 6. Onglet FFST

Barre du bas, onglet **FFST** : Brouillons (n) | Validées (n) | Licenciés (n). Colonnes : Nom et
prénom, Né(e) le, Nature, Licence n°, puis N° demande ou Demandé le, État. « Lu sur le site de la
FFST à … », bouton Rafraîchir. Sous Brouillons : « Valider le panier et payer les licences se fait
sur le site de la FFST ».

## 7. Données

`ffst_connections` (organisation, identifiant en trois parties, mot de passe chiffré, réglages,
dernier test) ; `ffst_snapshots` (organisation, liste, lignes telles que lues, heure). Aucune
table de licences à nous.

## 8. Risques

| Risque | Parade |
|---|---|
| Le site change : la lecture vise des repères internes de la page (boutons « M32 », champs « A33 ») | message « le site FFST a changé », lien vers le site ; le reste du tableau marche sans la FFST |
| Mauvaise personne : rapprochement par nom et prénom | refus quand deux personnes correspondent ; date de naissance FFST montrée à côté de celle de HelloAsso |
| Demande faite deux fois pendant que Sambo Admin tourne aussi (environ une semaine, Seb, 18 novembre) | relecture avant chaque écriture ; dans Sambo Admin, Rafraîchir avant une demande ; un doublon se voit dans le panier avant de payer |
| Deux connexions simultanées du même compte, mal supportées par le site | une action à la fois ; lectures rares grâce à la copie |
| Refus silencieux du site | vérification du message de confirmation (§5) |
| Aucun accord connu de la FFST pour cet usage automatique | à l'appréciation de Seb ; volume d'un bénévole |
| Un navigateur occupe le serveur 30 secondes | fait par le worker, pas par le serveur principal |

## 9. Technique

Chromium est déjà dans l'image du backend (PDF). Playwright (Python) est à ajouter aux dépendances ;
à vérifier qu'il utilise le Chromium installé sans toucher au Dockerfile, sinon demander à Seb.
Colonne et boutons déclarés côté écran, `memberColumns` du `module.js` (`core.md` §11.1, `modules/helloasso.md` étape 6).

## 10. Étapes (chacune une PR, sur le « vas-y » de Seb)

1. Connexion du club, lecture des trois listes, onglet FFST, colonne Statut FFST.
2. Demandes Pratiquant et Autre rôle, suppression d'un brouillon, choix du genre.

**Fait (étape 1, 18 novembre 2026)** :
- *Connexion* : ligne FFST de Fonctionnalités (`FfstReglages.jsx`), comme HelloAsso : identifiant en
  trois cases et mot de passe (l'œil l'affiche), **Tester la connexion** (« Connexion réussie » et le
  nombre de licenciés), **Enregistrer** (reteste, chiffre le mot de passe, puis lit tout de suite les
  trois listes) ; « Voir » : identifiant, depuis quand, Tester la connexion, Changer les identifiants.
  Pas de « Déconnecter » : décocher la case éteint le module. Routes `GET/PUT /ecoles/{id}/ffst`,
  `POST …/ffst/tester`, `POST …/ffst/retester` (Administrateur principal et Super User).
- *Lecture* (`backend/src/ffst/site.py`) : mêmes requêtes que Sambo Admin, par httpx (pas de
  navigateur) : une connexion par liste, une à la fois (verrou), quelques secondes, faite pendant la
  demande et non par le worker (le navigateur de l'étape 2 ira au worker). Si le site ne répond pas ou
  a changé, rien n'est remplacé : la dernière lecture reste, avec le message et un lien vers le site.
  `GET …/ffst/listes` (la copie), `POST …/ffst/lire` (Rafraîchir), tout admin.
- *Copie* : `ffst_snapshots`, une ligne par liste, remplacées ensemble ; `ffst_connections` (migration
  `d3f5a7c9e1b2`, module éteint dans les écoles existantes, comme HelloAsso). Les réglages de l'école
  (discipline, commune de naissance par défaut, droit à l'image) viennent avec l'étape 2, qui s'en sert.
- *Onglet FFST* (`FfstOnglet.jsx`), admins : Brouillons (n) | Validées (n) | Licenciés (n), « Lu sur le
  site de la FFST à 10 h 52 » (la date si ce n'est pas aujourd'hui), Rafraîchir, colonnes du §6 ; la
  Nature est le texte du site.
- *Statut FFST* : colonne du tableau d'Admin > Élèves (`memberColumns`), pour toute fiche de l'école,
  dès que le site est connecté (saison imposée ou non) ; `GET …/ffst/adherents`. Rapprochement : sans
  accent, majuscule, apostrophe ni espace en trop, « Nom Prénom » de la fiche contre « Nom et Prénom »
  du site. « Rafraîchir » du tableau relit aussi le site.
- *À savoir* : comme pour tout module, une école **créée** après la migration a le module allumé
  (pas de ligne = allumé, `core.md` §9 bis.3) : l'onglet FFST y apparaît pour les admins, avec
  « pas encore connecté ». Non corrigé ici (ce serait un réglage du core).
