# AppBase — Module `helloasso`

Version 1.9 du 18 novembre 2026 (§8.1 : le choix de la saison dans Éditer la saison ; §7.11 : étapes 6 à 10 faites ; §8.5 : étape 11 faite ; §8 : deux façons d'utiliser HelloAsso par saison, paiement par carte avec les clés de l'école ; §7 : adhérents entièrement imposés par HelloAsso, tableau repris de Sambo Admin, impayés, vérification, contact, résiliation). Décisions de Seb des 23, 26 et 27 octobre et du 18 novembre 2026. Repris de Sambo Admin
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
récupère ce que HelloAsso a fait. Seule exception : la résiliation d'une adhésion (§7.7).

## 2. La connexion (Admin › École › Connexions depuis le 18 novembre, `core.md` ; avant, Fonctionnalités)

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
  `member_values`, la formule et les paiements dans `helloasso_registrations` ; l'identifiant HelloAsso de la
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
`frontend/src/modules/helloasso/`), éteint dans les écoles existantes, et éteint par défaut dans toute nouvelle école (Seb, 18 novembre 2026, `core.md` §11.3). Sur sa ligne de
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

**Fait (étape 3, 27 octobre 2026)** : la synchronisation de la saison en cours, toutes les 5 minutes
par le worker `messagerie-relance` (`app/relance_worker.py`, pas de nouveau conteneur) et par le
bouton **Synchroniser maintenant** sous la campagne (Champs, tout admin), qui dit ce qui a changé
(« Synchronisé : 2 nouvelles fiches, 1 fiche complétée »). Les commandes de la campagne
(`/orders?withDetails=true`, toutes les pages) : chaque ligne d'adhésion ou de billet
(`Membership`, `Registration`) est une personne ; annulée ou remboursée, elle est ignorée. Fiche
retrouvée par nom et prénom (sans accents ni majuscules), sinon par email du payeur et prénom
(jamais par le seul email, que partagent les enfants d'un même payeur) ; une fiche non élève du même
nom (un prof) est complétée ; sinon une fiche d'élève est créée avec l'email du payeur. L'email du
payeur est écrit sur la fiche (famille, `core.md` §4.4). Les réponses vont dans les champs de la
campagne (date « 05/11/0017 » corrigée en 2017, comme Sambo Admin) et dans notre champ du même
intitulé caché par elle (la date de naissance donne l'âge). Table `helloasso_registrations` (saison,
identifiant HelloAsso de la ligne et de la commande, fiche, nom, prénom, email du payeur, formule,
montant, code promo, état, date, paiements `[{montant, date, état, moyen, échéance}]`, « plus sur
HelloAsso » quand la ligne disparaît : la fiche reste). Reste pour plus tard : les colonnes Montant
payé / Reste à payer et « Plus sur HelloAsso » dans le tableau des membres, les fichiers (photo
d'identité), « Modifiable sur HelloAsso » dans Profil.

**Fait (étape 4, 27 octobre 2026)** : l'écran Tarifs de la saison (Admin > École > Tarifs) montre, si
la saison a une campagne, « Tarifs de la campagne HelloAsso « X » : ils se modifient sur HelloAsso. »
puis ses formules (`tiers` du formulaire public, sauf les dons : nom, prix ou « Dès … » pour un prix
libre, « En plusieurs fois » / « Tous les mois », description) et ses options (`extraOptions`, à
cocher ou obligatoires), à la place des nôtres, sans rien de modifiable (`seasonPrices` du
module.js, `core.md` §11.1). HelloAsso ne donne pas ses codes promo par l'API : on montre ceux vus
dans les commandes synchronisées, avec leur nombre d'utilisations. Rien n'est écrit vers HelloAsso :
la maquette Tarifs (« publiés sur HelloAsso à la validation ») n'est pas suivie sur ce point,
l'API HelloAsso ne permet pas d'écrire les formules.

## 7. Adhérents entièrement imposés par HelloAsso (Seb, 18 novembre 2026)

But : reprendre dans l'appli, pour Alliance Sambo Combat La Ciotat (enseigne Assofight), l'onglet
Adhérents de Sambo Admin (`silvaplana/test-python`), **à fonctions identiques**, sauf l'Ancienneté
et l'onglet Historique, qui ne sont pas repris. Le mode reste optionnel et vaut pour toute école,
Contretemps comprise. Étude : https://claude.ai/artifact/7HPSBAeGZ5YrE4jahT213a. Maquette validée
par Seb le 18 novembre : https://claude.ai/artifact/4tizDZ6Br2WxGL5MYwSQfy ; les écrans la suivent.

Sambo Admin n'a aucune table d'adhérents : il relit HelloAsso à chaque ouverture. Ici la référence
reste HelloAsso, mais on lit la copie en base faite par la synchronisation (§4) : l'écran s'ouvre
tout de suite et l'adhérent a une fiche pour le reste de l'appli.

### 7.1 Totalement esclave

Une saison qui a une campagne « Imposés par HelloAsso » (§3) n'a pas d'autre source d'adhérents :
- dans Admin > Élèves (« Adhérents » pour ASC), plus de bouton « + », d'import ni de suppression
  d'une fiche d'élève ; le serveur refuse aussi la création ;
- quelqu'un qui paie en espèces ou par chèque est ajouté par l'école **dans HelloAsso** (paiement
  hors ligne) et arrive par la synchronisation ;
- les profs et les administrateurs gardent leur fiche et leur invitation, même sans adhésion ;
  les élèves à l'essai ne sont pas des adhérents ;
- on ne supprime jamais : une adhésion résiliée ou remboursée reste dans le tableau, grisée,
  « Résilié ». La synchronisation, qui ignore aujourd'hui ces lignes, les recopie avec leur état ;
- l'école peut toujours ajouter ses propres champs à côté (§3).
Une école sans le module HelloAsso, ou une saison « Nos champs », ne change en rien.

### 7.2 Le tableau

Admin > Élèves, pour une saison imposée par HelloAsso. Titre « Adhérents (n) » et bouton
**Rafraîchir** (synchronise maintenant, et relit les listes FFST si le module FFST est allumé) ;
recherche « Rechercher un adhérent... » ; filtres par âge : Tous, Juniors (moins de 18 ans),
Seniors, -10, 10-20, 20-30, 30-40, 40-50, 50+. Colonnes, dans cet ordre par défaut :

| Colonne | Contenu | Apportée par |
|---|---|---|
| Nom, Prénom, Email | l'email est celui du payeur | core |
| Montant, Code promo | montant de l'adhésion, code appliqué | HelloAsso |
| Photo | vignette de la photo d'identité, agrandie au toucher ; masquable par le menu ⋮ | HelloAsso |
| Statut HelloAsso | « Validé HelloAsso » (état `Processed`), « Résilié » ; jamais le mot anglais | HelloAsso |
| Vérification | « OK » ou « À vérifier » (§7.5) | HelloAsso |
| Statut FFST, Actions FFST | `modules/ffst.md` | FFST |
| Contact | « ✉ Mail », « 💬 SMS » avec le nombre déjà envoyé (§7.6) | HelloAsso |
| Adhésion | « Résilier » ou « Résiliée » (§7.7) ; droit Accès au Financier | HelloAsso |

Toucher une ligne ouvre la fiche (§7.3). Menu ⋮ : « Statistiques des adhérents de la saison »
(§7.8), « Vérifier les adhérents », « Masquer / Afficher les photos ». L'école peut toujours
masquer ou réordonner les colonnes (« Affichage dans Admin », `core.md` §4.3).

Ces colonnes et boutons sont déclarés par les modules, côté écran (`memberColumns` de `module.js`,
`core.md` §11.1 ; étape 6).

Écarts avec Sambo Admin, validés par Seb le 18 novembre : jamais « IA » à l'écran (« Vérification »,
« Vérifier les adhérents ») ; « Processed » devient « Validé HelloAsso » ; texte ≥ 17 px et boutons
≥ 48 px ; la navigation est celle de l'appli (Admin > Adhérents, onglet FFST en barre du bas,
« Impayés HelloAsso » à côté d'Adhérents) ; les rôles remplacent les deux mots de passe (le mot de
passe « comptes » = droit Accès au Financier).

