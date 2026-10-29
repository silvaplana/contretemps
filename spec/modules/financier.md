# AppBase — Module `finances` (onglet Financier)

Version 0.8, 29 octobre 2026 (§8 : dossiers de la trésorière Achats / Honoraires / Notes de frais / Ventes ; §8.3 bis : Virements, machine à états). Statut : **décision de Seb, 20 octobre** : reprendre tel quel le
Financier de Sambo Admin (dépôt `test-python`) dans Contretemps, sous-module par sous-module, et
améliorer ensuite ; AppBase sera tiré de Contretemps.

Écrit comme un module AppBase (rien de propre à la danse) ; ce qui ne vaut que pour Contretemps est
marqué *(Contretemps)*. Les notes de frais ont leur propre spec (`notes-de-frais.md`) et vivent dans
le même onglet.

---

## 1. Objectif

Donner au trésorier, dans l'appli, ce qu'il fait aujourd'hui à la main ou dans Sambo Admin : voir
les comptes de l'organisation, faire le bilan de la saison, préparer la partie financière de
l'assemblée générale, et un prévisionnel. **Les chiffres viennent des relevés de la banque**, jamais
d'une saisie ni d'une IA ; l'appli calcule, l'assistant commente.

## 2. Accès et sous-modules

Onglet **Financier**, trésoriers et Super User seulement (`core.md` §4). Sous-onglets, dans l'ordre :

1. **Comptes** (§3) — fait.
2. **Pièces** (§8) — à faire ; reprend le sous-onglet **Notes de frais** (`notes-de-frais.md` §7,
   décision de Seb, 29 octobre), qui disparaît.
3. **Bilan** (§4) — fait ; documents de l'AG à faire (§8.6).
4. **Assemblée générale** (§5) — fait.
5. **Prévisionnel** (§6) — fait.

Chaque sous-module expose ses actions à l'Assistant IA (`assistant-ia.md` §3, `actions.py`) : cible
de Seb, « fais-moi le PPT de l'AG de cette année à partir de celui de l'année dernière et du bilan
financier de cette année ». Fait, cette version (§7).

## 3. Comptes

### 3.1 Le relevé fait foi

Le trésorier dépose les **relevés PDF de la banque** (Crédit Mutuel : compte courant, Livret Bleu),
un par un ou en archive (zip, 7z, tar), depuis le menu **⋯ › Importer des relevés**. Chaque relevé
est lu mot à mot (position sur la page) et **vérifié au centime** : solde de début + opérations =
solde de fin, sinon il est refusé avec le message de la banque. Un relevé déjà importé (même compte,
même période) est ignoré : on peut redéposer toute une archive. Le compte rendu de l'import
(importés, déjà présents, refusés) s'affiche dans l'écran.

Pas de saisie manuelle d'opérations. Pas d'import CSV pour l'instant (un CSV n'a pas de soldes à
vérifier). La **connexion bancaire** (§3.5) ajoute des opérations provisoires « en attente du
relevé » ; le relevé qui les couvre les remplace.

### 3.2 L'écran

Repris de Sambo Admin :

- En-tête : **Total des comptes** (ou le compte choisi), solde par compte, « au jj/mm/aaaa ».
- Puces : comptes affichés (**Tous**, puis une puce par compte, sous le nom que lui donne le
  trésorier, autant de comptes qu'il en faut ; avant : CC + Bleu, deux comptes), **Graphique** |
  **Tableau**.
- Filtres : menu Catégories (toutes, les 5 plus grosses opérations, les 5 opérations les plus fréquentes — même libellé, sans dates ni numéros, au moins deux fois —, une catégorie ; des opérations et non des catégories depuis le 28 octobre 2026, Seb) et
  recherche (libellé, détail, catégorie, sans accents). Avec un filtre : nombre d'opérations,
  recettes, dépenses, net, détail par catégorie.
- **Graphique** : courbe du solde (ou du cumul des opérations retenues), périodes 3M / 6M / 1A / Max
  / **Saisons** (une courbe par saison de l'organisation, superposées du début à la fin de saison,
  chaque saison masquable d'un appui dans la légende), infobulle des opérations du jour.
- **Tableau** : date, libellé (catégorie, compte, détail), montant, solde de chaque compte, total ;
  50 lignes puis la suite en descendant. Un **virement entre deux comptes de l'organisation** n'occupe
  qu'une ligne (⇄, catégorie « Virement interne », total inchangé) ; sur un compte seul, c'est une
  opération ordinaire.
- Bas de page : périodes couvertes par les relevés, par compte, et les **trous** (« il manque un relevé
  entre le … et le … »).

Catégories : par mots-clés dans le code (`finances/categories.py`, liste de Sambo Admin), « Autres »
sinon. Catégories modifiables par le trésorier : amélioration à faire plus tard.

### 3.3 Données

Tables `fin_accounts` (organisation, numéro, nom, nature courant / livret ; unique par organisation
et numéro), `fin_statements` (compte, période, soldes de début et de fin, fichier ; unique par compte
et période), `fin_operations` (compte, relevé, rang, date, date de valeur, libellé, détail, montant en
centimes, opération jumelle du virement interne). Pas de saison : l'historique les traverse. Chaque
organisation ne voit que ses comptes (`org_id`).

### 3.4 Routes

`POST /finances/import` (fichiers), `GET /finances/ledger[?account=id]`, `GET /finances/seasons`.
L'appli hôte fournit le membre (`finances_contretemps/adapter.py` : trésorier, ou Super User avec
l'école choisie par l'en-tête `X-Ecole-Id`) et les saisons de l'organisation.

### 3.5 Connexion bancaire (28 octobre 2026)

Seb : brancher le vrai compte de l'école (Contretemps : CIC Lyonnaise de Banque, **trois comptes**,
401 compte courant, 403 compte courant des honoraires des professeurs, 402 Livret A). Repris de
Sambo Admin (`test-python`, `bankaccounts/` et `bankstatements.sync_live`), par **Enable
Banking** (agrégateur PSD2), pour plusieurs organisations :

