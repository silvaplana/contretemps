# AppBase — Sous-module `auto_import` (Financier › Pièces) : Import auto pièces

Version 0.1 du 19 novembre 2026. Demande de Seb (fil « Sous-module : Import auto pièces ») :
des pièces (factures, ventes, notes de frais, honoraires) qui **arrivent toutes seules** : un
fichier déposé dans un dossier de Docs ou d'un drive, un mail reçu dans la boîte du club, un
versement HelloAsso devient une pièce de Financier › Pièces, sans la saisir. Maquettes validées
par Seb le 19 novembre : l'écran https://claude.ai/artifact/PetMSgswm6ZVCH9Wnthqbe et la ligne
des drives dans Connexions https://claude.ai/artifact/4iDZBj38yrRLm31RR9ERyt (`core.md` §3,
« Drives du club »). **Pas codé.**

## 1. Ce que fait le sous-module

Un **import** est un processus réglé une fois : « regarde tel dossier (ou telle boîte) à tel
rythme, et chaque nouveau fichier devient une pièce de telle nature, À valider ». L'appli regarde
la source, lit chaque nouveau fichier avec le lecteur des factures (`notes_frais/lecture.py`,
celui du « + » de Pièces) et crée la pièce. La trésorière la retrouve dans Pièces, À valider,
comme une pièce saisie à la main : rien d'autre ne change dans Pièces, Rapprocher ni le Bilan.

Sous-module optionnel du Financier, **éteint par défaut**, allumé à ASC La Ciotat (écoles de
nature « combat », comme Mail). **Contretemps ne change pas** (saisie à la main sur papier) :
éteint, aucune entrée de menu, aucune ligne, aucune écriture. Tests à chaque PR : une école sans
le sous-module garde exactement ses écrans et ses pièces.

## 2. Où il se trouve

- **Financier › Pièces › ⋯** : entrée **« Import auto pièces »**, pour qui a l'Accès au Financier
  (Seb, 19 novembre).
- **Admin › École › Personnalisation › Fonctionnalités** : case « Import auto pièces » en retrait
  sous Financier (`requires=("finances",)`).
- Les sources viennent des connexions de l'école (Admin › École › Connexions) : **Drives du club**
  (`core.md` §3), **Boîte mail du club** (`mail.md` §4), **HelloAsso** (`helloasso.md`). Une source
  pas connectée n'est pas proposée.

## 3. L'écran Import auto pièces

Plein écran, titre « Import auto pièces », **croix en haut à droite** pour revenir à Pièces.

Un tableau, une ligne par import :

| Actif | Nom | Saison | Pièces | | |
|---|---|---|---|---|---|
| case | « Salaire du coach » | 2025-2026 | 3 | Voir | 🗑 |

- **Actif** : case à cocher ; décochée, l'import ne regarde plus sa source (les pièces déjà créées
  restent). Le nom et la saison passent en gris.
- **Saison** : la saison des pièces créées ; l'import ne prend que les fichiers et mails **datés
  dans cette saison** (date lue dans le fichier, sinon date du fichier ou du mail).
- **Pièces** : le nombre de pièces que l'import a créées. **Voir** (s'il y en a) ouvre la liste de
  ces pièces, avec en tête où sont leurs fichiers : dans la destination s'il y en a une, sinon
  dans la source ; toucher une pièce ouvre sa fiche dans Pièces.
- **🗑** efface **l'import, jamais les pièces** qu'il a créées : « Import « … » effacé. Les pièces
  déjà créées restent. », Annuler 10 s.
- **« + »** en bas à droite : un nouvel import, sa fiche s'ouvre.
- Toucher une ligne ouvre sa fiche (§4).

## 4. La fiche d'un import

Flèche ← en haut à gauche, retour au tableau. Enregistré au fil de la saisie.

- **Nom** (30 caractères).
- **Nature des pièces créées** : Facture d'achat, Vente, Note de frais, Honoraires (les natures de
  Pièces).
- **Source** : Docs, un des drives (« Drive « Club » (kDrive) »), HelloAsso ou une des boîtes
  mail, puis le **dossier** (pour Docs et un drive). **HelloAsso** : les versements de la
  campagne de la saison (Seb, 19 novembre).