### 7.3 La fiche

Identité et photo, adhésion (formule, montant, code promo, statut HelloAsso, statut FFST),
vérification du dossier (raisons, « Valider le dossier »), documents déposés (photo d'origine,
certificat médical, autorisation parentale), réponses au formulaire (« Modifiable sur HelloAsso »),
payeur, paiements et échéances, mails envoyés et SMS préparés.

La photo et les documents sont protégés par le jeton HelloAsso : le serveur les relaie. La
vignette est gardée sur le disque (elle ne change pas) ; **les documents ne sont jamais
enregistrés**, ils sont lus chez HelloAsso à la demande. Un PDF déposé à la place d'une photo
donne sa première page en vignette.

### 7.4 Impayés HelloAsso

Admin > **À encaisser** (ex-« Impayés HelloAsso », puis « Paiements HelloAsso » ; maquette validée par
Seb le 18 novembre 2026 : https://claude.ai/artifact/RJr31x9iHp1694Wx3nZ4CA), visible si le module est
allumé. Ce qui compte : l'argent qui doit encore arriver sur le compte. Pastille rouge = nombre
d'échéances dépassées sans paiement (`badge` des `adminTabs`).

- En haut, « À encaisser », « Rafraîchir » (synchronise puis relit) et un seul chiffre, « Doit encore
  arriver sur le compte » = partie 1 + partie 2.
- **1. À payer à HelloAsso** (et son total) : toutes les échéances que les adhérents doivent encore
  payer, ni payées ni remboursées, des adhésions non résiliées (`upcoming` de
  `GET …/helloasso/impayes`). Chaque ligne : date, Nom Prénom, nom de l'échéance sur HelloAsso
  (« Paiement 2 », `installmentNumber`), somme. Une échéance dont la date est passée sans paiement
  (refusée, ou jamais tentée) est un impayé : en rouge, en tête, avec au-dessus « n échéances
  dépassées sans paiement : total ». Les autres, rangées par mois avec le total du mois.
- **2. HelloAsso doit verser au compte** (et son total) : « Virement en route » et « Gardé par
  HelloAsso, versé vers le 10 <mois> », repris des statistiques de la saison (§7.8, `cash.in_transit`
  et `cash.held`, la banque disant quand un virement est arrivé).
- Lu dans `helloasso_registrations` (paiements déjà recopiés), rien de plus en base. La liste par
  adhérent de Sambo Admin (Email, Total, Impayé) n'est plus montrée ; la route la donne encore
  (`members`).

### 7.5 Vérification des dossiers

Reprise de `helloasso/verification.py` de Sambo Admin. Pour chaque adhérent : contrôles sans
modèle (document manquant, date de naissance illisible, fichier illisible), puis un seul appel au
modèle avec la photo, le certificat médical, l'autorisation parentale (mineurs) et les réponses.
Résultat gardé en base : OK, problème (raisons) ou erreur, validé à la main, coût cumulé. Un
dossier OK n'est plus revérifié.
- Un nouvel adhérent est vérifié dès sa détection par la synchronisation ; en cas de problème,
  mail au contact de l'école. Notification push « Nouvel adhérent » et pastille sur l'onglet.
- Menu « Vérifier les adhérents » (Accès au Financier) : relance pour ceux qui ne sont pas OK,
  coût cumulé affiché, rapport par mail.
- « Valider le dossier » à la main, dans la fiche.

**Décision de Seb (18 novembre 2026)** : comme Sambo Admin, le certificat médical est envoyé au
modèle pour être contrôlé, et rien n'est enregistré. C'est la seule exception à la règle « l'assistant
ne voit jamais la santé des membres » : elle ne vaut que pour cette vérification, jamais pour
l'assistant. La vérification est **éteinte par défaut** ; chaque école l'allume (réglage du module,
Administrateur principal).

### 7.6 Contact

- **Mail** : destinataire (email du payeur), copie, objet, message, messages préenregistrés avec
  `{prénom}` et `{nom}`, journal des mails envoyés (envoyé ou échec), compteur sur le bouton.
- **SMS** : préparé dans l'appli SMS du téléphone ; l'appli sait qu'il a été préparé, pas qu'il est
  parti. Messages préenregistrés, journal, compteur. Pas de bouton SMS sur ordinateur.
L'envoi passe par le service email du core, avec réponse vers l'adresse de l'école.

### 7.7 Résilier une adhésion

Seule action qui écrit chez HelloAsso (`POST /v5/orders/{id}/cancel`, droit RefundManagement de
la clé). Elle porte sur **toute la commande** (une fratrie entière), annule les échéances à venir,
ne rembourse rien, et ne se défait pas. Écran repris de Sambo Admin : aperçu obligatoire (qui est
dans la commande, ce qui est déjà encaissé et ne sera pas remboursé, combien d'échéances seront
annulées), puis « Résilier l'adhésion » / « Résilier les n adhésions ». Ici la règle « Annuler
plutôt que confirmer » ne s'applique pas : HelloAsso ne revient pas en arrière. Droit Accès au
Financier.

### 7.8 Statistiques de la saison

Majeurs et mineurs, prix moyen, encaissements arrivés et à venir mois par mois, solde actuel,
projection de fin de saison. Dépend des comptes de l'école dans le Financier (versements
HelloAsso vus à la banque) : dernière étape.

