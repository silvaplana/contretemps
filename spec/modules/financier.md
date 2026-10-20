# AppBase — Module `finances` (onglet Financier)

Version 0.2, 20 octobre 2026. Statut : **décision de Seb, 20 octobre** : reprendre tel quel le
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
3. **Bilan** (§4) — fait, cette version.
4. **Assemblée générale** — à reprendre (`generalassemblies/`, PPT du trésorier).
5. **Prévisionnel** — à reprendre (`forecasts/`).

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

## 5. Reste à faire

- Assemblée générale, Prévisionnel : repris de Sambo Admin, dans cet ordre, une PR chacun.
- Actions de l'Assistant IA pour les quatre sous-modules.
- Connexion bancaire (Enable Banking) quand le contrat est réglé.
- Améliorations notées : tableau plus lisible sur téléphone, catégories modifiables, « reste à
  recevoir » HelloAsso, textes ≥ 17 px (l'écran est repris tel quel).