- **Menu ⋯ › Se connecter aux comptes en banque** (nom choisi par Seb le 28 octobre) : un volet du même nom. Sans banque : choisir la banque dans la liste
  d'Enable Banking (recherche), l'espace (**Professionnels et associations** ou **Particuliers**),
  puis **Aller à ma banque** : on s'identifie chez la banque, on valide sur son téléphone, on
  revient sur l'appli. Banque connectée : « CIC · accès jusqu'au … · lue le … », **Actualiser**,
  **Reconnecter ou changer de banque**, les comptes lus à la banque (case à cocher : suivi ou non ;
  une carte, sans IBAN, n'est jamais proposée) et le **nom de chaque compte** (modifiable, aussi
  pour un compte venu des relevés ou sans banque connectée ; la fin du numéro, « n° …20401 », est
  affichée à côté pour distinguer deux comptes de même nature).
- **Fiche d'un compte** (Seb, 28 octobre) : une pastille de compte choisie, le lien « Voir le
  compte » sous son nom ouvre sa fiche : nom (modifiable), IBAN s'il est relié à la banque (sinon
  le numéro lu sur les relevés), nature, banque reliée ou non, périodes couvertes par les relevés.
  Le clic sur une pastille garde son rôle (choisir le compte affiché).
- Relevés : une ligne datée **sans montant** (CIC, livret : « NOUVEAU TAUX DU LOBNL TRIPLEX ») est
  une information, ignorée ; le solde reste vérifié au centime (28 octobre 2026).
- **Une banque par organisation**, choisie au moment de connecter. Le serveur ne garde que ce qui
  est commun : identifiant de l'application, clé privée (fichier monté en lecture seule, jamais
  dans le dépôt ni dans une variable), adresse de retour (`DEPLOY.md` §4).
- **Retour de la banque** : une seule adresse, `GET /finances/bank/return` (publique) ; `state`,
  aléatoire et valable 30 minutes, dit quelle organisation revient. Le serveur termine la
  connexion puis renvoie vers l'adresse de l'école (`?banque=ok|annule|erreur`), où l'écran
  Comptes l'annonce et ouvre le volet.