Seb, 18 novembre 2026 (maquette « Adhérents ASC » validée) : on la code comme la maquette,
projection comprise, même si elle recoupe le Prévisionnel du Financier ; on verra plus tard
laquelle on garde (a priori le Prévisionnel). Détail dans « Fait (étape 10) » (§7.11).

### 7.9 Données

`helloasso_registrations` gagne l'état résilié. Nouvelles tables, toutes par organisation et
rangées sous l'identifiant HelloAsso de l'adhésion : `helloasso_checks` (vérification),
`helloasso_mails`, `helloasso_sms`, `helloasso_templates`. Reprise du journal de Sambo Admin par
une commande `python -m app.<commande>` que Seb lance sur le VPS.

### 7.10 Bascule et risques

Sambo Admin reste en production pendant la reprise et s'arrête sur demande de Seb, une fois chaque
fonction de l'inventaire (étude, partie 6) retrouvée sur ASC La Ciotat. Pendant ce temps :
notifications et vérification automatique allumées dans l'appli seulement quand Sambo Admin les
éteint (sinon tout est fait deux fois) ; première synchronisation d'ASC avec un compte rendu avant
de l'appliquer (fiches déjà créées à la main, doublons à fusionner) ; tests « Le Beausset
inchangé » à chaque PR.