- **Destination** : Aucune, Docs ou un des drives, puis le dossier. **N'importe quel dossier**
  (Seb, 19 novembre) : les dossiers imposés du Financier ne servent qu'au rangement des pièces
  saisies avec « + », à « Reprendre les soldes » et au dépôt du bilan ; la compta ne dépend pas
  d'eux (la base garde où est le fichier). « Aucune » : la pièce garde le lien vers son fichier dans
  la source, rien n'est copié. **Source boîte mail : destination obligatoire** (Seb), « Aucune »
  n'est pas proposé : la pièce jointe y est déposée.
  **Source HelloAsso** : l'appli **reconstitue** une pièce par versement (PDF : date, campagne,
  montant, détail des paiements) ; avec une destination, ce PDF y est déposé sous le nom
  « … (reconstituée par l'appli).pdf ». La fiche le dit : « Pièces reconstituées par l'appli à
  partir des versements HelloAsso. Pour garder les vraies pièces, prenez comme source le dossier
  où elles sont déposées. » **Seule exception** à la règle du 10 novembre (l'appli n'invente
  jamais de fichier dans Docs), **accordée par Seb le 19 novembre** à condition que ce soit dit :
  le nom du fichier et une mention en tête du PDF (« Pièce reconstituée par l'appli à partir du
  versement HelloAsso »).
- **Regarder s'il y a de nouvelles pièces** : chaque heure, chaque jour, chaque semaine ou chaque
  mois, et à quelle heure (sauf « chaque heure ») ; heure de Paris. « L'appli regarde la source à
  ce rythme et crée une pièce pour chaque nouveau fichier. »
  Bouton **« Regarder maintenant »** (Seb, 19 novembre) : lance le passage de cet import tout de
  suite, puis dit ce qu'il a trouvé (« 1 nouvelle pièce, À valider dans Pièces » ou « Rien de
  nouveau »).
- **Statut de la pièce créée** : « À valider », seul choix pour l'instant (Seb) ; d'autres
  viendront peut-être.

### 4.1 Source boîte mail (Seb, 19 novembre : « analyse de toute la boîte »)

L'appli lit toute la boîte (dossier de réception). Un mail **sans pièce jointe PDF ou photo est
ignoré**. Un mail avec pièce jointe devient une pièce s'il répond à l'un des critères :

- **L'expéditeur est connu ou contient** … : par défaut les profs, l'URSSAF et les fournisseurs
  déjà payés (tiers des pièces existantes) ;
- **L'objet ou le texte contient** … : par défaut « facture, note d'honoraires, reçu,
  remboursement » ;
- **La pièce jointe montre un montant, une date, un SIRET ou un numéro de facture** (case, cochée
  par défaut), d'après le lecteur des factures.

Cases modifiables ; vide = critère ignoré. La **nature vient de l'expéditeur** quand il est connu
(un prof : Honoraires ; un adhérent qui demande un remboursement : Note de frais), sinon la nature
de la fiche. Le mail reste dans la boîte, l'appli ne le déplace ni ne le marque lu.

## 5. Ce qui se passe à chaque passage

1. Pour chaque import actif dont l'heure est venue : lister la source (fichiers du dossier, sans
   les sous-dossiers ; mails de réception ; versements HelloAsso).
2. Écarter ce qui est **déjà vu** par cet import (même fichier : chemin, ou empreinte `sha256` s'il
   a été déplacé ou renommé ; même mail : identifiant du message) et ce qui est hors de la saison.
3. Lire le fichier (lecteur des factures) ; appliquer les critères (§4.1) pour un mail.
4. Destination : y déposer une copie du fichier (Docs : un nouveau fichier du dossier, c'est un
   fichier fourni par l'utilisateur, pas inventé ; drive : écrit dans le dossier). Sans
   destination : la pièce garde le lien vers la source.
5. Créer la pièce : nature de la fiche, état À valider, montant, date et tiers lus, comme une
   pièce du « + ». Les doublons de contenu sont signalés comme aujourd'hui (« même fichier que la
   pièce n° N »).
6. Noter le fichier comme vu, même s'il n'a pas donné de pièce (mail hors critères, fichier
   illisible), pour ne pas le relire à chaque passage.

Une source injoignable (drive déconnecté, boîte coupée) : le passage est sauté, la ligne de
Connexions le dit déjà ; rien n'est effacé.

## 6. Ouvrir le fichier d'une pièce

La base garde **où est le fichier** ; Pièces va l'y chercher à l'ouverture. Docs : comme
aujourd'hui (`nf_pieces.doc_node_id`). Drive : l'appli lit le fichier sur le drive et le montre
(visionneuse). Fichier déplacé ou renommé : retrouvé par son empreinte dans le dossier, sinon
« Fichier introuvable sur le drive » ; ses écritures restent (`financier.md` §8.11). L'appli
n'efface jamais rien sur un drive.