- **Lecture** : solde (comptable de clôture de préférence) et opérations des 90 derniers jours
  des comptes suivis, à la connexion puis par **Actualiser** (les banques limitent les lectures
  automatiques à environ quatre par jour). Seules les opérations **postérieures au dernier relevé**
  du compte sont gardées, en provisoires (`source = banque`) ; elles sont remplacées à chaque
  lecture (lire deux fois n'ajoute rien).
- **Compte sans relevé** : créé depuis son IBAN (numéro = IBAN, nature courant ou livret selon la
  banque, nom par défaut « <produit> <3 derniers chiffres du compte> », ex. « Compte courant
  401 ») ; son solde lu à la banque sert de point de départ. Un relevé importé ensuite se rattache
  au même compte (son numéro est dans l'IBAN) et efface les provisoires qu'il couvre : le relevé
  fait foi.
- **Expiration** : 180 jours au plus ; le volet le dit, « Reconnecter la banque ».
- **Sans contrat Enable Banking**, l'application ne lit que les comptes que son propriétaire y a
  d'abord liés (Control Panel) : l'école de Seb, pas d'autres écoles.

Données : table `fin_bank_connections` (une ligne par organisation : banque, pays, espace,
session chiffrée, expiration, comptes autorisés et suivis, `state` en attente, dernière lecture,
dernière erreur) ; `fin_accounts` gagne `bank_uid`, `bank_balance` (centimes) et
`bank_balance_date`. Migration `f1a3c5e7b9d0`. Routes : `GET /finances/bank`,
`GET /finances/bank/banks?q=`, `POST /finances/bank/connect`, `GET /finances/bank/return`,
`PUT /finances/bank/accounts`, `POST /finances/bank/sync`, `PUT /finances/accounts/{id}`.

Pas encore fait : lecture automatique (deux fois par jour) et rappel avant l'expiration ;
lecture des relevés PDF du CIC (écrite pour le Crédit Mutuel, à vérifier).

## 4. Bilan

Repris de Sambo Admin (`financialreports/`). Un **bilan** est le compte d'exploitation d'une saison,
calculé par l'appli à partir des opérations de tous les comptes (§3), virements internes exclus.

### 4.1 Ce que fait l'appli, ce que fait l'analyse

- **L'appli calcule** : recettes et dépenses par catégorie et par mois, résultat, soldes de début et
  de fin (tous les comptes), et la **vérification** « solde de début + recettes − dépenses = solde de
  fin réel » (écart affiché sinon). Saison en cours : arrêtée au dernier jour connu des comptes.
  Comparaison avec la saison précédente (écart en % par catégorie) et rappel des trois saisons
  d'avant.
- **L'analyse** (modèle de langage, jamais nommé « IA » à l'écran) classe les opérations restées
  dans « Autres » (marquées « classé automatiquement ») et écrit **5 lignes** de commentaire selon
  les consignes du trésorier. Elle ne produit aucun chiffre : le tableau est recalculé avec son
  classement. Les classements d'un bilan **Officiel** servent de référence aux bilans suivants.
- Modèle au choix (Haiku, Sonnet par défaut, Opus, Fable), **coût** affiché en euros et noté dans
  Ressources (catégorie « Financier : analyse des bilans »). Le calcul tourne en arrière-plan, l'écran
  relit le bilan jusqu'à la fin.

### 4.2 L'écran

Sous-onglet **Bilan** : saison (celle en cours par défaut, nombre de bilans par saison), puces
Tous | Brouillon | Validé | Officiel, liste des bilans (nom, état, modèle, coût, date ; suppression).
**⋯ › Nouveau bilan**. Un bilan : nom, état, consignes pour l'analyse, modèle, coût cumulé ;
**Enregistrer** et **Produire le bilan** ; résultat : période, vérification, quatre chiffres
(recettes, dépenses, excédent ou déficit, solde de fin, avec la saison précédente), analyse, tableau
**Par catégorie** (avec écart) ou **Par mois** (le modèle du trésorier) ; téléchargement **Excel** et
**PDF**. Un seul bilan Officiel par saison : passer un bilan en Officiel ramène l'ancien en Validé.

Laissé de côté de Sambo Admin : réordonnancement des cartes, consignes enregistrées ; pas de fichier
Docs (décision de Seb : les produits seront rangés dans Docs › Financier plus tard).

### 4.3 Données et routes

Table `fin_reports` (organisation, saison, nom, état brouillon / valide / officiel, consignes,
modèle, coût cumulé en dollars, résultat JSON, statut du calcul, erreur). Routes
`GET /finances/reports?seasonId=`, `POST /finances/reports`, `GET|PUT|DELETE /finances/reports/{id}`,
`POST /finances/reports/{id}/run`, `GET /finances/reports/{id}/download?format=xlsx|pdf`.

## 5. Assemblée générale

Repris de Sambo Admin (`generalassemblies/`). Une **AG** est la base du PowerPoint de l'assemblée
générale d'une saison, préparée à partir du bilan de la saison (§4) et du PowerPoint de l'AG
précédente.

### 5.1 Ce que fait l'appli, ce que fait le calcul

- Chaque AG garde au plus **trois PowerPoint**, un par sorte : le **modèle** (l'exemple dont on
  reprend la mise en page : fichier de l'ordinateur, PowerPoint d'une autre AG, ou par défaut le
  PowerPoint final de l'AG officielle de la saison précédente, sinon le **modèle général** de
  l'organisation envoyé depuis ⋯), le **produit** (par le dernier calcul) et le **modifié** (retouché
  par le trésorier et renvoyé dans l'appli). Un nouveau fichier remplace celui de la même sorte.
- **Produire le PowerPoint** : le modèle de langage (jamais nommé « IA » à l'écran) reçoit le plan
  du modèle (zones de texte de chaque diapo), les chiffres du bilan de la saison (l'officiel, sinon
  le validé, sinon le brouillon le plus récent ; aucun bilan calculé : refusé) et les inscrits par
  saison. Il réécrit les diapos du trésorier (rapport d'activité, bilan, recettes, dépenses,
  résultat, prévisionnel), met les années à jour et marque **« À compléter »** (surligné en jaune) ce
  qu'il ne sait pas. **L'appli place ce texte dans le modèle** sans toucher à la mise en page et
  **vérifie chaque montant** écrit : tout montant qui ne vient ni du bilan ni des consignes est
  signalé (« Diapo n : x € ne vient pas du bilan, à vérifier »).
- Modèle au choix, coût en euros noté dans Ressources (« Financier : PowerPoint des assemblées
  générales »). Calcul en arrière-plan, l'écran relit l'AG jusqu'à la fin.

### 5.2 L'écran

Sous-onglet **AG** : même écran que Bilan (saison, puces d'état, liste ; **⋯ › Nouvelle AG**,
**⋯ › Modèle général de PowerPoint…**). Une AG : nom, état, PowerPoint modèle (« Choisir un
fichier », « Prendre le PowerPoint d'une autre AG… »), consignes, modèle, coût cumulé ;
**Enregistrer** et **Produire le PowerPoint** ; résultat : puces Modèle | Produit | Modifié,
téléchargement, bilan et modèle utilisés, montants à vérifier, résumé en 3 lignes, **aperçu des
diapos** (images par LibreOffice Impress s'il est installé sur le serveur, sinon le texte de chaque
diapo ; appui = plein écran) avec un point sur les diapos écrites par le calcul ; **Importer le
PowerPoint modifié**. Un seul PowerPoint officiel par saison.

*(Contretemps)* L'image Docker n'a que LibreOffice Writer et Calc : ajouter
`libreoffice-impress-nogui` au `backend/Dockerfile` pour les images des diapos (à faire par Seb).
Laissé de côté de Sambo Admin : réordonnancement des cartes, consignes enregistrées.

### 5.3 Données et routes

Tables `fin_assemblies` (mêmes colonnes que `fin_reports`, résultat JSON : bilan et modèle
utilisés, diapos écrites, résumé, montants à vérifier) et `fin_assembly_files` (AG, numéro, origine
modele / genere / envoye, nom, provenance). Fichiers `data/finances/assemblies/<organisation>/<AG>/v<n>.pptx`
(volume Docker, `FINANCES_DIR`), modèle général `<organisation>/modele.pptx`. Routes
`GET|POST /finances/assemblies`, `POST /finances/assemblies/template`,
`GET /finances/assemblies/model-sources`, `GET|PUT|DELETE /finances/assemblies/{id}`,
`POST …/{id}/run`, `POST …/{id}/upload`, `POST|PUT …/{id}/model`, `GET …/{id}/download?kind=`,
`GET …/{id}/files/{kind}/slides` et `…/slides/{n}.png`.

## 6. Prévisionnel

Repris de Sambo Admin (`forecasts/`). Un **prévisionnel** prévoit le solde de tous les comptes de
l'organisation, semaine par semaine, d'une date de départ jusqu'à la fin de la saison.

### 6.1 Ce que fait l'appli, ce que fait le calcul

- **L'appli prépare les données** : solde réel à la date de départ (celle du prévisionnel, sinon le
  dernier jour connu des comptes, au plus aujourd'hui ; saison terminée : une date est obligatoire,
  pour tester le prévisionnel sur le passé), solde au début de la saison, semaines jusqu'à la fin
  de saison (avec les mois qui commencent), ce qui est déjà passé sur le mois en cours, les 12 mois
  précédents par catégorie et leur moyenne mensuelle. Pas d'inscrits ni d'échéances de paiement
  (Sambo Admin les lisait dans HelloAsso) : le modèle fait sans.
- **Produire le prévisionnel** : le modèle de langage (jamais nommé « IA » à l'écran) n'écrit
  aucun chiffre : il écrit une **formule Python** `prevoir(donnees, p)` d'après les consignes du
  trésorier et déclare ses **curseurs** (nom, libellé, min, max, défaut, pas, unité), avec une
  explication en quelques phrases. **L'appli vérifie la formule** (une seule fonction, imports
  limités à `math` et `datetime`, ni fichier, ni réseau, ni nom ou attribut commençant par `_`) et
  **l'exécute à part** (processus séparé, `python -I`, garde-fous d'audit, délai maximal). Une
  formule refusée ou en erreur est renvoyée une fois au modèle pour correction.
- **Bouger un curseur rejoue la formule** sans rappeler le modèle ; la position des curseurs est
  enregistrée et reprise au calcul suivant (si le curseur existe toujours).
- Modèle au choix, coût en euros noté dans Ressources (« Financier : prévisionnels »). Calcul en
  arrière-plan, l'écran relit le prévisionnel jusqu'à la fin. Plusieurs prévisionnels officiels par
  saison (ce sont des hypothèses, pas un document de référence).

### 6.2 L'écran

Sous-onglet **Prévisionnel** : même écran que Bilan (saison, puces d'état, liste ; **⋯ › Nouveau
prévisionnel**). Un prévisionnel : nom, état, date de départ (raccourcis « Aujourd'hui », « Début
de saison », « Dernier relevé »), consignes, modèle, coût cumulé ; **Enregistrer** et **Produire le
prévisionnel** ; résultat : **Formule** (Explication | Formule Python, encart « Formule vérifiée »),
**Curseurs** (un curseur par paramètre, « Revenir aux défauts »), trois chiffres (solde au début de
saison, solde prévu en fin de saison, résultat prévu), **graphique** : réalisé de la saison, prévision
en pointillés, réel après le départ quand la date est passée, ligne d'équilibre (solde de début de
saison), saisons précédentes superposées au choix (retenu sur l'appareil) ; téléchargement en
**image** ou **PDF** avec les mêmes saisons.

Laissé de côté de Sambo Admin : réordonnancement des cartes, consignes enregistrées, zones
repliables mémorisées, inscrits HelloAsso.

### 6.3 Données et routes

Table `fin_forecasts` (mêmes colonnes que `fin_reports`, plus `start_date` et `params` : dernière
position des curseurs ; résultat JSON : formule, explication, curseurs, données, courbe). Routes
`GET|POST /finances/forecasts`, `GET|PUT|DELETE /finances/forecasts/{id}`, `POST …/{id}/run`,
`PUT …/{id}/params`, `GET …/{id}/download?format=png|pdf&seasons=`.

## 7. Actions de l'Assistant IA

Comme les autres modules (`assistant-ia.md` §3), le Financier ouvre ses actions à l'assistant
dans `finances_contretemps/actions.py` (il faut passer du compte de Contretemps au `Member` du
module). Chacune propose une carte Faire / Annuler, et ne fait au clic que ce que le bouton
« Produire… » du sous-onglet fait déjà ; le calcul tourne en arrière-plan, le résultat se lit
dans l'appli. Réservées aux trésoriers et au Super User (refus sinon) :

| Action | Ce qu'elle fait |
|---|---|
| `produce_financial_report` | Crée un bilan (saison par son nom, ou la saison en cours ; nom, consignes, état, modèle) et lance son calcul. |
| `produce_general_assembly` | Crée une AG et lance le PowerPoint : il faut un bilan calculé (sinon refus qui renvoie au bilan) et un PowerPoint modèle (par défaut l'AG officielle de la saison précédente, sinon le modèle général ; ou `template` : une AG désignée par son nom ou sa saison, « modèle général »). |
| `produce_forecast` | Crée un prévisionnel (date de départ facultative, vérifiée dans la saison) et lance son calcul. |

Pas d'action pour Comptes : importer des relevés demande un fichier, que l'assistant ne transmet
pas aux actions. L'assistant ne lit pas encore les chiffres du Financier (soldes, bilans) : à
décider avec Seb.

## 8. Pièces et comptabilité (28 octobre 2026)

Étude « documents comptables de l'AG » (fil du 28 octobre, maquette validée par Seb :
https://claude.ai/artifact/5nieoHKtypLrvyrgnsuPaM). Point de départ : les quatre documents que
la trésorière de Contretemps (comptable de métier) produit pour l'AG, édités le 9 novembre 2025
par son logiciel comptable pour 2024-25 : **Balance**, **Grand livre**, **Rapport financier**
(Word) et **Synthèse Dépenses-Recettes** (Excel). Ce sont les modèles de forme à reproduire.

Objectif : les produire dans l'appli à partir des comptes en banque (§3) et des justificatifs, sans
ressaisie, et sans que l'assistant écrive un chiffre. Ce que l'association a : des dossiers papier
par nature de pièce, que la trésorière a fait créer dans Docs › Privé › Saison <saison> › Financier
le 28 octobre 2026 : **Achats**, **Honoraires**, **Notes de frais**, **Ventes**. Ce sont exactement
les journaux de son grand livre (AC, HO, NF, VE).

### 8.1 Deux niveaux, un réglage

Admin › École › Personnalisation › Fonctionnalités, ligne Financier : **Simple** ou **Complet**,
par organisation. Pas de troisième cas.

- **Simple** (comptabilité de trésorerie ; une association loi 1901 sous les seuils n'a rien
  d'autre à tenir) : comptes en banque, caisse, pièces rattachées, plan comptable, Synthèse,
  Rapport financier. Le Sambo reste en Simple.
- **Complet** (partie double) : en plus, comptes de tiers (401 Fournisseurs, 411 Adhérents, un
  467x par prof, 471 Attente), écritures à deux lignes générées par l'appli, lettrage, soldes de
  départ, clôture, Grand livre et Balance au format de la comptable, relevé des honoraires par prof
  (DAS-2). Contretemps passe en Complet.

Passer de Simple à Complet est possible à tout moment : l'appli génère les écritures manquantes à
partir des pièces déjà rattachées. L'inverse n'existe pas.

### 8.2 Plan comptable

Comptes ⋯ › **Plan comptable** : la liste des comptes de l'organisation, numéro du plan comptable
associatif + libellé de l'organisation (« 613 Location Galli », « 6226 Honoraires des
professeurs »), groupés Dépenses / Recettes / Tiers et attente (Complet). Repris au départ de la
Balance 2024-25 de la comptable (pour une nouvelle organisation : liste par défaut courte,
`finances/chart.py`). Un compte peut être marqué « gala » (ou autre événement) pour le bloc
« Ressources / Coût » de la Synthèse. Ajout, renommage ; un compte utilisé ne se supprime pas.

Les catégories par mots-clés de §3.2 (`categories.py`) restent pour l'écran Comptes ; chaque
compte du plan porte ses mots-clés de proposition (repris et enrichis par l'historique confirmé :
même fournisseur → même compte). Pas de « type » à l'écran : on dit « compte » et « nature ».

### 8.3 Pièces (sous-onglet)

Financier › **Pièces** : le classeur des justificatifs. Puces **Achats** · **Honoraires** ·
**Notes de frais** · **Ventes** : les quatre dossiers de l'association dans Docs (ci-dessus), ni
plus ni moins, qui donnent le journal (AC, HO, NF, VE) ; plus une puce **À rattacher** (compteur)
qui est un filtre sur les pièces pas encore rattachées, pas un dossier. Bouton principal
**+** (voir §8.3 bis « Établir une dépense ») : Photo du ticket, Choisir un fichier, ou « Choisir
dans Docs » (PDF reçu par mail). Chaque photo est un fichier du dossier
Docs › Privé › Saison <saison> › Financier › <dossier>, nommé par l'appli
(« 2025-02-09 Amazon 39,90.jpg ») une fois lue ; une photo pas encore lue attend dans Ventes
ou Achats selon le sens, et change de dossier si la lecture dit autrement.

Trois origines de pièces :
- **photographiées** (factures, tickets, notes d'honoraires, bordereaux de chèques) ;
- **produites par l'appli** : note de frais validée (`notes-de-frais.md`, journal NF, déjà
  rattachée à son virement de remboursement), virement HelloAsso (`helloasso.md`, ventilé
  Cotisations / Cours par les inscriptions de la saison) ; plus tard, notes d'honoraires calculées
  par la présence des profs (module à part) ;
- **caisse** (§8.5).

Cas de la **remise de chèques** (dossier Ventes ; vu chez la trésorière de Contretemps le
28 octobre) : le ticket de dépôt de la banque (« 25 chèques, 3 795,00 € ») et la page du cahier
qui liste chaque chèque (nom de la famille, banque, numéro, montant) forment une seule pièce,
photographiée en deux fois et lue ensemble. Elle se rattache à la ligne « REM CHQ » du relevé,
avec une **sous-ligne par chèque** : nom rapproché d'une fiche de l'appli (famille, par le
payeur ; proposition à confirmer), montant, compte Cotisations ou Cours déduit de l'inscription
de l'élève (ou choisi). La somme des sous-lignes doit faire le montant de la banque. Le paiement
apparaît sur la fiche de l'élève ; le trésorier voit qui n'a pas payé.

**Lecture et proposition** (modèle de langage, jamais nommé « IA » à l'écran, coût noté dans
Ressources « Financier : lecture des pièces ») : la pièce est lue (fournisseur, date, montant,
numéro, objet), rangée dans un dossier, et l'appli propose **la ligne de banque** (même montant,
date proche, nom) et **le compte** du plan. Le trésorier **Confirme**, choisit **Autre ligne**,
ou dit **Pas encore payée** / **Payée en espèces**. Rien n'est rattaché sans confirmation ; la
ligne garde « proposé par l'assistant, confirmé par X le … ». Le montant lu sert à chercher la
ligne, jamais à écrire un chiffre dans les comptes : le montant comptable est celui de la banque
(ou de la caisse). Une différence pièce / banque est signalée, pas corrigée.

Une pièce « pas encore payée » reste dans son dossier et compte dans « Fournisseurs à payer » de
la Synthèse (Simple) ou dans 401 (Complet).

### 8.3 bis Virements (puce de Pièces, 29 octobre 2026)

Étude et maquette retenues par Seb le 29 octobre 2026 (fil « Module : Virements depuis l'appli »,
https://claude.ai/artifact/B9Udrp2K2KGb92vgQ69yHh). Besoin : savoir ce qui attend d'être payé et
où en est chaque paiement ; aider à faire le virement ; le faire faire par quelqu'un d'autre (chez
Contretemps, la trésorière prépare et la trésorière adjointe, qui a l'appli CIC, paie).

**L'appli ne paie pas.** Lancer un virement par API demande une licence d'établissement de
paiement (Enable Banking la réserve aux sociétés agréées) ou un contrat avec un prestataire agréé
(Bridge : sur devis, CIC à confirmer). Écarté pour l'instant ; la banque fait de toute façon
valider chaque virement dans son appli. L'assistant ne remplit pas l'appli de la banque (Android
et la banque l'interdisent ; l'assistant n'écrit jamais un chiffre).

Financier › Pièces › puce **Virements** (première puce, avant À rattacher ; compteur = ce qui
reste à faire). Quatre états, une partie chacun, qui se déroule et se replie (À payer ouvert,
les autres repliés avec leur nombre ; une partie vide n'apparaît pas) :

1. **À payer** : pièce de dépense reçue, rien de préparé ;
2. **Préparés, en attente d'envoi** : préparé, la personne qui paie ne l'a pas encore fait ;
3. **Envoyés** : « J'ai fait le virement » touché, pas encore vu sur le compte ;
4. **Payés** : l'opération est vue sur le compte, la pièce y est rattachée (= « rattachée »).

**Machine à états** (schéma de Seb, 29 octobre : `/mnt/project-files/appbase/captures/virements-schema-seb.jpg`),
la même pour les trois natures de dépense :

```
Note de frais ──┐                              Achat (établi par le trésorier)
Honoraires ─────┴─▶ À valider                              │
   (établis par l'auteur,  │                            À valider
    ou le trésorier        ▼                               │
    pour lui)       Validation trésorier       Déjà payé ? (vérifié sur les comptes)
                     │ non         │ ok            │ non              │ oui
                     ▼             ▼               ▼                  │
              Refusé (motif)    À payer ◀──────────┘                  │
                                   ▼                                  │
                           Virement préparé ──▶ (demande au trésorier qui a la carte)
                                   ▼                                  │
                                Envoyé                                │
                                   ▼                                  ▼
                                 Payé ◀───────────────────────────────┘
```

Toute dépense commence **À valider**, dès qu'elle est établie. Les notes de frais suivent cette
machine (plus de statuts à part, `notes-de-frais.md` §5) et le sous-onglet Notes de frais de
Financier disparaît : les notes sont dans la puce Notes de frais de Pièces (`notes-de-frais.md` §7),
le côté membre ne change pas.

**Une seule structure « dépense »** (décision de Seb, 29 octobre) : note de frais, note d'honoraires
et achat sont la même chose, avec une **nature** (frais / honoraires / achat), portée par le module
Notes de frais déjà codé (`nf_notes` + `nf_depenses`, qui gardent leur nom ; on ajoute la nature et,
pour un achat, le fournisseur à la place de la personne). **Deux niveaux pour les trois natures**
(Seb, 29 octobre) : la **dépense** = un ticket ou une facture (photo, montant, compte) ; la **note** =
ce qu'on paie en une fois, qui porte l'état et le RIB, et qui passe par Virements. Notes de frais :
inchangé. Honoraires : la note d'un prof a le plus souvent une ligne (le mois), parfois deux. Achats :
une photo crée une note avec une seule dépense ; plusieurs factures réglées d'un seul virement se
regroupent avec **« Ajouter une dépense à cette note »** depuis la note.

**Saisir le moins possible** (Seb, 29 octobre) : la photo fait le travail. La lecture remplit tout ce
qu'elle peut (personne ou fournisseur, date, montant, période, compte, description) et l'écran ne
demande que de **valider ou corriger**, jamais de ressaisir ; une dépense lue sans doute s'enregistre
d'un seul toucher. Les puces Notes de frais,
Honoraires et Achats de Pièces sont trois filtres sur cette nature ; Ventes reste à part (recettes).
Partagé tel quel : la fiche (qui, titre, photos agrandissables, total, RIB), l'envoi, Valider et
Refuser avec motif, « Saisir pour quelqu'un », les badges d'état, le rangement dans Docs, l'export
Excel, et la **recherche du paiement sur les comptes** à l'établissement, pour les trois natures (une
note de frais ou des honoraires déjà virés passent directement Payé, comme un achat). Ce qui diffère :
honoraires = l'auteur est un prof, une seule ligne (période, montant), journal HO ; achat = établi par
le trésorier, « qui » est un fournisseur, RIB demandé seulement quand il y a à payer, journal AC.

**Établir une dépense : le « + »** (Seb, 29 octobre). Un seul bouton principal sur Pièces, **+**,
qui reprend l'écran « Nouvelle dépense » de `notes-de-frais.md` §4.2, tel qu'il est codé
(`DepenseModal.jsx`) : deux boutons, **Photo du ticket** (appareil photo) et **Choisir un fichier**
(image ou PDF), plus « Choisir dans Docs » ; lecture par l'appli qui pré-remplit avec la mention
« Rempli d'après le ticket, à vérifier », on corrige, **Enregistrer**. La nature est celle
de la puce où l'on est (Notes de frais, Honoraires, Achats) ; depuis Virements, À rattacher ou
Ventes, le « + » demande d'abord la nature. Les champs changent avec la nature, le reste est commun :
- **Note de frais** : d'abord « Pour qui ? » (§7 ter de `notes-de-frais.md`), puis date, montant,
  catégorie, description ; plusieurs dépenses forment une note (titre) ;
- **Honoraires** : « Pour qui ? » (un prof), période (mois), montant ; une ligne = une note, pas de
  catégorie (compte 6226) ;
- **Achat** : fournisseur (lu sur la facture), date, montant, compte du plan proposé, description ;
  pas de « Pour qui ».
Une dépense établie par le trésorier est validée en même temps. Le bouton « Photographier des
pièces » de §8.3 et des écrans d'exemple n'existe plus : c'est le « + », avec « Photo du ticket »
dedans.

**Rafale** (Seb, 29 octobre) : pour une note de frais, une photo = une dépense, avec le formulaire
tout de suite (comme aujourd'hui). Pour **Achats** et **Honoraires**, le trésorier a souvent une pile
de papiers : « Photo du ticket » enchaîne les photos sans formulaire entre deux, **une photo = une
dépense**, chacune créée aussitôt (À valider, « Lecture en cours… ») et lue en arrière-plan ; après
chaque photo, **Pièce suivante** (par défaut) ou **Encore une page de celle-ci** (facture de deux
pages, ticket de dépôt + page du cahier). On revient ensuite à la liste de la puce, où chaque ligne
porte ce qui a été lu (fournisseur ou prof, date, montant, compte proposé) : on touche une ligne pour
vérifier ou compléter, le reste est déjà rangé dans Docs. Pour les honoraires, la lecture reconnaît le
nom du prof et le rapproche d'une fiche ; en cas de doute la ligne demande « Pour qui ? ». Même chose
avec « Choisir un fichier » et « Choisir dans Docs » quand on sélectionne plusieurs fichiers, et, sur
ordinateur, en **glissant des fichiers** depuis le bureau sur la liste de la puce (Achats, Honoraires
ou Notes de frais) : chaque fichier déposé = une dépense de cette nature, comme un import. Pas sur
téléphone.

**Rangement dans Docs** (Seb, 29 octobre, revient sur `notes-de-frais.md` §7 bis et « Rangement sur le
disque » du 16-17 octobre) : **un seul endroit**, Docs, dans les dossiers de la trésorière ; la
photo y est rangée à l'établissement et **n'en bouge plus**. **L'état ne se voit que dans l'appli**,
sur la ligne de la dépense : dans Docs le fichier n'a pas de badge et ne change pas. Le PDF
récapitulatif est fait **une seule fois, quand c'est payé** (et sur demande avant, « Télécharger »),
plus de version à chaque étape. Plus d'enveloppes à part sur le disque du serveur (`NOTES_FRAIS_DIR`)
: Docs range déjà ses fichiers sur le disque. Chemins :
- Notes de frais : `Notes de frais › <n° personne> <Nom> › <date> <titre> (<n°>)`, comme aujourd'hui ;
- Honoraires : par personne aussi, `Honoraires › <n° personne> <Nom> › <date> <titre> (<n°>)` ;
- Achats : pas par personne, `Achats › <date> <fournisseur> <montant>` (le fichier lui-même, comme
  « 2025-02-09 Amazon 39,90.jpg » de §8.3 ; un dossier seulement quand l'achat a plusieurs pièces).

- **Note de frais** et **note d'honoraires** sont établies (saisies, photographiées ou importées
  d'un fichier) par leur auteur (le membre, le prof), ou par le trésorier pour lui ; la validation du trésorier les fait passer d'À valider à À payer,
  ou à **Refusé** avec un motif (comme `notes-de-frais.md` §5). Quand c'est le trésorier qui
  établit pour la personne, la validation est faite en même temps : la pièce passe directement
  À payer.
  Le RIB vient de `nf_ribs` s'il est déjà donné. Plus tard, les honoraires seront calculés par la
  présence des profs.
- **Achat** : établi (saisi, photographié ou importé) par le trésorier, À valider le temps que
  l'appli cherche le paiement sur les comptes.
  Trouvé (carte du club, prélèvement, virement fait avant la facture, comme le camping) : la pièce
  se rattache à l'opération et est **Payé** sans passer par Virements. Pas trouvé : **À payer**
  (c'est ce que dit le bouton « Pas encore payée » de §8.3). Un achat réglé avec la carte
  personnelle du trésorier n'est pas un achat mais une note de frais.
- On peut aussi **préparer un virement sans pièce** (demande ou devis) ; la facture s'y rattache
  quand elle arrive (« Ajouter la facture »).

Dans Achats, Honoraires, Notes de frais, chaque dépense montre son état (badge À valider / Refusé / À payer / Préparé /
Envoyé / Payé) ; payée par carte ou déjà vue sur le compte : directement Payé.

**Aide au virement** : toucher une ligne ouvre « Virement à faire » : bénéficiaire, IBAN, montant,
libellé (« Contretemps honoraires oct 2026 »), chacun avec **Copier**, dans l'ordre de l'écran de
la banque ; le compte à utiliser (403 pour les honoraires) et la pièce. Bouton principal
**J'ai fait le virement** (→ Envoyés) ; **Faire payer par <nom>** (→ Préparés). Pas de RIB :
**Photographier** le RIB (ou le choisir dans Docs), IBAN, BIC et titulaire lus et vérifiés à
l'écran. Guide « Faire un virement dans l'appli CIC » (4 étapes) montré au premier virement, puis
derrière « Comment faire » ; écrit pour le CIC seulement au départ. À tester sur le téléphone de
Seb : « Tout copier » via l'historique du presse-papier du clavier.

**Faire payer par quelqu'un** : réglage **Qui paie** sur la ligne Financier d'Admin › École ›
Personnalisation › Fonctionnalités (une ou plusieurs personnes ; par défaut les trésoriers).
« Faire payer par Anne » lui envoie une notification « Virement à faire : Lucie Martin, 480,00 € »
qui ouvre l'aide au virement, avec « Préparé par Claire Petit le … · RIB enregistré par … le … ».
Si celle qui prépare paie elle-même, pas de notification. Quand le virement est vu sur le compte,
celle qui l'a préparé est prévenue (« Payé »).

**Vu sur le compte** : à chaque lecture de la banque (§3.5) ou import de relevé, une opération de
débit du même montant, au nom du bénéficiaire, après la date d'envoi, est proposée ; rattachée sur
confirmation, comme toute pièce (§8.3). Sans connexion bancaire, Envoyés attend le relevé.

**Sécurité** : le risque est le RIB changé. Enregistrer ou changer un RIB, et préparer un
virement, demandent la clé d'accès (empreinte) de la personne quand l'étude double
authentification sera codée (en attendant : trésoriers et Super User seulement) ; qui et quand
sont gardés et montrés à celle qui paie. Seuls nom, IBAN, BIC sont gardés ; aucun mot de passe
de banque.

### 8.4 Comptes : compte et pièce sur chaque ligne

Dans Comptes › Tableau, chaque opération porte son **compte** (ou « Compte à choisir ») et sa
**pièce** (ou « sans pièce ») ; puces **Sans compte** et **Sans pièce** avec compteur. Un appui
ouvre la **fiche de l'opération** : compte (proposé, à confirmer), pièce (changer, détacher,
photographier, choisir dans Docs), et, en Complet, les **écritures** générées (achat du jour de la
facture : 6xx contre 401 ; paiement : 401 contre 512x ; lettre de rapprochement). Une ligne
HelloAsso ou une remise de chèques se ventile sur plusieurs comptes (montants qui doivent faire
le total ; vérifié par l'appli).

### 8.5 Caisse

Une puce **Caisse** à côté des comptes en banque : le seul compte saisi à la main (une dizaine
de lignes par an : fond de caisse, entrées du gala en espèces, défraiements). Une ligne = date,
libellé, montant, compte, pièce. Un retrait d'espèces au distributeur = virement interne banque →
caisse. Dérogation au §3.1 (« pas de saisie manuelle ») limitée à ce compte.

### 8.6 Documents de l'AG (dans Bilan)

Le Bilan (§4) additionne désormais **par compte du plan** (plus par mots-clés), virements
internes exclus ; l'analyse en cinq lignes reste. Sous le bilan produit, le bloc **Documents de
l'AG** :

| Document | Forme | Niveau |
|---|---|---|
| Synthèse Dépenses-Recettes | Excel + à l'écran : charges et produits par compte groupés par classe (60, 61, 62…), total, résultat ; trésorerie par compte et caisse ; fournisseurs à payer ; un bloc par événement marqué (« Ressources du gala / Coût du gala / Bénéfice ») | Simple |
| Rapport financier | Word + PDF, forme du modèle (A Recettes, B Dépenses, points à revoir, conclusion). Texte rédigé par le modèle d'après le bilan et les consignes ; **chaque montant et chaque pourcentage est placé par l'appli** (gabarit `{{…}}`) et vérifié comme dans l'AG (§5.1) | Simple |
| Grand livre | PDF, forme du modèle : par compte, date, journal, pièce (lien vers la pièce), libellé, lettre, débit, crédit, solde ; totaux par compte et général | Complet |
| Balance | PDF, forme du modèle : par compte, totaux débit / crédit de la période et soldes ; totaux bilan / résultat | Complet |
| Honoraires par professeur | Excel : total par prof et par mois, pour la DAS-2 | Complet |

Les fichiers vont dans Docs › Privé › Saison <saison> › Financier › AG, avec le badge Brouillon / Validé /
Officiel du bilan ; l'AG (§5) les joint à la convocation.

### 8.7 Complet : écritures, soldes de départ, clôture

- **Écritures** : table `fin_entries` (organisation, saison, journal AN/OD/AC/HO/NF/VE/BQn/CA,
  date, pièce, libellé, lettre) et `fin_entry_lines` (écriture, compte, débit, crédit en
  centimes, opération bancaire ou ligne de caisse d'origine, pièce). Générées par l'appli à la
  confirmation d'un rattachement ; jamais saisies à la main, sauf les écritures de régularisation
  OD du trésorier (compte 471, défraiements), avec pièce ou motif.
- **Soldes de départ** (Comptes ⋯ › Soldes de départ) : première saison dans l'appli, repris de
  la Balance de l'an dernier déposée dans Docs (lecture du PDF, vérification à l'écran, « Reprendre
  ces soldes ») ; l'appli vérifie que les soldes 512x égalent les relevés au 31/08. Saisons
  suivantes : calculés par la clôture.
- **Clôture** (Bilan, bilan Officiel) : résultat reporté (120 / 129 → 110), écritures d'à-nouveaux
  de la saison suivante, saison verrouillée (plus de rattachement sans la rouvrir, trace gardée).
- **Lettrage** : lettre de trois caractères par paire facture / paiement, comme le modèle ;
  paiement en plusieurs fois accepté (somme).

### 8.8 Données et routes

Tables `fin_chart_accounts` (organisation, numéro, libellé, nature dépense / recette / tiers /
banque / caisse / attente, événement, mots-clés, actif), `fin_documents` (organisation, saison,
dossier HO/AC/NF/VE/CA, fichier Docs, lecture JSON, état à rattacher / rattachée / non payée /
espèces, opération bancaire ou ligne de caisse, origine photo / docs / notes de frais / helloasso,
proposé par, confirmé par et quand), `fin_operation_accounts` (opération, compte, montant :
ventilation), `fin_cash_lines` (caisse), `fin_entries` / `fin_entry_lines` (§8.7),
`fin_opening_balances`, `fin_payees` (§8.3 bis : organisation, nom, IBAN, BIC, fichier Docs du
RIB, enregistré par et quand ; le RIB d'un membre reste dans `nf_ribs`) ; dans `fin_documents`,
l'état de paiement à payer / préparé / envoyé, bénéficiaire, libellé, préparé par, payé par, dates
(payé = rattachée). Routes sous `/finances/chart`, `/finances/documents`
(`POST …/upload`, `POST …/{id}/confirm`, `…/unpaid`, `…/cash`), `/finances/cash`,
`/finances/entries`, `/finances/reports/{id}/documents?kind=synthese|rapport|grand-livre|balance|honoraires`.

### 8.9 Étapes (une PR chacune, sur le « vas-y » de Seb)

1. Plan comptable, Pièces (photo, lecture, proposition, confirmation), compte et pièce sur chaque
   ligne de Comptes, caisse, réglage Simple / Complet. Suffit pour la Synthèse.
1 bis. Virements (§8.3 bis) : puce, quatre états, aide au virement, RIB, Qui paie, notification.
2. Documents de l'AG : Synthèse, Grand livre, Balance, Honoraires par prof ; Bilan par compte.
3. Rapport financier (gabarit Word du modèle, texte par le modèle, chiffres par l'appli).
4. Complet : écritures, soldes de départ, lettrage, clôture.

À demander à la trésorière (vendredi 31 octobre) : son logiciel et si elle veut un export vers
lui ; si elle confirme elle-même dans l'appli (compte Trésorier) ; son plan comptable 2025-26 ;
qui tient la caisse ; les 717,50 € du compte d'attente.

## 9. Reste à faire

- Connexion bancaire (§3.5) : lecture automatique deux fois par jour, rappel avant l'expiration,
  relevés PDF du CIC.
- Améliorations notées : tableau plus lisible sur téléphone, catégories modifiables, « reste à
  recevoir » HelloAsso, textes ≥ 17 px (l'écran est repris tel quel).