### 7.11 Étapes (chacune une PR, sur le « vas-y » de Seb)

5. Totalement esclave : verrou de création, adhésions résiliées, colonnes Montant, Code promo,
   Photo, Statut HelloAsso, filtres par âge, fiche.
6. Colonnes et boutons déclarés par les modules (`core.md` §11.1).
7. Impayés HelloAsso.
8. Contact (mail, SMS, messages préenregistrés) et Résilier.
9. Vérification des dossiers, notification « Nouvel adhérent ».
10. Statistiques de la saison.
Le module FFST (`modules/ffst.md`) s'intercale après l'étape 6.

**Fait (étape 5, 18 novembre 2026)** :
- *Verrou* : `Eleves.locks` (core), que le module remplit en se montant
  (`helloasso/members.py`, `lock`) : saison en cours avec une campagne et module allumé ⇒ refus
  (409, message en clair) de créer, importer (aperçu et validation) ou supprimer une fiche d'élève,
  par l'écran, l'inscription OCR / web ou l'assistant. La synchronisation crée ses fiches malgré le
  verrou (`Eleves.create(..., external=True)`). « Nos champs » ou module éteint rouvrent tout. Les
  profs, admins et la fusion de deux fiches ne changent pas.
- *Résiliées* : la synchronisation recopie aussi les lignes `Canceled`, `Refunded`, `Refunding`,
  `Deleted`, `Abandoned` (avant : ignorées) avec leur état ; une fiche est créée si besoin, ses
  réponses ne sont pas écrites (une adhésion active de la même personne fait foi).
  `helloasso_registrations` gagne `answers` (réponses telles que HelloAsso les donne ; pour un
  fichier, son adresse chez HelloAsso) et `payer_name` (migration `ab41da4bb0f7`, remplies au passage
  suivant du worker).
