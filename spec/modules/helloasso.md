# AppBase — Module `helloasso`

Version 1.0 du 27 octobre 2026. Décisions de Seb des 23, 26 et 27 octobre 2026. Repris de Sambo Admin
(`silvaplana/test-python`, `backend/src/helloasso/`), qui lit HelloAsso en direct sans base ; ici on
recopie en base et on synchronise. Maquette de la connexion :
https://claude.ai/artifact/FhTWcRKXpVfdf9toaTSeXS. Socle : `spec/core.md` §4.3 et §9.3.

## 1. Ce que fait le module

Une organisation qui encaisse ses adhésions sur HelloAsso branche l'appli dessus :
1. **la connexion**, une fois pour l'organisation ;
2. pour une saison, **la campagne** (formulaire HelloAsso d'adhésion ou d'événement) qui impose
   les champs de la fiche et les tarifs ;
3. **la synchronisation** : les inscrits de la campagne deviennent des membres de la saison, avec
   leur formule, leurs options, leurs codes et leurs paiements.

Le module ne crée rien sur HelloAsso : les membres s'inscrivent et paient sur HelloAsso, on
récupère ce que HelloAsso a fait.

## 2. La connexion (Admin > École > Fonctionnalités)

- Case **HelloAsso** dans Personnalisation > Fonctionnalités ; cochée, la ligne montre « Connecter ».
- Écran **Connecter** : trois lignes de guide (ouvrir HelloAsso > Mon association > Intégrations et
  API, créer des identifiants, les coller ici), champs **Identifiant client** et **Clé secrète**
  (œil pour l'afficher), bouton **Tester la connexion** : le serveur demande un jeton à
  `https://api.helloasso.com/oauth2/token` (client credentials ; jeton ~30 min, renouvelé par
  refresh ou redemandé), puis lit l'association et ses formulaires ; résultat : « Connecté à
  <association>, N formulaires » ou l'erreur en clair. **Enregistrer**. Sandbox
  (`api.helloasso-sandbox.com`) par variable d'environnement, pour les tests.
- Connectée : écran « Connecté à <association> », « Tester à nouveau », « Changer les clés »,
  « Déconnecter » avec Annuler 10 s. Déconnecter ne touche ni aux membres ni aux paiements déjà
  recopiés.
- La clé secrète est chiffrée en base (`org_helloasso` : organisation, identifiant client, clé
  chiffrée, nom de l'association, date du dernier test, dernier résultat). Jamais dans le dépôt.
- Administrateur principal et Super User seulement.

## 3. La campagne d'une saison

- Étape **Membres** de la création de saison, et Admin > Élèves > ⋯ > Champs : si la connexion
  existe, choix **Imposés par HelloAsso** et liste des formulaires de l'association (nom, nature,
  état). Sans connexion, le choix n'apparaît pas.
- Campagne choisie :
  - **les champs** de la fiche sont ceux du formulaire : les questions HelloAsso
    (`customFields` : « Genre (H/F) », « date de naissance », « Adresse », « code postal », « Ville »,
    « Numéro de téléphone », « photo d'identité »… selon la campagne) plus nom, prénom, email et
    email du payeur (celui de la commande). Verrouillés, marqués « Calculé par HelloAsso », non
    supprimables ; l'organisation peut seulement ajouter ses propres champs à côté (saisis dans
    l'appli, jamais envoyés à HelloAsso) ;
  - **les tarifs** sont ceux de HelloAsso (`core.md` §9.3) : formules (`tiers`), options, codes
    promo, paiement en plusieurs fois, en lecture seule dans l'écran Tarifs de la saison ;
  - le **formulaire d'inscription** est celui de HelloAsso : l'appli montre son lien (bouton
    « S'inscrire sur HelloAsso » sur la page publique et dans les mails) et rien d'autre.
- Changer de campagne en cours de saison : possible, les membres déjà recopiés restent ; les champs
  de l'ancienne campagne restent lisibles.
- `season_helloasso` : saison, identifiant du formulaire, nature (`Membership`, `Event`…), nom,
  date de la dernière synchronisation.

## 4. La synchronisation

- **Quoi** : chaque commande (`orders` / `items`) de la campagne : nom, prénom, email, email du
  payeur, réponses aux questions, formule (`tierName`), options, code promo appliqué (`discount`),
  montant, échéances (`installments`, payées ou à venir), date.
- **Quand** : toutes les 5 minutes par le worker (comme Sambo Admin), et par le bouton
  « Synchroniser maintenant » de l'écran Tarifs ou de la liste des membres. Webhook HelloAsso plus
  tard, s'il devient fiable.
- **Comment** : une commande = une fiche de la saison (`core.md` §4.1 : complétée si la personne
  existe déjà par nom, prénom ou email, créée sinon) ; les champs HelloAsso sont écrits dans
  `member_values`, la formule et les paiements dans `member_plan` ; l'identifiant HelloAsso de la
  commande est gardé pour ne rien recopier deux fois. Une personne retirée côté HelloAsso n'est pas
  supprimée : marquée « Plus sur HelloAsso », l'admin décide.
- Ce que l'appli calcule ensuite est à elle : famille (email du payeur), groupes (un champ
  « Groupe » ajouté côté appli, ou un produit relié à un groupe), colonnes d'Admin (Montant payé,
  Reste à payer), relances. Rien n'est renvoyé vers HelloAsso.
- Les paiements HelloAsso sont la source du module Paiement pour cette saison ; aucun encaissement
  dans l'appli pour une saison sur HelloAsso.

## 5. Droits et écrans

- Connexion et choix de campagne : Administrateur principal et Super User. Synchroniser : tout admin.
- Les membres voient leurs réponses dans Profil (lecture seule, « Modifiable sur HelloAsso »).
- Aucune action de l'assistant n'écrit vers HelloAsso ; il peut lancer la synchronisation et lire
  les colonnes.

## 6. Aujourd'hui et étapes

Rien n'est codé dans Contretemps ; Contretemps encaisse par son propre parcours d'inscription
(`SPEC-inscription.md`, `inscriptions/helloasso.py` pour le paiement seulement). Étapes, chacune
une PR sur le « vas-y » de Seb, après les groupes et les champs des membres (`core.md` §13) :
1. connexion de l'organisation (écran, test, clés chiffrées) ;
2. campagne d'une saison et champs imposés ;
3. synchronisation des membres et des paiements ;
4. tarifs HelloAsso en lecture seule dans l'écran Tarifs.

**Fait (étape 1, 27 octobre 2026)** : module `helloasso` (`backend/src/helloasso/`,
`frontend/src/modules/helloasso/`), éteint dans les écoles existantes. Sur sa ligne de
Fonctionnalités (`settings` du module.js, `core.md` §11.1) : « Pas encore connecté » / « Connecté à
<association> », lien « Connecter » ou « Voir » ; cocher la case sans connexion ouvre l'écran des
clés. Tester demande un jeton, lit `/v5/users/me/organizations` (l'association reliée aux clés) et
ses formulaires d'adhésion ; Enregistrer reteste puis garde les clés. Table `org_helloasso`
(identifiant client, clé secrète chiffrée par Fernet avec une clé tirée du secret du serveur
`SECRET_JETONS` / fichier `secret_jetons` du volume, association, slug, actif, dernier test).
Déconnecter éteint la connexion et le module, Annuler 10 s les rallume. La sauvegarde technique ne
contient pas les clés : après une restauration sur un autre serveur, on les recolle. Sandbox :
`HELLOASSO_SANDBOX=1`.

**Fait (étape 2, 27 octobre 2026)** : en tête de « La fiche d'un membre » (Admin > Élèves > ⋯ >
Champs), si HelloAsso est connecté : **Nos champs** / **Imposés par HelloAsso** et la liste des
formulaires d'adhésion et d'événement de l'association (`memberFields` du module.js, `core.md`
§11.1). Choisir une campagne lit ses questions (`/forms/{nature}/{formulaire}/public`, `customFields`
de toutes les formules, sans doublon) et les met sur la fiche de la saison, en tête, marquées
« Calculé par HelloAsso » (`member_fields.source = "helloasso"`, `source_key` = l'identifiant de la
question) ; un champ à nous du même intitulé est caché. Changer de campagne garde les questions
communes (même identifiant) et retire les autres, réponses gardées ; « Nos champs » retire la
campagne (Annuler 10 s la remet). Choisir : Administrateur principal et Super User, saison en
cours ; les autres admins voient la campagne sans la changer. Nom, prénom, emails et email du payeur
sont les champs du socle. Table `season_helloasso` (saison, nature, identifiant et nom du formulaire,
date du choix, dernière synchronisation). Reste pour plus tard : le choix à l'étape Membres de la
création de saison (aujourd'hui, on crée la saison puis on choisit la campagne dans Champs).