## 7. Données

Tables préfixées `autoimport_`, liées par `organization_id` (écoles étanches) :

- `autoimport_rules` : `organization_id`, `name`, `active`, `season_id`, `nature`
  (`achat`, `vente`, `frais`, `honoraires`), `source_kind` (`docs`, `drive`, `mail`, `helloasso`),
  `source_ref` (id du drive ou de la boîte), `source_path` (dossier), `target_kind` (`none`, `docs`,
  `drive`), `target_ref`, `target_path`, `frequency` (`hourly`, `daily`, `weekly`, `monthly`),
  `at_time`, `created_status` (`a_valider`), `mail_senders`, `mail_words`, `mail_need_amount`,
  `last_run_at`.
- `autoimport_seen` : `rule_id`, `source_key` (chemin ou identifiant du mail), `sha256`,
  `note_id` (nul si rien créé), `seen_at`. Effacer un import efface ses lignes `autoimport_seen`,
  jamais les `nf_notes`.
- `nf_pieces` gagne de quoi pointer un fichier de drive : `drive_id`, `drive_path` (le reste est
  déjà là : `sha256`, `taille`, `doc_node_id`). Composition : la pièce ne sait rien de l'import ;
  le nombre de pièces se compte par `autoimport_seen.note_id`.

## 8. Technique

- Code : `backend/src/auto_import/` (règles, passage, routes) et
  `frontend/src/modules/auto_import/` ; `module.py` avec `enabled_by_default=False`, allumé par
  migration dans les écoles de nature « combat ».
- Passage : un worker comme `app/sauvegarde_worker.py` (`app/auto_import_worker.py`), toutes les
  heures, qui lance les imports dont l'heure est venue.
- Sources par composition : une petite fonction par nature de source (lister, lire un fichier),
  branchée sur le service des drives (`core.md` §3), la boîte mail (`mail/imap.py`) et HelloAsso.
- Création de la pièce par le service existant des pièces (`notes_frais/service.py`), sans
  nouveau chemin d'écriture comptable.
- `guide.md` du module Financier mis à jour dans la même PR que l'écran.

## 9. Étapes de code (chacune une PR, sur le « vas-y » de Seb)

1. **Drives du club** dans Connexions, kDrive d'abord (`core.md` §3) : connexion, liste des dossiers,
   lecture d'un fichier. Nouveau point de branchement du core, accordé par Seb (19 novembre :
   « code tout et merge toi-même »). **Fait (19 novembre)** : `backend/src/drives/` (module
   `drives`, éteint par défaut, allumé pour les écoles « combat »), `core.drives` pour les autres
   modules ; kDrive demande aussi le numéro du kDrive ; Google Drive codé, proposé seulement quand
   le serveur a la clé du compte de service (`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` dans `backend/.env`).
2. **Écran Import auto pièces** et source **Docs** : tableau, fiche, worker, création des pièces
   À valider, Voir, 🗑.
   **Fait (19 novembre)** : `backend/src/auto_import/` (module `auto_import`, éteint par défaut,
   allumé pour les écoles « combat ») ; tables `autoimport_rules`, `autoimport_seen` ; `nf_pieces`
   gagne `linked`, `drive_id`, `drive_path` : une pièce reliée (`linked`) n'est jamais rangée,
   déplacée ni mise à la corbeille par Pièces (`notes_frais/service.py`, `etablir(lien=…)`). Passages :
   une boucle dans le serveur (`auto_import.module.start_loop`, toutes les 5 minutes, lancée par
   `app.main.main()`, pas un conteneur de plus), 50 fichiers au plus par passage. Saison : date du
   fichier. Nature « Vente » : l'import attend (« Les ventes ne se saisissent pas encore dans
   Pièces »), les ventes n'existant pas encore dans Pièces.
3. Source et destination **drive** (kDrive), ouverture du fichier depuis le drive (§6).
4. **Google Drive** dans Drives du club (partage du dossier avec l'adresse de l'appli).
5. Source **boîte mail** (§4.1).
6. Source **HelloAsso** (versements, `financier.md` §8.11).

## 10. Reste à décider

- D'autres statuts de pièce créée que « À valider ».
- Bulletins de salaire et avis URSSAF (paie complète, `financier.md` §8.11) : une nature de plus,
  ou l'étape 3 de §8.11 telle quelle.
- Rendre réglables les dossiers imposés du Financier, si un club les refuse (chantier à part).