- *Tableau* : le module déclare côté écran `memberList` (module.js, `adherents.jsx`) : ses colonnes
  Montant, Code promo, Photo, Statut HelloAsso (« Validé HelloAsso », « Résilié », jamais le mot
  anglais), proposées dans « Affichage dans Admin » (nature Calculé, HelloAsso) ; sans affichage
  enregistré, ordre de Sambo Admin : Adhérent, Email, Montant, Code promo, Photo, Statut HelloAsso,
  le reste masqué. Le tableau d'Admin > Élèves, quand la saison affichée a une campagne : titre
  « Adhérents (n) » (adhésions HelloAsso non résiliées seulement : une fiche sans adhésion, un prof par exemple, est listée en dernier sans être comptée), « Rafraîchir » (synchronise, saison en cours),
  « Rechercher un adhérent... » (nom, prénom, email), ordre de Sambo Admin (celui de HelloAsso :
  la commande la plus récente d'abord, Seb 18 novembre 2026 ; `memberList.ordre`), filtres par âge, ligne résiliée grisée et nom
  barré, pas de « + », d'import, de poubelle ni d'Inscription OCR / web ; menu ⋮ « Masquer /
  Afficher les photos » (par appareil, comme Sambo Admin). Route
  `GET /ecoles/{id}/helloasso/adherents`.
- *Fiche* : bloc du module sous l'identité : photo, Adhésion, Documents déposés sur HelloAsso,
  Réponses au formulaire (« Modifiable sur HelloAsso. »), Payeur, Paiements. Photo par
  `…/adherents/{fiche}/photo?size=` : vignette carrée gardée sur le disque
  (`HELLOASSO_PHOTOS_DIR`, défaut `./data/helloasso-photos`), première page pour un PDF ; documents
  par `…/adherents/{fiche}/fichiers/{n}`, lus chez HelloAsso à chaque demande, jamais enregistrés
  (`Cache-Control: no-store`). Le serveur ne relaie que les adresses `https://docs.helloasso.com/
  customFieldsAnswer/…` gardées en base, jamais une adresse envoyée par le navigateur. Tout admin.
- *Écarts* : Nom et Prénom restent dans une seule colonne « Adhérent » (colonne du core) ; Vérification,
  Statut FFST, Actions FFST, Contact, Adhésion, les messages envoyés et le menu « Statistiques » /
  « Vérifier les adhérents » viennent avec les étapes 6 à 10. Le branchement `memberList` est le
  début de l'étape 6 côté écran.

**Fait (étape 6, 18 novembre 2026)** : les colonnes et boutons des modules dans le tableau d'Admin >
Élèves (`core.md` §11.1). Décision : ils se déclarent côté écran, `memberColumns` du `module.js`
(`charger`, `colonnes`, `rafraichir`), et non dans `module.py` : leurs valeurs viennent des routes
du module, avec leurs droits ; le core n'a ni table ni route de plus. `app/modules.js`
(`colonnesModules`, `rafraichirColonnes`) les rassemble pour le tableau, l'appui long et
« Affichage dans Admin » ; une cellule de nature Bouton reçoit `relire` pour relire le tableau
après son action ; « Rafraîchir » appelle aussi le `rafraichir` de chaque module. HelloAsso y
range ses quatre colonnes (Montant, Code promo, Photo, Statut HelloAsso) ; `memberList` garde le
verrou, le compte, les filtres, le menu et la fiche. Sans affichage enregistré d'une saison imposée,
les colonnes d'un autre module (Statut FFST, Actions FFST) s'affichent après l'ordre de Sambo Admin.
Rien ne change à l'écran tant qu'aucun autre module ne déclare de colonne.

**Fait (étape 7, 18 novembre 2026)** : Admin > **Impayés HelloAsso**, sous-onglet après Cours quand
le module est allumé (`adminTabs` du `module.js`, `core.md` §11.1 : un module peut ajouter un
sous-onglet d'Admin). Titre « Impayés HelloAsso (n) », « Rafraîchir » (synchronise puis relit) ;
colonnes Nom, Prénom, Email (du payeur), Total, Impayé (en rouge), Échéances refusées (dates) ;
« Aucun impayé. » ou « Pas de campagne HelloAsso pour cette saison. ». Une ligne par adhésion de la
saison affichée (résiliées comprises) dont au moins un paiement est `Refused`, `Error`, `Canceled`,
`Abandoned`, `Deleted` ou `Inconsistent` ; Impayé = somme de ces paiements, Total = montant de
l'adhésion. Route `GET /ecoles/{id}/helloasso/impayes` (tout admin), lue dans
`helloasso_registrations.payments` : rien de plus en base.

**Fait (étape 8, 18 novembre 2026)** : deux colonnes de nature Bouton dans le tableau (`memberColumns`),
après Statut HelloAsso, sur les lignes qui ont une adhésion.
- **Contact** : « ✉ Mail » et « 💬 SMS » avec le nombre déjà envoyé (ou préparé). « 💬 SMS » seulement
  sur un écran tactile et si le formulaire HelloAsso a donné un téléphone (réponse de nature
  téléphone, ou question dont le libellé contient « téléphone » / « phone »).
  « Mail à Prénom Nom » : Message préenregistré (Aucun + la liste), Objet, Message, « n mails déjà
  envoyés à cette personne. » ou « Premier mail à cette personne. », Annuler / **Envoyer**, puis
  « Mail envoyé ». Le mail part à l'email du payeur par `core.mail_ecole` (`core.md` §11.1) :
  expéditeur de l'enseigne au nom de l'école, l'école en copie et en réponse ; un échec est noté au
  journal avec sa raison et affiché.
  « SMS à Prénom Nom » : Message préenregistré, Message, Annuler / **Ouvrir mes SMS** (ouvre
  `sms:<téléphone>?body=…`), puis « SMS préparé dans ton téléphone ».
  Messages préenregistrés : « Garder ce message » (le texte tapé, avec `{prénom}` et `{nom}`
  remplacés au choix) et « Retirer ce message préenregistré », par école et par nature (mail, SMS).
- **Adhésion** : « Résilier » (rouge, droit Accès au Financier) ou « Résiliée ». Écran « Résilier
  l'adhésion » : la commande entière (chaque adhérent et son montant), ce qui est déjà encaissé et ne
  sera pas remboursé, les échéances à venir annulées, « Cette action est définitive » ; **Annuler**
  est le bouton principal, « Résilier l'adhésion » / « Résilier les n adhésions » en rouge. Après
  l'appel à HelloAsso, les adhésions de la commande passent à l'état résilié sans attendre la
  synchronisation. Une clé sans le droit de remboursement : message qui demande de le cocher sur
  HelloAsso.
- La fiche gagne la rubrique **Messages envoyés** (date, mail ou SMS préparé, objet ; « Pas parti :
  … » pour un échec).
- Routes : `POST …/helloasso/adherents/{fiche}/mail`, `…/sms` (→ téléphone, noté au journal),
  `GET …/resiliation` (aperçu), `POST …/resilier` (403 sans Accès au Financier, 409 déjà résiliée),
  `GET|POST /ecoles/{id}/helloasso/messages`, `DELETE …/messages/{id}`. Tables `helloasso_mails`,
  `helloasso_sms`, `helloasso_templates` (§7.9), rangées sous l'identifiant HelloAsso de l'adhésion
  pour survivre à une fusion de fiches. La reprise du journal de Sambo Admin reste à faire
  (commande sur le VPS).

**Fait (étape 9, 18 novembre 2026)** : vérification des dossiers et « Nouvel adhérent », repris de
`helloasso/verification.py` de Sambo Admin.
- **Réglages** (Fonctionnalités > HelloAsso > Voir, bloc « Nouveaux adhérents », Administrateur
  principal), deux cases éteintes par défaut (§7.10) : « Prévenir les administrateurs à chaque
  nouvel adhérent » et « Vérifier le dossier de chaque adhérent : photo, certificat médical,
  autorisation parentale ». Colonnes `check_files` et `notify_new` de `org_helloasso`.
- **Nouvel adhérent** : une adhésion vue pour la première fois par la synchronisation (worker toutes
  les 5 minutes ou « Rafraîchir »), pas résiliée. Notification push « Nouvel adhérent » (« n nouveaux
  adhérents ») aux admins de l'école, avec les noms ; dossier vérifié (en arrière-plan dans l'appli,
  directement dans le worker) ; s'il n'est pas OK, mail à l'adresse de l'école « Nouvel adhérent à
  vérifier : Prénom Nom » avec les raisons. Branché par `Sync.on_new`.
- **Vérification d'un dossier** : contrôles sans modèle (date de naissance absente ou illisible,
  photo ou certificat manquant, autorisation parentale manquante pour un mineur, fichier illisible ou
  indisponible), puis un seul appel au modèle (Sonnet 5.5, consignes de Sambo Admin sans le nom du
  club en dur) avec les documents en images (2 pages au plus d'un PDF) et les réponses. Résultat
  dans `helloasso_checks` (par organisation et identifiant HelloAsso de l'adhésion) : ok, problem
  (raisons) ou error (l'appel a échoué), coût cumulé en dollars. Rien des documents n'est gardé.
- **Colonne Vérification** (seulement quand la vérification est allumée), après Statut HelloAsso :
  « OK » en vert ou « À vérifier » (lien), vide si jamais vérifié. « À vérifier » ouvre « Dossier de
  Prénom Nom » : les raisons, les documents déposés, « Écrire à l'adhérent » (l'écran Mail) et
  **Valider le dossier**. Valider : « Dossier validé » avec Annuler 10 s ; le dossier compte OK et
  n'est plus revérifié, les raisons restent pour l'Annuler.
- **Fiche** : rubrique « Vérification du dossier » après Adhésion (OK, ou les raisons et « Valider
  le dossier »).
- **⋮ > Vérifier les adhérents** (vérification allumée) : « n dossiers à vérifier. Les dossiers déjà
  OK ne sont pas revérifiés. », « Coût cumulé des vérifications de dossiers : x € », Annuler /
  **Relancer la vérification** (Accès au Financier). Les dossiers pas OK de la saison en cours
  (résiliées exclues) sont revérifiés en arrière-plan, puis le rapport part par mail à l'adresse de
  l'école. « Vérification relancée, le rapport arrive par mail ».
- Routes : `GET|PUT /ecoles/{id}/helloasso/reglages` (Administrateur principal),
  `GET|POST /ecoles/{id}/helloasso/verification`, `POST|DELETE …/adherents/{fiche}/valider`
  (tout admin). Le tableau gagne `checks_on` et, par ligne, `check` {ok, issues} ; la fiche, `check`.
- Pas encore fait : la pastille sur l'onglet (un module ne peut pas encore ajouter de pastille à un
  onglet du core : point de branchement à proposer).

**Fait (étape 10, 18 novembre 2026)** : statistiques de la saison, repris de Sambo Admin
(`helloasso/summary.py`, `seasons/projection.py`), sans modèle : chaque chiffre s'explique.
- **⋮ > Statistiques des adhérents de la saison** (tout admin, saison affichée) : « Statistiques de
  la saison 2026-2027 » ; Majeurs / Mineurs / Prix moyen (âge tiré de la réponse « date de
  naissance ») ; « n adhérents, x € au total (résiliées non comptées). ».
- *Solde actuel* : un solde par compte du Financier, « au » jour connu.
- *Encaissements des adhésions*, dépliables : « Déjà arrivé sur le compte courant » (« Reçu le …
  (versement HelloAsso du …), n paiements ») et « Reste à encaisser » : « Versement en cours
  HelloAsso → compte courant », « Payé sur HelloAsso, versé vers le 10 du mois prochain »,
  « Échéances de <mois> ». C'est la banque qui dit si un versement est arrivé (virement HelloAsso
  dont le libellé finit par le jour du versement, lu dans les comptes du Financier) ; sans comptes,
  l'état donné par HelloAsso. Un paiement hors HelloAsso (chèque, espèces) n'y est pas.
