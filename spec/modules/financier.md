# AppBase — Module `finances` (onglet Financier)

Version 0.10, 29 octobre 2026 (§8 : dossiers de la trésorière Achats / Honoraires / Notes de frais / Ventes ; §8.3 bis : Virements, machine à états ; §8.9 : étapes 1 à 4 codées ; §8.7 : écritures recalculées, pas stockées). Statut : **décision de Seb, 20 octobre** : reprendre tel quel le
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
(importés, déjà présents, laissés de côté, refusés) s'affiche dans l'écran.

**Revue avant l'import (Seb, 9 novembre 2026 ; maquette
https://claude.ai/artifact/Cfxf9LG6GKEmYC19vd3dv2)** : l'appli lit d'abord les fichiers **sans rien
écrire** (ni lignes dans Comptes, ni PDF dans Docs) et montre sa proposition dans un tableau façon
Excel, une ligne par relevé : **Fichier | À quoi il correspond | Compte | Rangé dans** (« Compte
courant …20401, oct. 2025 » ; étiquettes « déjà importé », « ignoré » pour un fichier qui n'est pas un
relevé ; « Rangé dans » = « 2023-2024 › 401 », étiquette « saison créée » quand l'import la crée).
**Saison passée à créer** (Seb, 9/11) : au-dessus du tableau, « Saison 2023-2024 à créer, comme dans Admin ›
Saisons (sans rien recopier) : du … au … », dates proposées avec les mêmes jour et mois de début que les
saisons de l'école (1er septembre à défaut), sur un an, raccourcie si elle chevaucherait la suivante,
modifiables ; créée à Valider seulement (refusée : message, la revue reste ouverte). Le
compte est deviné par le numéro lu sur le relevé (ou contenu dans l'IBAN d'un compte relié à la
banque) ; un compte inconnu est proposé comme « Nouveau : <nom> » ; il se change dans sa case
(autre compte, « Ne pas importer ») ; « À choisir » bloque Valider. **Valider** importe avec les
comptes choisis et range les PDF (§8, dossiers RELEVES BANCAIRES) ; **Annuler** ne change rien. Sur
téléphone, le tableau glisse vers la gauche. Routes : `POST /finances/import/preview` (lecture),
`POST /finances/import` avec `choices` (un choix par relevé, dans l'ordre).

**Grille des relevés (Seb, 9 novembre 2026 ; maquette https://claude.ai/artifact/5T8GbmNkh9UsnXKYC1krep)** :
Comptes › ⋯ › **Relevés**, plein écran avec « ← Comptes ». Une puce par saison (pastille rouge si un
relevé y manque), puis un tableau une ligne par compte, une case par mois de la saison :
✓ vert = couvert par un relevé (toucher ouvre son PDF dans Docs) ; – vert clair = **aucun mouvement**,
le relevé suivant repart du même solde (un livret n'a pas de relevé les mois sans opération) ;
! rouge = **il manque un relevé**, les soldes de deux relevés ne se suivent pas ; ↓ orange = après le
dernier relevé, la banque reliée montre des opérations ce mois-là (relevé à importer) ; ? gris = après
le dernier relevé, **en attente du prochain** (on ne peut pas savoir avant lui s'il y a eu du
mouvement) ; vide = avant le premier relevé importé ou mois à venir. Dessous : « Il manque N relevés
en <saison> : … » et le bouton Importer des relevés. Route : `GET /finances/statements/calendar`.

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
  recherche dans tout ce que montre la ligne (dates d'opération et de valeur, libellé, détail, catégorie, montant — « 276 » trouve −276,00 € —, compte, compte du plan comptable, pièce), sans accents. Avec un filtre : nombre d'opérations,
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
  le numéro lu sur les relevés), **compte au Grand livre** (modifiable), nature, banque reliée ou
  non, périodes couvertes par les relevés. Le clic sur une pastille garde son rôle (choisir le
  compte affiché).
- **Compte au Grand livre** (Seb, 10 novembre 2026, simulation 2024-25) : chaque compte bancaire
  est 512 + son rang (5121, 5122…) ; la trésorière peut lui donner le numéro de son ancien
  logiciel (5123, 5124, 5125 chez EBP) pour que la Balance et le Grand livre se lisent pareil
  (`fin_accounts.ledger_number`). 512 suivi de chiffres, jamais le numéro d'un autre compte ; le
  journal de banque suit (BQ + dernier chiffre). À faire avant de saisir les soldes de départ,
  qui portent le numéro.
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

**Lecture automatique et rappel (codés le 10 novembre 2026)** : le programme de fond
(`app.relance_worker`) regarde toutes les 15 minutes et relit une organisation dont la dernière
lecture a plus de 12 heures (deux lectures par jour, les banques en tolèrent quatre) ; une erreur
reste dans le volet (« dernière erreur »), le tour suivant réessaie. Une semaine avant la fin de
l'accès, les personnes qui ont le droit Financier reçoivent une notification « Accès à la banque
bientôt expiré » (une fois par accès : `expiry_reminded_at`, remis par une reconnexion). Le
conteneur du programme de fond doit voir la clé (volume `/run/secrets`, comme `backend`).

Pas encore fait : lecture des relevés PDF du CIC (écrite pour le Crédit Mutuel, à vérifier).

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

Pas d'action pour importer des relevés : il faut un fichier, que l'assistant ne transmet pas
aux actions.

**Tout le Financier ouvert à l'assistant (Seb, 30 octobre 2026).** Le code est dans
`finances_contretemps/lectures.py`, et Pièces dans `notes_frais_contretemps/actions.py`.

- **Lectures** (réponse sans carte, en JSON calculé par l'appli) :
  - le plan des écrans et des boutons, et les règles de l'appli (à classer, Simple / Complet,
    lettrage) : `finances_contretemps/guide.md`, lu par l'outil `app_guide` de l'assistant ;
  - `finance_bank_accounts`, `finance_operations` (filtres saison, dates, libellé, compte du
    plan, sans compte, sans pièce), `finance_operation` (fiche et écritures d'une ligne) ;
  - `finance_chart` ;
  - `finance_reports`, `finance_report` (contenu du bilan, analyse, rapport financier rédigé) ;
  - `finance_ag_document` (synthèse, balance, grand livre, honoraires) ;
  - `finance_assemblies`, `finance_assembly_slides` (texte de chaque diapo) ;
  - `finance_forecasts` ;
  - `expense_notes` (pièces à valider, à payer, terminées).
- **Écritures** (carte Faire / Annuler) :
  - `set_operation_accounts` : confirmer le compte de lignes choisies par numéro ou par
    libellé ; sans compte donné, l'appli confirme ses propositions ;
  - `recalculate_financial_report`, `write_financial_statement`, `store_ag_document` ;
  - `edit_chart_account` (ajouter, renommer, mots-clés, activer), `delete_chart_account`
    (supprime un compte jamais utilisé, désactive sinon ; un compte de tiers est toujours désactivé,
    jamais supprimé : son numéro reste pris, Seb 10 novembre), `set_accounting_level` (Complet,
    sans retour) ;
  - `review_expense_notes` : valider et refuser plusieurs pièces sur une seule carte. On
    demande « propose-moi les validations » ; l'assistant lit les pièces à valider, explique
    chaque proposition, puis présente la carte ;
  - `mark_expense_notes_paid`.
- **Laissés aux écrans** (gestes rares) : clôture, soldes de départ, import de relevés et
  connexion à la banque.

## 8. Pièces et comptabilité (28 octobre 2026)

Étude « documents comptables de l'AG » (fil du 28 octobre, maquette validée par Seb :
https://claude.ai/artifact/5nieoHKtypLrvyrgnsuPaM). Point de départ : les quatre documents que
la trésorière de Contretemps (comptable de métier) produit pour l'AG, édités le 9 novembre 2025
par son logiciel comptable pour 2024-25 : **Balance**, **Grand livre**, **Rapport financier**
(Word) et **Synthèse Dépenses-Recettes** (Excel). Ce sont les modèles de forme à reproduire.

**Dossiers de Docs › Privé › Saison › Financier (Seb, 30 octobre 2026)**, noms en majuscules sans
accent, créés vides par l'appli quand un trésorier ouvre le Financier (saison en cours et saisons
ouvertes ; une demande à la fois, sinon les demandes simultanées de l'écran créaient « ACHATS (2) »,
« ACHATS (3) », Seb 9/11) :

- **RELEVES BANCAIRES** › un dossier par compte en banque (le nom de sa puce dans Comptes) : le PDF de
  chaque relevé importé y est rangé, dans la saison de sa date de fin ; une saison passée absente est
  créée avec les dates validées dans la revue de l'import (§3.1 ; la saison qui contient la date de fin,
  un relevé du 31 août va dans la saison qui se termine) ; une saison terminée et fermée le reçoit aussi (Seb, 9/11 : on archive le
  document de la banque, les comptes de la saison ne changent pas). Le dossier est celui du compte
  validé dans la revue de l'import (§3.1).
  Réimporter un relevé déjà importé range son PDF sans recréer ses lignes : c'est ainsi qu'on range les
  relevés importés avant le 30 octobre (leur PDF n'avait pas été gardé).
- **ACHATS** › un dossier par mois de la pièce, « MM.AAAA » (« 08.2026 »), créé avec la première pièce
  du mois : les achats payés avec les comptes de l'association.
- **HONORAIRES** › un dossier par prof, « PRENOM NOM » › un dossier par note d'honoraires (une note
  regroupe des dépenses, une par facture, comme une note de frais).
- **Notes de frais** : inchangé (par personne, puis par note).
- **VENTES** › **COTISATIONS**, **COURS**, **PARTICIPATION GALA** (vides : pas encore de pièces de vente).

Les pièces rangées avant le 30 octobre restent dans les anciens dossiers « Achats » et « Honoraires ».

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
**Nature libre** (Seb, 10 novembre 2026) : dans la fiche d'un compte, Nature › « Autre nature… », un
nom au choix (« Immobilisations »), puis « Pour le résultat, ce compte est » : une dépense, une recette,
ou hors résultat (Balance et Grand livre seulement, nature de base « attente »). Le calcul suit la nature
de base ; le nom (`fin_chart_accounts.nature_label`) groupe les comptes dans le Plan comptable et se
propose ensuite dans le menu Nature. Gardé par la copie mémorisée du plan.
Le menu Nature propose aussi les **rubriques du plan comptable des associations** (règlement ANC
2018-06 : « 21 Immobilisations corporelles », « 61 Services extérieurs », « 75 Cotisations, dons… »,
« 86-87 Contributions volontaires en nature » ; `finances/chart.py`, `OFFICIAL_NATURES`), chacune déjà
réglée d'après son numéro : 6 dépense, 7 recette, le reste hors résultat. Pour un nouveau compte hors
classes 6 et 7, la rubrique se propose d'après le numéro tapé (2183 → 21 Immobilisations corporelles).
**Classes** (Seb, 10/11) : le Plan comptable s'affiche par classe (premier chiffre du numéro : Classe 1
Capitaux… Classe 7 Produits, 8 Contributions volontaires ; `CLASSES` dans `chart.py`), puis par nature dans
la classe. Une nature appartient à la classe des comptes qui la portent : dans la fiche, le menu Nature
ne montre que les rubriques et natures de la classe du numéro, et « Créer une nature dans la classe N… »
en crée une (nom libre ; « pour le résultat » réglé d'après la classe, modifiable).

Les catégories par mots-clés de §3.2 (`categories.py`) restent pour l'écran Comptes ; chaque
compte du plan porte ses mots-clés de proposition (repris et enrichis par l'historique confirmé :
même fournisseur → même compte). Pas de « type » à l'écran : on dit « compte » et « nature ».

### 8.3 Pièces (sous-onglet)

Financier › **Pièces** : le classeur des justificatifs. Puces **Achats** · **Honoraires** ·
**Notes de frais** · **Ventes** : les quatre dossiers de l'association dans Docs (ci-dessus), ni
plus ni moins, qui donnent le journal (AC, HO, NF, VE) ; plus **Virements**. La puce À rattacher
a quitté Pièces le 31 octobre (Seb : une pièce n'est pas une ligne de banque) : les lignes sans
compte se traitent dans Comptes (« Sans compte »), avec le badge sur le sous-onglet Comptes, saison
en cours. Sur téléphone, les cinq puces tiennent en deux lignes de trois, sans défiler. **Badges (Seb, 29/10)** : une pastille ronde
compte ce qui attend une action de la personne qui regarde, rien quand c'est zéro ; Achats,
Honoraires et Notes de frais = À valider ; Virements = À payer, Préparés pour elle, Envoyés vus sur
le compte ; le sous-onglet Pièces montre la somme. Pas comptés : Refusé et Brouillon (au membre),
Envoyé pas encore vu (la banque), Payé. Bouton principal
**+** (voir §8.3 bis « Établir une dépense ») : Photo du ticket, Choisir un fichier, ou « Choisir
dans Docs » (PDF reçu par mail). Chaque photo est un fichier du dossier
Docs › Privé › Saison <saison> › Financier › <dossier>, nommé par l'appli
(« 2025-02-09 Facture Amazon 39,90.jpg », voir notes-de-frais.md §7 bis « Nom des fichiers ») une fois lue. **La saison est celle de la date de la pièce**
(date de la facture, pas du paiement : une charge appartient à l'exercice de sa facture, Seb
29/10), **tant que cette saison n'est pas clôturée au Financier** (§8.7) : les trésoriers
travaillent sur l'ancienne saison pendant la nouvelle, sans rien rouvrir dans Admin › Saisons
(Seb, 1er/11 ; l'appli range dans le Financier d'une saison terminée même si son dossier Docs est en
lecture seule pour les gens). Saison clôturée : la pièce va dans la saison en cours et sa fiche le
dit (« Saison de la pièce clôturée au Financier : rangée dans la saison en cours ») ; rouvrir la
clôture si on y tient. Date, personne ou fournisseur corrigé : le fichier suit (dossier et nom) ; une photo pas encore lue attend dans Ventes
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
ou dit **Pas encore payée** / **Payée en espèces**. Rien n'est rattaché sans confirmation, **sauf**
quand la ligne est sûre (même montant et même nom, Seb 31 octobre : « la banque décide »,
`notes-de-frais.md` §7 quinquies) : rattachée toute seule, la pièce attend « Valider : Payé » d'un
trésorier, détachable tant que la saison n'est pas clôturée ; la ligne garde « proposé par l'assistant, confirmé par X le … ». Le montant lu sert à chercher la
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

Financier › Pièces › puce **Virements** (première puce, avant À rattacher ; badge = ce qui
reste à faire, voir ci-dessus). Quatre états, une partie chacun, qui se déroule et se replie (À payer ouvert,
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

Marche arrière (Seb, 31 octobre) : un trésorier ramène une pièce une étape en arrière ou l'annule
(`notes-de-frais.md` §7 quinquies) ; jamais une pièce Payé rattachée à la ligne du compte sans la
détacher d'abord. Toute dépense commence **À valider**, dès qu'elle est établie. Les notes de frais suivent cette
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

**Depuis le 31 octobre** (`notes-de-frais.md` §7 quinquies) : le « + » ne demande plus la nature,
on photographie d'abord (rafale ou paquet de fichiers), l'appli lit et **propose** la nature (prof →
Honoraires, autre personne → Note de frais, personne → Achat) et la ligne du compte qui la paie ;
puis revue pièce par pièce. Ce qui suit décrit l'étape d'avant.

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
sur la ligne de la dépense : dans Docs le fichier n'a pas de badge et ne change pas. **L'appli ne
range dans Docs que les fichiers qu'on lui donne** (Seb, 10 novembre) : plus de PDF récapitulatif
rangé au paiement ; il se fait seulement sur demande (« Télécharger »). Plus d'enveloppes à part sur le disque du serveur (`NOTES_FRAIS_DIR`)
: Docs range déjà ses fichiers sur le disque. Chemins :
- Notes de frais : `Notes de frais › <n° personne> <Nom> › <date> <titre> (<n°>)`, comme aujourd'hui ;
- Honoraires : par personne aussi, `Honoraires › <n° personne> <Nom> › <date> <titre> (<n°>)` ;
- Achats : pas par personne, `Achats › <date> <fournisseur> <montant>` (le fichier lui-même, comme
  « 2025-02-09 Facture Amazon 39,90.jpg » de §8.3 ; un dossier seulement quand l'achat a plusieurs pièces).

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

### 8.3 ter Catégories des pièces = plan comptable (Seb, 30 octobre 2026)

Les catégories des dépenses (notes de frais, honoraires, achats) sont les **comptes de charges
actifs du plan comptable** (classe 6, chez Contretemps de 6063 Autres fournitures à 658 Charges
diverses de gestion), dans l'ordre des numéros (`nf_categories.code` = numéro du compte, port
`Ports.plan` du module Notes de frais). Ajouter, renommer ou retirer un compte de charges change la
liste ; les anciennes catégories libres sont désactivées et restent sur les anciennes dépenses. Dans
Pièces, la fiche d'un achat ou d'honoraires a un champ Catégorie et un **crayon** qui ouvre le plan
comptable. Une pièce dont toutes les dépenses ont la même catégorie fait **proposer ce compte** sur
la ligne de banque qui la paie (« la pièce « Castorama » est classée dans ce compte »), avant
l'historique et les mots-clés. Ventes : leurs catégories seront les comptes de produits (classe 7,
756 Cotisations à 768 Intérêts du livret) quand les pièces de vente existeront ; aujourd'hui une
vente est une ligne de banque dont on confirme le compte de produits.

### 8.4 Comptes : compte et pièce sur chaque ligne

Comptes se filtre par catégorie, par **mois** (menu « Tous les mois » : chaque mois depuis la
première opération, le plus récent en tête ; Seb, 10 novembre 2026) et par recherche ; les
filtres se cumulent et le graphique montre alors le cumul des opérations retenues.
Dans Comptes › Tableau, chaque opération porte son **compte** (ou « Compte à choisir ») et sa
**pièce** (ou « sans pièce ») ; puces **Sans compte** et **Sans pièce** avec compteur. Un appui
ouvre la **fiche de l'opération** : compte (proposé, à confirmer), pièce (changer, détacher,
photographier, choisir dans Docs), et, en Complet, les **écritures** générées (achat du jour de la
facture : 6xx contre 401 ; paiement : 401 contre 512x ; lettre de rapprochement ; virement entre
deux comptes : 512a contre **580 Virements internes**, puis 580 contre 512b, forme des logiciels
de comptabilité, Seb 10 novembre 2026 ; en Simple, 512a contre 512b). Une ligne
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
| Grand livre | PDF, format comptable standard (celui du logiciel de la trésorière, 10 novembre 2026) : bandeau nom de l'association + « Édition du », titre et période, « Comptes … à … », « Devise : EUR » ; un bloc par compte (numéro, libellé) avec Type (cadenas = validée par la clôture), date, journal, pièce (numéro de pièce), libellé, lettre, débit, crédit, solde ; « Total pour le compte n » ; « Total du Grand-Livre » | Complet |
| Balance | PDF, même en-tête ; colonnes N° Compte, Intitulé, Total Période (débit, crédit), Solde Période (débit, crédit) ; « Total des comptes de Bilan » (classes 1 à 5), « Total des comptes de Résultat » (6 et 7), « Total de la Balance » | Complet |
| Bilan actif-passif | PDF, au dernier jour de la saison, forme simplifiée des petites associations (PCA 2018) : **actif** = soldes débiteurs des comptes de bilan (créances 4xx, trésorerie 5xx), **passif** = fonds associatifs (comptes 1, report à nouveau, **résultat de la saison** porté ici) et dettes (soldes créditeurs 4xx) ; totaux égaux, sinon l'écart est écrit (ligne sans compte, soldes de départ incomplets). Codé le 10 novembre 2026 | Complet |
| Honoraires par professeur | Excel : total par prof et par mois, pour la DAS-2 | Complet |
| FEC | Fichier des écritures comptables (art. A47 A-1 du LPF) : texte, 18 colonnes séparées par une tabulation, dates AAAAMMJJ, montants à virgule, ISO-8859-15. Les écritures du Grand livre (§8.7), regroupées en écritures numérotées par date (même journal, même jour, même opération ; les à-nouveaux en une seule). Pièce vide : le numéro d'écriture. Comptes de tiers dans CompteNum (pas de CompAux pour l'instant) | Simple |

**Écran Balance** (Seb et la trésorière, 10 novembre 2026 ; maquette
https://claude.ai/artifact/N1EtPWMPcDvo381hcZyB3M) : Comptes › ⋯ › **Balance**, à tout moment, pas
seulement à l'AG, et par la puce **« Balance »** à côté de Graphique et Tableau (Seb 12/11, à la place du
bouton « Voir la Balance » ; visible aussi dans le volet Comptes à côté du bilan). Recalculée **chaque fois qu'on ouvre l'écran** avec tout ce qui est enregistré
(rien n'est figé ni rangé dans Docs). La **période est dite en clair** sous le titre (« Période : du
1er septembre 2025 au 31 août 2026 »), avec la date des dernières transactions bancaires connues si
elle est plus tôt. Saison par défaut : **la dernière saison terminée si elle n'est pas clôturée** (celle dont on
prépare le bilan ; les vieilles saisons des relevés jamais clôturées ne comptent pas, Seb 10/11), sinon la saison en cours ; menu Saison, dates Du / Au pour
regarder une partie de la saison (bornées à la saison). Puces Tous les comptes / Bilan (classes 1 à
5) / Résultat (classes 6 et 7) ; tableau par classe, colonnes Compte, Libellé, Total période (débit,
crédit), Solde (débit, crédit), total par classe, totaux de Bilan, de Résultat et de la Balance ; un
compte touché montre ses écritures (date, pièce, libellé, débit, crédit, lettre) comme au Grand
livre, et **une pièce touchée ouvre sa fiche** par-dessus la Balance (la fermer y revient) ; « ✓ Équilibrée » ou l'écart. « Télécharger le PDF » : la Balance ci-dessus pour la même
période (téléchargée, pas rangée dans Docs). Les deux niveaux (Simple : trésorerie contre charges
et produits). API : `GET /finances/balance?season_id&start&end`, `GET /finances/balance/pdf`.

**Contrôle du FEC** (Seb, 30/10) : sous la ligne FEC, « FEC juste : n écritures équilibrées » ou
« FEC à corriger » avec la liste : écritures déséquilibrées, débit ≠ crédit, lignes à classer
(65900 / 75900 : Comptes › Sans compte), écritures hors saison, numéros hors plan (classe 1 à 7,
3 chiffres au moins), comptes sans libellé, lettrage qui ne s'équilibre pas. À savoir sans être
faux : niveau Simple (trésorerie, sans tiers ni lettrage), pas d'à-nouveaux. L'assistant le lit
(`finance_ag_document`, document `fec`). Pas d'œil pour le FEC (fichier texte) : téléchargement
et Docs. À venir : import du FEC d'EBP (plan, tiers, à-nouveaux, rapprochement des lignes) quand la
trésorière aura donné le sien.

**Cap (Seb, 30/10)** : un logiciel de comptabilité aux normes françaises des associations (plan
comptable associatif, règlement ANC 2018-06, partie double, FEC), comme EBP ; pas d'IFRS. Reste à
faire pour y arriver : validation des écritures (irréversible, numérotation continue), écritures
saisies à la main (OD), lettrage à la main, bilan actif / passif, amortissements.

Les fichiers vont dans Docs › Privé › Saison <saison> › Financier › AG, avec le badge Brouillon / Validé /
Officiel du bilan ; l'AG (§5) les joint à la convocation.

À l'écran (Seb, 29/10) : le bilan produit est replié, il se déplie d'un toucher sur « Résultat ». Chaque
document a un œil (le fichier est produit, rangé dans Docs et ouvert comme dans Docs : Word et Excel dans
OnlyOffice, PDF dans la visionneuse du téléphone), un téléchargement et une icône Docs qui ouvre
Financier › AG.
Fermer l'aperçu (←) ramène au Bilan, sur le même bilan, aux Documents de l'AG (Seb, 29/10).

### 8.7 Complet : écritures, soldes de départ, clôture

- **Écritures** : journaux AN/AC/HO/NF/BQn/CA (date, pièce, libellé, lettre ; compte, débit,
  crédit en centimes, opération bancaire ou ligne de caisse d'origine). **Décision du 29 octobre
  2026** : elles ne sont pas stockées (pas de `fin_entries`) mais recalculées à chaque fois depuis
  les lignes de banque, de caisse, les comptes confirmés et les pièces (`ag_documents.books`) :
  toujours justes, rien à régénérer en passant de Simple à Complet. Seules la clôture
  (`fin_closings`), les soldes de départ (`fin_opening_balances`) et les écritures à la main du
  trésorier (`fin_manual_entries`, journal OD, §8.10 étape 4 : 411, 471) sont écrites.
- **Soldes de départ** (Comptes ⋯ › Soldes de départ, et Bilan › Préparer étape 2) : première saison
  dans l'appli, repris de la Balance de l'an dernier déposée dans Docs ; saisons suivantes : reportés
  par la clôture. **Règle (Seb, 10 novembre 2026, « que ferait un pro »)** : les soldes de départ sont
  les soldes de clôture de l'an dernier pour tous les comptes de bilan (banques, caisse, dettes 401 /
  467x, créances 411, fonds et report) ; les relevés ne servent qu'à **vérifier** les 512x. **Sous
  chaque solde qui n'est pas à zéro, une phrase dit ce qu'il veut dire** (Seb, 10/11 ; règles fixes du
  plan, jamais un chiffre inventé) : banque / caisse « l'argent au <veille> », ✓ si égal aux relevés ;
  401 « factures reçues, pas encore payées », avec les pièces non payées datées d'avant la saison
  (« donnent exactement ce total » quand c'est le cas) ; 467x ce que l'on devait à la personne ; 411 ce
  que des adhérents devaient ; 471 en orange « argent pas encore classé : un compte d'attente doit être
  vide, demandez à la trésorière » ; 110 « les fonds de l'association ». Piste en plus : une transaction
  bancaire des trois premiers mois du même montant (« Transaction bancaire du même montant : date,
  libellé ») ; `GET /finances/opening-balances/{saison}` rend `earlyTransactions` et `unpaidBefore`. Tant que
  rien n'est repris, l'appli ne connaît que la trésorerie des relevés : l'écran le dit en orange
  (« les soldes de l'an dernier ne sont pas encore repris ») et l'étape 2 de Préparer reste à faire au
  niveau Complet (`toCarry`). **« Reprendre les soldes de la Balance <saison précédente> (Docs › Financier) »** (le
  bouton nomme sa source, Seb 10/11 ; `GET
  /finances/opening-balances/{saison}/previous`) : l'appli cherche dans Docs › saison précédente ›
  Financier (tous sous-dossiers), sinon dans le Financier de la saison en cours (le dossier d'une
  saison terminée est en lecture seule à l'écran), le PDF le plus récent dont le nom contient « balance », lit ses
  colonnes Solde Débit / Crédit (`finances/balance_reader.py`, format d'EBP et le nôtre) ; si les
  colonnes ne se lisent pas (autre logiciel, scan, photo), le même lecteur que les factures lit le
  document et l'écran dit « lus par l'appli : à vérifier ligne par ligne ». Ne sont proposés que les
  comptes de bilan à solde non nul, hors 110 / 120 / 129 que l'équilibre recalcule. Les cases se
  remplissent, la vérification des 512x contre les relevés s'affiche (écart = chèque pas encore
  débité ou erreur, à expliquer), et **rien n'est écrit avant « Utiliser ces soldes »**. Sans Balance
  dans Docs : le message dit où la déposer, et les cases se remplissent à la main.
- **Clôture** (Bilan, bilan Officiel) : résultat reporté (120 / 129 → 110), écritures d'à-nouveaux
  de la saison suivante, saison verrouillée (plus de rattachement sans la rouvrir, trace gardée).
  **Le cadenas (10 novembre 2026, modèle EBP)** : la clôture **valide** toutes les écritures de la
  saison. Tant qu'elle n'est pas rouverte : aucun compte ne change sur une transaction bancaire ou
  une ligne de caisse de la saison (déjà), aucune pièce ne s'y rattache ni ne s'en détache (le
  rattachement automatique à l'import d'une pièce s'abstient aussi), un relevé dont la période touche
  la saison n'entre pas (compte rendu d'import : « Saison clôturée le … »). À l'écran : cadenas sur
  les lignes de Comptes des saisons clôturées, bandeau et Enregistrer grisé dans la fiche de la
  transaction ; Grand livre : colonne **Type** avec le cadenas sur chaque écriture et « Écritures
  validées par la clôture du … » en tête ; FEC : `ValidDate` = la date de la clôture (sinon la date
  de l'écriture). Bilan › Clôture garde la trace des clôtures rouvertes (« Clôturée le …, rouverte
  le … »). Pas de validation écriture par écriture : la saison se valide d'un bloc.
- **Un compte manque au plan (10 novembre 2026)** : depuis la fiche d'une pièce (« Modifier les
  catégories ») comme depuis la fiche d'une transaction bancaire (crayon à côté de « Compte »), le
  Plan comptable s'ouvre à la place de la fiche ; fermer revient à la saisie en cours, le nouveau
  compte dans la liste. Le plan s'enrichit au fil du classement, sans interrompre la tâche.
- **Numéro de pièce (10 novembre 2026, modèle EBP : colonne Pièce)** : chaque pièce reçoit à sa
  validation un numéro par saison et par journal, « AC-2025-001 » (AC achats, HO honoraires, NF
  notes de frais ; saison = septembre → août, l'année du début), donné une fois, jamais repris ni
  réattribué (`nf_notes.piece_number`). Il s'affiche sur la fiche de la pièce (« Pièce n° … »), dans la
  colonne Pièce du Grand livre et dans `PieceRef` du FEC ; sans numéro (pièce pas encore validée), le
  titre de la pièce. Le nom du fichier dans Docs ne change pas. **Numéro saisi** (Seb, 10 novembre) :
  la fiche d'une pièce (saisie à la main ou à vérifier) a un champ facultatif « Numéro de pièce » ;
  rempli, il remplace le numéro de l'appli (unique dans l'école, 20 caractères, majuscules
  indifférentes) ; vide, l'appli numérote à la validation, saisie à la main validée d'un coup comprise.
- **Comptes de tiers des profs (10 novembre 2026)** : une facture d'honoraires va au compte 467x
  dont le libellé porte le nom du prof. Un prof qui n'en a pas encore : à sa première facture, les
  livres créent « 467n Honoraires Nom » au prochain numéro libre (jamais le compte d'un autre prof).
  Un prof parti : on **désactive** son compte (case « Compte actif » du Plan comptable) ; Retirer
  sur un compte de tiers fait la même chose, un numéro de tiers ne se libère jamais, l'histoire du
  prof reste dans les Grands livres passés et dans la comparaison N-1.
- **Repartir à zéro sur cette saison (10 novembre 2026)** : Seb s'exerce sans la trésorière, se
  trompe, recommence. Bilan › Clôture, bouton « Repartir à zéro », le nom de la saison retapé
  confirme (trésorier seulement, `POST /finances/seasons/{id}/reset`). Pour la saison choisie
  seulement, **part** : les pièces datées de la saison quel que soit leur état (défaites comme
  « Annuler cette pièce » : fichiers à la corbeille de Docs, une note envoyée par un membre lui
  revient, numéros de pièce libres) et leurs rapprochements ; les comptes confirmés sur ses
  transactions bancaires et les justifications « sans facture » ; les écritures à la main, les soldes
  de départ, les explications, la clôture ; le plan comptable revient à sa copie mémorisée s'il y en a
  une. **Reste** : relevés et transactions bancaires, comptes en banque (nom, numéro au Grand
  livre), caisse, bilans calculés, autres saisons. Seb (10/11 13h27) : la fenêtre dit tout cela en
  clair, poste par poste, avant « Tout effacer ».
  **Mémoriser le plan comptable** (Comptes › ⋯ › Plan comptable, Seb 10/11 midi) : chaque copie
  entre dans un **journal** (`fin_chart_snapshots` : date, commentaire, comptes) affiché sous
  « Copies du plan » ; le commentaire est pré-rempli avec ce qui a changé depuis la copie précédente,
  calculé par l'appli (« 2 comptes ajoutés (6061 Eau, 6062 Gaz), 1 libellé modifié (606) » ;
  première copie : « Plan de départ »), le trésorier le garde ou le réécrit. Repartir à zéro propose
  la copie à remettre (la plus récente par défaut) ; la remise reprend libellés, natures, mots-clés et
  actif par numéro, recrée les comptes retirés, supprime les comptes ajoutés depuis (inactifs s'ils
  ont servi ailleurs). Sans copie, le plan ne bouge pas. Pas de « tag » plus fin :
  revenir à un instant précis rejouerait aussi Docs et ce que d'autres ont fait entre-temps ; la
  version honnête est une copie de la base sur le VPS.
- **Lettrage** : lettre de trois caractères par paire facture / paiement, comme le modèle ;
  paiement en plusieurs fois accepté (somme). **Depuis le 10 novembre 2026** : la facture entre au
  tiers à son montant (le total des pièces rattachées à la transaction), le paiement au montant de la
  banque ; la lettre n'est posée que si les deux sont égaux, sinon les deux lignes restent ouvertes
  sur le tiers (acompte, écart « à régler » dans la fiche de la pièce : `notes-de-frais.md` §7
  septies) et la charge est au montant de la facture. Un **« Reste dû »** (`settles` dans le port des
  pièces) n'est qu'un paiement de plus sur le tiers : la lettre se pose sur la facture et tous ses
  paiements quand leur somme fait la facture, sinon tout reste ouvert (10 novembre 2026). **Lettrage à la main** : dans Rapprocher,
  « Rattacher à une transaction bancaire… » sur une facture sans paiement ouvre la liste des
  transactions bancaires sans facture de la période (montants les plus proches en premier) ; le
  trésorier choisit, tout débit libre est accepté (`POST …/payee` avec `manuel`), l'écart reste.

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
   **Codée le 29 octobre 2026** (`finances/chart.py`, `finances/accounting.py`, tables `fin_settings`,
   `fin_chart_accounts`, `fin_operation_accounts`, `fin_cash_lines` ; écrans `finances/compta/`) :
   plan par défaut d'une association (`DEFAULT_CHART`) et commande
   `python -m app.plan_comptable_contretemps --ecole <id>` pour les comptes de la Balance 24-25 ;
   compte proposé d'après l'historique confirmé (même libellé sans ses chiffres) puis les mots-clés,
   jamais écrit sans confirmation ; fiche de l'opération avec ventilation (la somme doit faire la
   banque) ; puces Sans compte / Sans pièce ; la pièce d'une ligne = la dépense payée par cette
   opération (`nf_notes.bank_operation_id`) ; badge « Sans compte » sur le sous-onglet Comptes
   (saison en cours) ; caisse avec retrait au distributeur = virement interne ; niveau Simple /
   Complet dans Comptes › ⋯ › Plan comptable et, depuis le 29 octobre, sur la ligne Financier
   d'Admin › École › Personnalisation › Fonctionnalités (« Passer en Complet »). Reste : remise de
   chèques avec une sous-ligne par chèque rapprochée d'une famille, pièce choisie dans Docs ou
   photographiée depuis la ligne de Comptes, pièce sur une ligne de caisse.
1 bis. Virements (§8.3 bis) : puce, quatre états, aide au virement, RIB, Qui paie, notification.
   **Codée le 29 octobre 2026**, dans le module Notes de frais (`nf_notes.nature`, `supplier`,
   `prepared_*`, `payer_id`, `transfer_sent_*`, `bank_operation_id` ; `nf_pieces.doc_node_id` ; table
   `nf_payers` pour Qui paie) : puces Virements, Notes de frais, Honoraires, Achats réelles (À rattacher
   et Ventes restent des exemples) ; « + », rafale, « Encore une page », import de plusieurs fichiers,
   glisser-déposer sur ordinateur (Honoraires, Achats) ; Docs seul rangement et commande
   `python -m app.ranger_notes_frais` pour les anciennes enveloppes ; aide au virement, Qui paie,
   notification ; « Vu sur le compte » et « C'est payé ». Pas de `fin_payees` : le RIB d'un fournisseur
   est sur la pièce et repris du dernier achat chez lui. Reste : « Choisir dans Docs », lecture d'une
   photo de RIB, glisser-déposer sur Notes de frais (il faut « Pour qui ? »), « Ajouter une dépense à
   cette note » pour un achat, virement sans pièce, la pièce visible sur la ligne de Comptes (§8.4),
   la clé d'accès pour le RIB.
2. Documents de l'AG : Synthèse, Grand livre, Balance, Honoraires par prof ; Bilan par compte.
   **Codée le 29 octobre 2026** (`finances/ag_documents.py`, bloc `compta/DocumentsAG.jsx` sous un
   bilan, routes `GET /finances/reports/{id}/documents` et `…/documents/{synthese|balance|grand-livre|honoraires}`) :
   grand livre en mémoire depuis les lignes de banque (compte confirmé contre 512x, une ligne sans
   compte va dans « Dépenses / Recettes à classer ») et la caisse (530 ; un retrait = banque → caisse),
   soldes de départ de la trésorerie repris dans 110 « Report à nouveau » pour que la Balance soit
   équilibrée ; Synthèse par classe (60, 61…), trésorerie, fournisseurs à payer (dépenses validées pas
   encore payées), un bloc par événement ; Balance et Grand livre en PDF ; Honoraires par prof et par
   mois (notes d'honoraires payées) en Excel ; chaque fichier produit est rangé dans Docs › Financier ›
   AG (saison en cours, remplacé à chaque production). Le Bilan additionne par compte confirmé, l'IA ne
   classe plus que les lignes sans compte. Reste : badge Brouillon / Validé / Officiel sur les fichiers,
   dossier de la saison du bilan plutôt que la saison en cours, écritures de tiers (étape 4).
3. Rapport financier (gabarit Word du modèle, texte par le modèle, chiffres par l'appli).
   **Codée le 29 octobre 2026** (`finances/written_report.py`, table `fin_written_reports`, routes
   `GET/POST /finances/reports/{id}/rapport` et `…/rapport/download?format=docx|pdf`, ligne
   « Rapport financier » du bloc Documents de l'AG avec « Rédiger », Voir, Word, PDF) : le modèle
   reçoit les chiffres de la saison et de la précédente (chaque poste de la Synthèse, écart et %,
   totaux, résultat, trésorerie, événements), l'analyse du bilan et les consignes du trésorier ; il
   rédige dans la forme du rapport 2024-25 (introduction, A - Recettes, B - Dépenses, Points à revoir,
   conclusion) en citant les chiffres par des repères `{{clé}}` que l'appli remplace par ses propres
   montants ; un montant ou un pourcentage qu'il aurait écrit lui-même est signalé « à vérifier »
   (comme les diapos de l'AG, §5.1), un repère inconnu est effacé. Le texte est gardé (la dernière
   rédaction fait foi), relu à l'écran, produit en Word (python-docx) et PDF, rangé dans Docs ›
   Financier › AG ; coût noté dans Usage ressources (« rapport financier »). Reste : reprendre le
   gabarit Word de la trésorière tel quel (en-tête, police) plutôt qu'un Word simple, retouche du
   texte à l'écran avant le Word.
4. Complet : écritures, soldes de départ, lettrage, clôture.
   **Codée le 29 octobre 2026** (`ag_documents.py`, tables `fin_opening_balances` et `fin_closings`,
   routes `GET/PUT /finances/opening-balances/{saison}`, `POST/DELETE /finances/reports/{id}/close`,
   `GET /finances/operations/{id}/entries` ; écrans `compta/SoldesDepart.jsx`, bloc Clôture dans
   Documents de l'AG, écritures dans la fiche de l'opération) : au niveau Complet, une ligne de banque
   confirmée qui a une pièce passe par le tiers (achat : 6xx contre 401 le jour de la facture, puis
   401 contre 512x au paiement ; honoraires et notes de frais : 467x, celui dont le libellé porte le
   nom de la personne, sinon le plus court), avec une lettre AAA, AAB… commune aux deux lignes ;
   colonne Lettre du Grand livre. Soldes de départ : Comptes › ⋯ › Soldes de départ, par saison,
   prérempli par la trésorerie des relevés (ou les soldes reportés par la clôture précédente), un
   solde par compte du bilan, « Utiliser ces soldes au <début de la saison> », vérification des 512x contre les relevés,
   différence dans 110. Clôture (Bilan › Documents de l'AG, Complet) : résultat dans 110, soldes des
   comptes de bilan reportés sur la saison suivante, saison verrouillée (rattachement et caisse
   refusés tant qu'elle n'est pas rouverte ; « Rouvrir » garde la trace). Reste : lecture de la
   Balance PDF de l'an dernier pour préremplir, pièces « pas encore payées » dans 401 (elles restent
   dans « Fournisseurs à payer » de la Synthèse), écritures OD de régularisation.

À demander à la trésorière (vendredi 31 octobre) : son logiciel et si elle veut un export vers
lui ; si elle confirme elle-même dans l'appli (compte Trésorier) ; son plan comptable 2025-26 ;
qui tient la caisse ; les 717,50 € du compte d'attente ; qu'une pièce va dans la saison de sa
facture et non de son paiement (comptabilité d'engagement).

### 8.10 Le bilan en parcours (Seb, 9 novembre 2026)

But : produire depuis l'appli les documents de Docs › Privé › Saison › Financier › BILAN FINANCIER
(Balance, Grand-Livre général, Recettes-Dépenses, Rapport financier, plus Honoraires par prof et
FEC), **dans la même forme que ceux de la trésorière** (modèles 2024-25), sans rien de magique :
la trésorière valide point par point. Maquette : https://claude.ai/artifact/SvQXof5zZJRt51t6MLjPrY.
**Comptes ou Pièces à côté du bilan** (Seb, 10/11 ; maquette https://claude.ai/artifact/1LscgY7ak4mT7fKHU4bD4C) :
en tête du Bilan, une rangée « Bilan · Comptes · Pièces · Docs », Bilan à gauche et toujours allumé ; toucher
Comptes, Pièces ou Docs (l'écran Docs de l'appli, donné par l'hôte) l'ouvre à côté (il s'allume aussi), toucher Bilan ou ← referme. Sur ordinateur (≥ 900 px),
un volet s'ouvre à droite dans la même fenêtre, avec son propre fond, un cadre orange et le titre « À côté
du bilan : Comptes » ; la puce Bilan reste choisie, chaque moitié défile seule. La barre orange du milieu se
fait glisser (le volet prend de 25 à 75 % de la largeur), ou ⅓ ½ ⅔ en un geste ; ← referme le volet. Sur
téléphone, l'écran choisi s'ouvre en entier avec « ← Revenir au bilan ».
Contre-calcul indépendant de la saison 2025-26 depuis les relevés PDF du CIC (Balance, Synthèse,
questions) : `appbase/bilan/contre-calcul/` dans les fichiers du projet ; il servira de comparaison
avec ce que l'appli calcule (trésorière avec EBP, appli, contre-calcul : à trois).

**Financier › Bilan** = **Préparer** (sept étapes depuis l'étape de code 6 ci-dessous ; avant : trois onglets Préparer | Documents | Clôture). Préparer = six
étapes sous le titre « Étapes du bilan <saison> », chacune nommée par un verbe à l'infinitif sur la chose
(Seb 10/11), avec son compteur, dans l'ordre ; une étape montre ce qui reste, rien ne se calcule
sans que la trésorière l'ait vu :

1. **Obtenir les relevés** : la grille des relevés (§3) toute verte pour la saison.
2. **Reprendre les soldes de départ** au premier jour de la saison (§8.7) : repris de l'an dernier (ou reportés par
   la clôture) et 512x = relevés ; au Complet, « trésorerie des relevés seulement » reste orange.
3. **Rapprocher les factures et classer les transactions bancaires** (le titre dit quoi, Seb 10/11) :
   l'écran Rapprocher de Pièces (`notes-de-frais.md` §7 septies),
   filtré sur la saison, puis **un compte sur chaque ligne de banque** : d'abord les lignes où
   l'appli n'est pas sûre (proposition en bleu avec « ? », une par une : choisir le compte,
   rattacher la facture qui tranche, ou ventiler une remise de chèques entre Cours / Cotisations /
   Gala), puis les comptes sûrs par le libellé, validés **par compte entier** (« Valider le compte
   6226 Honoraires : 48 lignes »). Un numéro de compte ne s'affiche jamais seul : toujours avec son
   libellé.
4. **Compter la caisse et les factures non payées** : caisse, factures non payées au 31/08 (401), cotisations dues (411), compte
   d'attente (471) ; saisi à la main, une ligne par question.
5. **Passer les contrôles**, affichés en clair : solde de début + mouvements = solde de fin pour chaque compte
   bancaire ; aucune ligne sans compte ; Balance équilibrée ; résultat de la Synthèse = résultat de
   la Balance ; FEC juste. Un contrôle rouge bloque les documents.
6. **Produire les documents** (§8.6) **et comparer à l'an dernier** compte par compte, écart de
   plus de 30 % marqué « ? » : la trésorière l'explique en une ligne (reprise dans le Rapport) ou
   retourne pointer.

**Documents de référence** (question de Seb) : pas « voici un PDF, refais pareil ». Ceux de l'an
dernier servent à trois choses : le plan comptable et les regroupements (déjà installés chez
Contretemps ; pour une autre association, l'assistant les lit et propose un plan que la trésorière
valide), les soldes de départ, et la comparaison N-1. Les documents de l'appli restent un catalogue
fixe paramétré par le plan ; la mise en page suit le gabarit de la trésorière (Rapport : reste à
faire, §8.9 étape 3).

**Pièces** : pas nécessaires au compte d'exploitation (la banque donne tous les montants) ; elles
tranchent le compte des lignes ambiguës (Amazon, Temu, Carrefour), portent les factures non payées
au 31/08 et sont à conserver. Des scans médiocres suffisent (date, montant, fournisseur). Le bilan
n'attend jamais une pièce : une ligne sans pièce reçoit son compte à la main, signalée.

Étapes de code (une PR chacune) :
1. **Codée le 10 novembre 2026** : « Déjà payée » et la puce Rapprocher (`notes-de-frais.md`
   §7 septies), puis « Justifier sans facture » et « Demander le justificatif » (§7 octies).
2. **Codée le 10 novembre 2026** : Bilan en trois onglets **Préparer | Documents | Clôture**
   (`compta/Preparer.jsx`, `GET /finances/seasons/{id}/preparation`,
   `POST /finances/seasons/{id}/confirm-accounts`) : les six étapes avec leur compteur et un ✓ quand
   il ne reste rien ; 1 ouvre la grille des relevés, 2 les soldes de départ, 3 montre les compteurs
   de Rapprocher sur la saison (bouton « Ouvrir Rapprocher les factures ») puis les transactions bancaires sans
   compte : « À confirmer une par une » (aucune proposition : la fiche de l'opération) et « Comptes
   proposés par l'appli » regroupées par compte proposé avec **« Valider le compte 6226 Honoraires :
   48 lignes »** (`Accounting.confirm_many`, une opération déjà classée ou un virement interne est
   ignoré) ; 4 hors banque : texte d'attente ; 5 les contrôles en clair (relevés complets, soldes de
   départ = relevés, un compte sur chaque transaction, FEC juste) ; 6 renvoie à Documents. Documents =
   l'écran des bilans d'avant ; Clôture = la clôture portée par le bilan le plus avancé de la saison
   (Officiel, Validé, dernier), niveau Complet.
3. **Codée le 10 novembre 2026** : étape 4 **Hors banque** = la caisse (solde, renvoi à Comptes ›
   Caisse) et les **factures validées pas encore payées** (`AgPorts.unpaid`, désormais avec date,
   nature, compte de charge et nom) : au niveau Complet, une facture datée de la saison entre en
   charge le jour de la facture contre son tiers (401 / 467x), sans lettre, dans `books()` ; au
   niveau Simple elles restent dans « Fournisseurs à payer » de la Synthèse. Étape 6 **Documents et
   comparaison** : compte par compte, la saison et la précédente (montant, écart, %), **« ? »** quand
   l'écart dépasse 30 % ou que le compte apparaît ou disparaît, jusqu'à ce que la trésorière
   l'explique en une ligne (table `fin_season_notes`, `PUT /finances/seasons/{id}/notes/{numéro}` ;
   vide = effacée) ; le Rapport financier reçoit ces explications (`explicationsDuTresorier`).
   Cinquième contrôle : « Écarts avec la saison précédente expliqués ».
4. **Codée le 10 novembre 2026** : étape 4, **écritures à la main** (journal OD, niveau Complet) :
   ce qui n'est ni sur les relevés ni dans la caisse ni porté par une pièce, comme les cotisations
   dues au 31 août (411 contre 756) ou la régularisation du compte d'attente (471). Une ligne par
   question : date (dans la saison), libellé, compte débité, compte crédité, montant positif (le
   sens est donné par les deux comptes) ; la banque et la caisse refusées (elles passent par les
   relevés et Comptes › Caisse), les deux comptes différents, saison clôturée refusée. Table
   `fin_manual_entries` (la seule écriture stockée, avec la clôture et les soldes de départ ;
   `books()` les prend telles quelles au journal OD, le FEC aussi) ; `GET/POST
   /finances/seasons/{id}/manual-entries`, `DELETE /finances/manual-entries/{id}` ; trésorier
   seulement. Pas de modification : supprimer et refaire.
5. **Codée le 10 novembre 2026** : **remise de chèques** (libellé « REM CHQ », « REMISE DE
   CHEQUES »… : `chart.is_cheque_deposit`). La banque ne dit pas ce que payent les chèques :
   une remise n'est jamais « sûre », l'étape 3 la met dans « À confirmer une par une » avec la
   mention « Remise de chèques : à ventiler entre ses comptes », jamais dans un compte à valider en
   bloc. Sa fiche le rappelle et, dès qu'une remise a déjà été ventilée, propose **« Ventiler comme
   les remises précédentes »** : les comptes des remises passées (du plus fréquent au plus rare,
   `splitSuggestion`), le montant total sur le premier, à répartir ; une part à zéro est ignorée à
   l'enregistrement ; le total doit faire le montant de la banque (règle de §8.4). Pas de
   catégorie « Cours / Cotisations / Gala » codée en dur : ce sont les comptes de l'association.
6. **Codée le 10 novembre 2026** (maquette https://claude.ai/artifact/AQ4jHpBWkybxqEXuXXeN3s) :
   **Préparer en sept étapes, plus d'onglets Documents ni Clôture**. Étape 6 = les documents de la
   saison **d'après ceux de l'an dernier** (Seb : chaque association a les siens) : les fichiers de
   Docs › Financier (saison précédente) rangés dans un dossier dont le nom contient « bilan », à
   toute profondeur (`AgPorts.previous_documents`, `finances/season_documents.py`). Chaque fichier
   est **reconnu d'après son contenu** (haut de la première page d'un PDF, premières lignes d'un
   Excel, d'un Word, d'un texte), puis tout le contenu, puis son nom (quelqu'un a pu prendre des
   libertés avec les noms) : Synthèse, Balance, Grand livre, Bilan actif-passif, Honoraires, FEC,
   Rapport financier, sinon « Autre : à faire à la main ». La trésorière coche ce qu'on refait et
   corrige la nature (« reconnu comme », table `fin_document_choices`, `GET/PUT
   /finances/seasons/{id}/documents`) ; « Ajouter un document que l'appli sait faire » complète.
   Chaque document prend **le nom de celui de l'an dernier, les années avancées d'un an**
   (« Balance 2024-2025.pdf » → « Balance 2025-2026.pdf »), au format que l'appli produit ; sans
   fichier l'an dernier : Synthèse, Balance, Rapport financier. Voir et Télécharger
   (`GET /finances/seasons/{id}/documents/{nature}/file?name=`) ; **rien n'est rangé dans Docs**
   (Seb 10/11) : on dépose soi-même ce qu'on garde. Le Rapport financier se rédige dans le bilan le
   plus avancé de la saison, créé « Officiel » s'il n'y en a pas (`POST
   /finances/seasons/{id}/rapport-report`). Étape 7 = **Clôturer** (§8.7), possible quand les
   étapes 1 à 6 sont vertes (`POST/DELETE /finances/seasons/{id}/close`), avec ce que fait la
   clôture en trois lignes et la trace des clôtures rouvertes. « Repartir à zéro » passe en bas de
   Préparer. La liste des bilans (pour l'AG) reste par ⋯ › Nouveau bilan, avec « ← Étapes du bilan ».
   **Voir sur chaque document** (Seb 13/11) : un PDF dans un nouvel onglet ; un Excel, le Rapport
   (Word) ou le FEC dans OnlyOffice, **en lecture seule et hors de Docs** : le serveur fabrique le
   fichier, le garde une heure dans un dossier temporaire (`APERCUS_DIR`, sinon le dossier temporaire
   du système), OnlyOffice le lit par un lien signé (`GET /bureautique/apercu/{jeton}`), rien ne
   revient. `Bureautique.apercu` est branché sur Financier par `FinancesReceiver(preview=…)`
   (`GET /finances/seasons/{id}/documents/{nature}/preview?name=`,
   `GET /finances/reports/{id}/rapport/preview?name=`) ; sans OnlyOffice : « L'aperçu n'est pas
   configuré sur ce serveur ».
7. Comparaison appli / contre-calcul / EBP sur la saison 2025-26 et corrections.

## 9. Reste à faire

- Connexion bancaire (§3.5) : relevés PDF du CIC.
- Améliorations notées : tableau plus lisible sur téléphone, catégories modifiables, « reste à
  recevoir » HelloAsso, textes ≥ 17 px (l'écran est repris tel quel).
