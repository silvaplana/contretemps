# AppBase — Module `finances` (onglet Financier)

Version 0.3, 20 octobre 2026. Statut : **décision de Seb, 20 octobre** : reprendre tel quel le
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
2. **Notes de frais** (`notes-de-frais.md`) — fait.
3. **Bilan** (§4) — fait.
4. **Assemblée générale** (§5) — fait.
5. **Prévisionnel** (§6) — fait, cette version.

Chaque sous-module expose ses actions à l'Assistant IA (`assistant-ia.md` §3, `actions.py`) : cible
de Seb, « fais-moi le PPT de l'AG de cette année à partir de celui de l'année dernière et du bilan
financier de cette année ». À faire une fois les quatre sous-modules repris.

## 3. Comptes

### 3.1 Le relevé fait foi

Le trésorier dépose les **relevés PDF de la banque** (Crédit Mutuel : compte courant, Livret Bleu),
un par un ou en archive (zip, 7z, tar), depuis le menu **⋯ › Importer des relevés**. Chaque relevé
est lu mot à mot (position sur la page) et **vérifié au centime** : solde de début + opérations =
solde de fin, sinon il est refusé avec le message de la banque. Un relevé déjà importé (même compte,
même période) est ignoré : on peut redéposer toute une archive. Le compte rendu de l'import
(importés, déjà présents, refusés) s'affiche dans l'écran.

Pas de saisie manuelle d'opérations. Pas d'import CSV pour l'instant (un CSV n'a pas de soldes à
vérifier). La **connexion bancaire** (Enable Banking, opérations provisoires « en attente du
relevé ») est prévue dans les tables (`source`) mais pas branchée : contrat à régler.

### 3.2 L'écran

Repris de Sambo Admin :

- En-tête : **Total des comptes** (ou le compte choisi), solde par compte, « au jj/mm/aaaa ».
- Puces : comptes affichés (CC + Bleu | CC | Bleu), **Graphique** | **Tableau**.
- Filtres : menu Catégories (toutes, les 5 plus fréquentes, les 5 plus grosses, une catégorie) et
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

## 7. Reste à faire

- Actions de l'Assistant IA pour les quatre sous-modules.
- Connexion bancaire (Enable Banking) quand le contrat est réglé.
- Améliorations notées : tableau plus lisible sur téléphone, catégories modifiables, « reste à
  recevoir » HelloAsso, textes ≥ 17 px (l'écran est repris tel quel).