- *Projection de fin de saison* : « Solde projeté au <fin de saison> » = solde actuel + reste à
  encaisser − salaires et cotisations jusqu'à la fin de la saison − licences FFST encore à payer.
  Salaires, URSSAF et mutuelle (catégories du Financier) : montant des 3 derniers mois s'ils sont
  identiques, sinon moyenne des 6 derniers mois complets ; du mois en cours s'il n'est pas encore
  payé. Licences : (adhérents + 1 coach − licenciés de la dernière lecture du site FFST) × 24 €,
  comme Sambo Admin ; ligne absente si la FFST est éteinte ou jamais lue. « Chiffre optimiste : il
  ne compte ni les autres dépenses (matériel, frais bancaires…), ni les adhésions qui peuvent
  encore arriver. »
- Soldes et projection seulement avec l'Accès au Financier et le Financier allumé ; sinon absents.
- *Lien* : les comptes et les licences appartiennent à d'autres modules. Le module HelloAsso les
  attend dans `core.helloasso_stats` (`Sources` : `ledger`, `licences`, vides par défaut) ;
  Contretemps les remplit dans `backend/src/helloasso_contretemps/` (lit le Financier et la copie
  de la FFST), qui déclare le module à la place de `helloasso.module` dans `app/modules.py`.
- La synchronisation garde désormais, par paiement, `cash_out_state` et `cash_out_date` de
  HelloAsso (dans le JSON `payments`, sans migration ; remplis au passage suivant du worker).
- Route : `GET /ecoles/{id}/helloasso/statistiques`.

## 8. Deux façons d'utiliser HelloAsso, par saison (Seb, 18 novembre 2026)

La connexion (§2) se fait **une seule fois pour l'association**. Ensuite **chaque saison** choisit
comment elle s'en sert. Maquette du paramétrage : https://claude.ai/artifact/N9NhspShBZ4S1F7ZPCa7h2.

### 8.1 Les trois choix

Seb, 18 novembre 2026 : une campagne par saison, donc le choix se fait **dans la saison** :
Admin › École › Saisons › **Éditer la saison**, sous les dates (saison en cours, HelloAsso
connecté, administrateur principal et Super User). La connexion (Connexions › HelloAsso › Voir)
ne garde que les clés, le résumé de la saison et le rappel « N'oubliez pas de brancher chaque
saison à sa campagne HelloAsso dans « Saisons » ». Point de branchement côté écran :
`seasonEditor` du module.js (bloc sous les dates, `SaisonsSection.jsx`). Pas encore fait :
choisir à l'avance pour une saison future (aujourd'hui, la saison en cours seulement). Trois
cartes, une seule cochée :
1. **HelloAsso fait tout** : les gens s'inscrivent et paient sur HelloAsso. On choisit la campagne
   (§3) ; les adhérents sont recopiés et verrouillés (§7). C'est le choix « Imposés par HelloAsso »
   de l'écran Champs, qui reste et dit la même chose.
2. **L'appli fait tout, HelloAsso encaisse** : les gens s'inscrivent dans l'appli, l'école garde
   ses champs, ses tarifs et crée ses adhérents librement. HelloAsso ne sert qu'à payer par carte,
   élève par élève. Pas de campagne : chaque paiement arrive sur le compte HelloAsso de
   l'association. Chèque, espèces et virement restent possibles.
3. **Sans HelloAsso** : rien ne passe par HelloAsso pour cette saison.

Le choix vaut pour une saison et se refait à la suivante. Quitter le choix 1 retire la campagne
(Annuler 10 s), les réponses déjà recopiées restent. Administrateur principal et Super User.

### 8.2 Le paiement par carte avec les clés de l'école (choix 2)

Aujourd'hui le paiement en ligne (`inscriptions/helloasso.py`, Checkout HelloAsso) lit ses clés
dans les variables du serveur (`HELLOASSO_CLIENT_ID`, `HELLOASSO_CLIENT_SECRET`,
`HELLOASSO_ORGANIZATION_SLUG`) : une seule association pour tout le serveur. Désormais :
- une saison au choix 2 paie avec la connexion de son école (`org_helloasso` : identifiant client,
  clé secrète déchiffrée, slug de l'association) ;
- une école sans connexion garde le comportement d'aujourd'hui (variables du serveur) : rien ne
  change pour Contretemps tant qu'elle n'a pas choisi ;
- la vérification d'un paiement ne change pas : on redemande toujours à HelloAsso l'état du
  paiement, jamais le seul retour du navigateur.

### 8.3 Données

`season_helloasso` gagne le choix de la saison (`mode` : `master` ou `payment`) ; au choix 2 la
ligne n'a pas de campagne (colonnes du formulaire vides). Pas de ligne = sans HelloAsso. Une
migration : les lignes existantes passent à `master`.

### 8.4 Ce qui n'est pas fait ici

Le **formulaire d'inscription de l'appli** : celui qui existe est fait pour l'école de danse
Contretemps (`SPEC-inscription.md`). Le rendre propre à chaque association est une étude à part
(Seb, 18 novembre : « on verra après »). Tant qu'elle n'est pas faite, le choix 2 ne sert que là
où ce parcours d'inscription existe.

### 8.5 Étape (une PR, sur le « vas-y » de Seb)

11. Choix de la saison (écran de la maquette) et paiement par carte avec les clés de l'école.

**Fait (étape 11, 18 novembre 2026)** :
- `season_helloasso.mode` (`master` / `payment`, migration `c1b18c1cfaa9`, les lignes existantes
  passent à `master`). `Campaigns.current` ne rend une campagne qu'au choix 1 : le verrou (§7), les
  tarifs et la synchronisation ignorent une saison au choix 2. `Campaigns.set_payment` passe une
  saison au choix 2 (la campagne est retirée, les réponses restent) ou la retire (choix 3).
- Routes `GET /ecoles/{id}/helloasso/saison` (admin : choix, nom de la saison, campagne) et `PUT`
  (`payment` ou `none`, Administrateur principal et Super User, saison en cours, connexion requise) ;
  le choix 1 se fait en choisissant la campagne (route existante).
- Paiement par carte : `inscriptions/helloasso.py` garde un jeton par identifiant client et prend
  des clés optionnelles (`SchoolKeys`) ; `HelloAsso.school_keys` est une liste de fonctions que le
  module remplit au montage (`helloasso/payment.py` : clés de `org_helloasso` si la saison est au
  choix 2), sans que `inscriptions` connaisse le module. Sans réponse : variables du serveur, comme
  avant (Contretemps et Le Beausset inchangés).
- Écran (depuis le 18 novembre 2026, §8.1) : Saisons › Éditer la saison, bloc
  `HelloAssoSaison.jsx`, trois cartes de la maquette ; au
  choix 1, la campagne se choisit dans la carte, puis « Synchroniser maintenant ».
