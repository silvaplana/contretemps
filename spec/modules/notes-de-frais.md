# AppBase — Module `notes-de-frais`

Version 0.4, 29 octobre 2026 (§5 et §7 : machine à états commune, notes dans Pièces ; §7 bis et §10 : un seul rangement, dans Docs ; §10 : colonnes ajoutées, codé). Statut : **brouillon, en cours de validation avec Seb** (fil « Notes de
frais » du projet). Maquette visuelle : Artifact « Notes de frais Contretemps », lien dans ce fil.

Écrit comme un module AppBase (rien de propre à la danse), comme `documents.md` : quand AppBase existera,
ce fichier y part tel quel. En attendant, il se code dans Contretemps ; ce qui ne vaut que pour
Contretemps est marqué *(Contretemps)*.

---

## 1. Objectif

Tout membre de l'organisation (élève, prof, admin, bénévole) peut avancer de l'argent pour elle et se
faire rembourser. Il photographie ses tickets au fil de l'eau, les regroupe en une note quand il veut
être remboursé, et l'envoie aux trésoriers, qui valident puis remboursent.

L'appli **ne paie pas** : le trésorier fait les virements depuis la banque de l'organisation, puis le
signale dans l'appli.

## 2. Vocabulaire

- **Dépense** : un achat, un ticket. Date, montant, catégorie, description, une ou plusieurs photos du
  justificatif (ou aucune, voir §4.3).
- **Note de frais** (ou « note ») : un ensemble de dépenses envoyées ensemble aux trésoriers. Titre libre,
  total calculé, un statut. C'est la note qu'on valide et qu'on rembourse, en un seul virement.
- **Trésorier** : rôle qui traite les notes (§6).

## 3. Accès

- **Membres** : une ligne **« Mes notes de frais »** dans l'écran **Profil**, pour tous les rôles, Super User
  compris (§3 bis), avec un
  compteur (« 3 à envoyer », « 1 en attente »). Elle ouvre un écran à part, hors de la barre du bas (même
  principe que Profil › « Mes heures », SPEC.md §5.7). Pas de nouvel onglet : la barre du bas est déjà
  pleine (décision de Seb, 16 octobre).
- **Trésoriers** (et Super User) : onglet **Financier**, sous-onglets **Comptes** puis **Notes de frais**
  (§7). Comptes : voir `financier.md` §3 (relevés bancaires repris de Sambo Admin, 20 octobre).
- Autres entrées possibles plus tard, qui mènent au même écran : l'Assistant (« j'ai payé 48 € de
  costumes », avec la photo) et le modèle « Faire une note de frais » du module documents
  (`documents.md` §5.6).

### 3 bis Le Super User (décision de Seb, 19 octobre)

Le Super User peut tout faire, donc aussi des notes de frais, **dans l'école où il intervient** (celle
qu'il a choisie après la connexion, `spec/core.md` §6.1). Il n'a pas de fiche dans l'école : sa dépense
et sa note sont **à son nom, rattachées à son compte**, sans fiche créée pour lui. L'appli envoie au
serveur l'école choisie (en-tête `X-Ecole-Id`), lu pour le seul Super User ; une école qui n'existe pas
est refusée. Sa note suit le même chemin que les autres : un trésorier la valide et la rembourse.

## 4. Côté membre

### 4.1 Liste « Mes notes de frais »

- En haut, **« À envoyer »** : les dépenses pas encore envoyées, chacune avec une case à cocher, toutes
  cochées par défaut. Ligne : description, date · catégorie, montant ; mention « sans justificatif » s'il
  n'y a pas de photo.
- En dessous, **« Envoyées »** : les notes, de la plus récente à la plus ancienne, avec titre, nombre de
  dépenses, total et statut (§5).
- Bas d'écran : bouton **« Envoyer (n) · total »**, qui suit la sélection, et bouton **« + »** pour une
  nouvelle dépense.

### 4.2 Nouvelle dépense (« + »)

1. Photo du ticket (appareil photo, ou choix d'une image ou d'un PDF existant).
2. L'IA lit le justificatif et **pré-remplit** date, montant, catégorie et description, avec la mention
   « Rempli d'après le ticket, à vérifier ».
3. La personne corrige si besoin, puis **Enregistrer** : la dépense rejoint « À envoyer ».

Une dépense « À envoyer » se modifie et se supprime librement.

### 4.3 Sans justificatif

Permis (péage, parking sans ticket…) : on saisit à la main. La dépense porte la mention **« sans
justificatif »**, visible du trésorier, qui juge (décision de Seb, 16 octobre).

### 4.4 Envoi

On coche, on appuie sur **Envoyer** : une petite fenêtre montre
- un **titre** pré-rempli (la catégorie commune, sinon le mois), modifiable ;
- le nombre de dépenses et le **total** ;
- le **RIB** de remboursement, repris du Profil (§4.5) ; s'il manque, on peut le saisir ici, et il est
  alors enregistré dans le Profil ;
- la case **« Je renonce au remboursement (don à l'association) »**, voir §8.

**Envoyer** crée la note et l'envoie d'un coup : pas d'étape « note créée mais pas envoyée », les
dépenses « À envoyer » jouent déjà ce rôle (décision de Seb, 16 octobre).

**Reprendre** : tant qu'aucun trésorier n'a validé, la personne peut reprendre sa note. La note disparaît
et ses dépenses repassent « À envoyer ».

### 4.5 RIB dans le Profil

Profil › Paramètres › **« Mon RIB »**, **facultatif** : titulaire, IBAN, BIC (ou photo du RIB, lue par
l'IA comme un ticket). Texte d'explication sous le champ : « Facultatif. Sert uniquement à vous
rembourser vos notes de frais ; seuls les trésoriers de l'association le voient. » (décision de Seb,
16 octobre)

### 4.6 Catégories

Liste par organisation. Plus de bouton « Catégories » dans Financier (décision de Seb, 19 octobre) : la
liste par défaut s'applique. Par défaut : Costumes, Déplacement, Matériel,
Location de salle, Alimentation, Autre. *(Contretemps : la liste par défaut ci-dessus.)*

**30 octobre 2026 (Seb)** : quand l'appli hôte donne un plan comptable (`Ports.plan`), les
catégories sont ses comptes de charges actifs (`nf_categories.code`) ; la liste libre ci-dessus ne
sert plus et se modifie dans le plan comptable (crayon de la fiche d'une pièce, financier.md §8.3 ter).

Déplacements en voiture : **au ticket** (essence, péage) pour l'instant, pas de barème kilométrique
(décision de Seb, 16 octobre).

## 5. Statuts d'une note

Depuis le 29 octobre 2026 (décision de Seb, fil « Virements »), une note suit la **machine à états
commune aux dépenses** de `financier.md` §8.3 bis, la même que pour les honoraires et les achats :

```
à valider ──valider──▶ à payer ──préparer──▶ préparé ──« j'ai fait le virement »──▶ envoyé ──vu sur le compte──▶ payé
   │                     (don : à payer = terminée, voir §8)
   ├──refuser (motif)──▶ refusé
   └──reprendre──▶ (note supprimée, dépenses « À envoyer »)
```

Même décision : une note de frais, une note d'honoraires et un achat sont la **même structure
« dépense »**, avec une nature, portée par ce module (`financier.md` §8.3 bis : ce qui est partagé et
ce qui diffère). À l'établissement, l'appli cherche aussi pour une note de frais si le virement a déjà
été fait sur les comptes : si oui, elle passe directement payé.

Correspondance avec les statuts d'avant (gardés tels quels en base, `nf_notes.statut`) : envoyée =
à valider, validée = à payer, remboursée = payé ; refusée ne change pas. Préparé et envoyé sont
nouveaux. Quand c'est le trésorier qui établit la note pour la personne (§7 ter), la validation est
faite en même temps : la note passe directement à payer.

- Un **seul trésorier** suffit pour valider (décision de Seb, 16 octobre).
- Le trésorier **refuse la note entière**, avec un **motif obligatoire** ; pas de refus ligne par ligne.
  La personne peut reprendre les dépenses d'une note refusée (elles repassent « À envoyer ») pour les
  corriger et renvoyer.
- Validation et paiement sont deux étapes : on valide souvent tout de suite, on fait les virements
  plus tard, en une fois, depuis Financier › Pièces › Virements (`financier.md` §8.3 bis : aide au
  virement, faire payer par quelqu'un). Le passage à payé se fait quand l'appli voit le virement sur
  le compte.

## 6. Rôle trésorier

- Nouveau rôle **`tresorier`**, réservé aux **admins** : un trésorier est toujours un admin (décision de
  Seb, 16 octobre), comme Owner. Il ne change pas le rang (bascule de profil, libellé principal) : c'est un
  droit en plus. Retirer le rôle admin retire aussi le rôle trésorier.
- Donné et retiré par un **administrateur principal** (Owner, le seul qui modifie ce tableau ; il peut
  cocher sa propre ligne, pour qu'une école à un seul Owner ait un trésorier) : dans Admin › École, le tableau des
  administrateurs a une **colonne « Trésorier » à cocher** (décision de Seb, 16 octobre). C'est le
  **seul endroit** où l'on nomme ou retire un trésorier (ni fiche élève, ni Assistant).
- Une organisation peut avoir plusieurs trésoriers. Sans trésorier, les notes envoyées attendent, et
  l'envoi prévient la personne que personne ne peut encore les traiter.
- Un trésorier ne valide pas ses propres notes s'il y a un autre trésorier ; s'il est seul, il peut.

## 7. Côté trésorier : Financier › Pièces › Notes de frais

Décision de Seb, 29 octobre 2026 : le sous-onglet **Notes de frais** de Financier disparaît, les notes
sont des pièces comme les autres, dans la puce **Notes de frais** de Financier › Pièces
(`financier.md` §8.3). Rien ne change côté membre (§4). Dans la puce : la liste des notes, de la plus
récente à la plus ancienne, chacune avec son état (badge à valider / refusé / à payer / préparé /
envoyé / payé), titre, qui (et son rôle), date, nombre de dépenses, total ; filtre par période ; export
Excel (une ligne par dépense : date, personne, catégorie, description, montant, note, statut). Les
notes **à valider** sont en tête. Ce qui est à payer, préparé ou envoyé se retrouve aussi dans la
puce **Virements**, avec le RIB de la personne et l'aide au virement ; plus de bouton « Marquer
remboursées » : c'est « J'ai fait le virement », puis le rapprochement avec le compte.

Détail d'une note : chaque dépense avec sa photo (agrandissable), la mention « sans justificatif » le cas
échéant, le total, le RIB ; boutons **Valider** et **Refuser…** (motif obligatoire), et **« Télécharger les
justificatifs »** : un zip des photos de la note, nommées comme sur le disque (décision de Seb, 17 octobre).

### 7 ter Saisir pour quelqu'un (décision de Seb, 19 octobre)

Le trésorier reçoit souvent des papiers et des factures à la place des gens. Dans Financier, le menu
**⋯** propose **« Créer une dépense pour quelqu'un »** et **« Envoyer une note pour quelqu'un »**. Les
deux commencent par **« Pour qui ? »** : la liste de toutes les personnes de l'école, avec une recherche
par nom. Ensuite, ce sont **les mêmes écrans que Profil › « Mes notes de frais »**, au nom de cette
personne (« Pour Margot Perrin », retour vers Financier) ; « Créer une dépense » ouvre directement la
saisie.

Tout est **au nom de la personne choisie** : ses dépenses, sa note, son RIB (celui qu'on saisit à
l'envoi s'il manque). Elle les retrouve dans son « Mes notes de frais », et la note suit le chemin
habituel (validée en même temps, puis à payer). Réservé aux trésoriers et au Super User. Technique : l'appli
envoie l'id de la personne dans l'en-tête `X-Pour-Personne` ; le serveur vérifie le droit et que la
personne est de l'organisation.

### 7 quater Personnes extérieures (Seb, 31 octobre)

Un prof invité ou un intervenant se paie sans être membre (exemple : Jacques Pesanti). Il n'a pas
de fiche dans l'école : il n'est ni dans la liste des membres, ni dans les envois à tous, ni à l'AG.
Le module garde à part une liste **Extérieurs** (nom, mail, RIB).

- **« Pour qui ? »** (⋯ « pour quelqu'un », « + » des notes de frais, Pour qui des honoraires, qui
  s'ouvre par la loupe) : les membres d'abord, puis les extérieurs sous le titre « Extérieurs », la
  recherche les trouve tous ; en bas **« + Quelqu'un d'extérieur »** : nom (repris de la
  recherche), mail, RIB ; il est ajouté et choisi.
- La photo d'une facture d'honoraires le reconnaît comme un membre (son nom lu sur la facture).
- Ensuite tout est pareil : RIB recopié, Virements, Docs (dossier à son nom). Il n'a pas l'appli :
  il est prévenu par mail (note de frais validée ou refusée, remboursée ; honoraires payés).
- **Financier › ⋯ › Extérieurs** : la liste ; toucher une ligne pour corriger le nom, le mail ou le
  RIB, ou **Retirer de la liste** (plus proposé dans « Pour qui ? », ses notes gardent son nom).
- Technique : table `nf_externals` ; dans le module, son `person_id` est négatif (−id), son RIB est
  dans `nf_ribs` sous ce numéro ; l'annuaire de l'hôte n'en sait rien.

### 7 bis Rangement dans Docs (Seb, 17 octobre ; simplifié le 29 octobre)

Décision de Seb, 29 octobre 2026 (`financier.md` §8.3 bis « Rangement dans Docs ») : **un seul
endroit**, Docs › Privé › Saison en cours › Financier › Notes de frais › `<n° personne> <Nom>` ›
`<date d'envoi> <titre> (<n°>)`, où les justificatifs sont rangés dès l'envoi et **ne bougent plus**.
**L'état ne se lit que dans l'appli** : plus de badge sur le dossier, plus de nouvelle version du PDF à
chaque étape. Le PDF récapitulatif est fait une fois, quand la note est payée (ou sur demande,
« Télécharger les justificatifs »). Plus d'enveloppes à part sur le disque du serveur (§10) : Docs
range déjà ses fichiers sur le disque. Une note **reprise** par son auteur (avant validation ou après
un refus) part à la corbeille des documents. Le dossier Financier existe dans chaque saison et n'est
visible que des trésoriers (documents.md §4.7 bis) ; « Notes de frais » y est créé à la première note.
La saison est celle du jour de l'envoi. Si le rangement échoue, l'action reste faite.

## 8. Don à l'association

Cocher « Je renonce au remboursement » fait de la note un **don** : une fois validée, elle est terminée
(pas de virement) et compte dans les dons de la personne pour le reçu fiscal (abandon de frais). Le reçu
fiscal lui-même relève d'un futur module ; ce module ne fait que marquer et lister ces notes.

## 9. Alertes

Par **notification dans l'appli** et par **mail**, à chaque étape :
- note envoyée → à **chaque trésorier** ;
- note validée, refusée (avec le motif), remboursée → à la **personne**.

**Adresse mail du trésorier** : nouveau champ de l'organisation, dans Admin › École, à côté de
l'adresse mail de contact, qui est à créer elle aussi (décision de Seb, 16 octobre). Souvent une boîte partagée du bureau.

Mails : envoyés par l'appli (adresse technique d'expédition, au nom de l'organisation), comme les autres
mails de l'appli.
- **Note envoyée** : le mail part à l'**adresse mail du trésorier** de l'organisation ; si elle n'est pas
  remplie, à l'email de chaque trésorier. **Exception** : si la personne qui envoie la note a elle-même
  l'adresse mail du trésorier (c'est le trésorier qui se fait rembourser), le mail part à l'email
  personnel des **autres** trésoriers, jamais à elle-même (décision de Seb, 16 octobre). « Répondre à » :
  la personne qui a envoyé la note. La
  notification dans l'appli, elle, va à chaque trésorier.
- **Note validée, refusée, remboursée** : mail à la personne, « répondre à » l'**adresse mail du
  trésorier** (repli : le trésorier qui a fait l'action, puis l'adresse de contact de l'organisation).
*(Contretemps : expédition `contretemps@silvaplana.cloud` par Brevo, SPEC.md §2.2.)*

## 10. Données

Tables préfixées `nf_` (module autonome) :

- `nf_depenses` : id, organisation, personne (qui a payé), date, montant (centimes), catégorie,
  description, lue_par_ia, note_id (null = « À envoyer »), créée le. « Sans justificatif » = aucune pièce.
- `nf_pieces` : id, depense_id, chemin du fichier (sur le disque avant l'envoi ; ensuite le nom dans Docs),
  `doc_node_id` (le fichier dans Docs), type, nom, taille, ordre. 5 pièces au plus par dépense, 20 Mo par fichier.
- `nf_notes` : id, organisation, personne, titre, statut (`envoyee`, `validee`, `refusee`, `preparee`,
  `viree`, `remboursee`), don, RIB (copie au moment de l'envoi), motif_refus, envoyée le, traitée le / par,
  remboursée le / par ; depuis le 29 octobre : `nature` (`frais`, `honoraires`, `achat`), `supplier`
  (achat), `prepared_at` / `prepared_by` / `payer_id` (Faire payer par…), `transfer_sent_at` / `_by`
  (J'ai fait le virement), `bank_operation_id` (opération du compte, payé). Honoraires dont le prof n'est
  pas encore reconnu : personne 0.
- `nf_payers` : réglage « Qui paie » (organisation, personne) ; vide = les trésoriers.
- `nf_externals` : personnes extérieures (organisation, nom, mail, retirée le) ; §7 quater.
- `nf_categories` : id, organisation, libellé, ordre, active.
- `nf_ribs` : RIB du membre (titulaire, IBAN, BIC), facultatif, un par personne (Profil › Mon RIB),
  visible de lui et des trésoriers seulement.
- Organisation : `email_tresorier` et `email_contact` *(Contretemps : colonnes de `ecoles`, Admin › École
  › Coordonnées)*.
- Rôle `tresorier` dans la table des rôles du compte *(Contretemps : `roles_compte`, SPEC.md §6.3bis)*.

Montants en centimes entiers ; total d'une note = somme de ses dépenses, jamais stocké à part.

**Pas de saison** : dépenses et notes appartiennent à la **personne**, pas à une saison (décision du
16 octobre). Une note envoyée en juin et remboursée en septembre reste visible des deux côtés après le
changement de saison. *(Contretemps : la « personne » est le premier compte de la chaîne
`compte_precedent_id`, comme pour les documents.)*

### Rangement sur le disque (décision de Seb, 16 octobre ; abandonné le 29 octobre)

Les enveloppes `<NOTES_FRAIS_DIR>/<organisation>/<n° personne> <Nom>/…` (un dossier par personne,
`depenses/` puis une enveloppe par note avec « Note de frais.pdf » refait à chaque étape) sont
**remplacées par Docs** (§7 bis, décision de Seb du 29 octobre) : un seul endroit, PDF fait une fois
quand c'est payé. Codé le 29 octobre, avec la commande
`python -m app.ranger_notes_frais` (`--essai` pour voir sans rien changer) qui déplace les enveloppes existantes dans Docs ; les tickets pas encore
envoyés (`depenses/`) restent sur le disque jusqu'à l'envoi. Les fichiers ne sont jamais servis en
accès direct : seulement par les routes, à l'auteur et aux trésoriers.

## 11. Droits

| Action | Qui |
|---|---|
| Créer, modifier, supprimer une dépense « À envoyer » | son auteur |
| Envoyer, reprendre une note (tant que pas validée) | son auteur |
| Voir ses dépenses et ses notes | son auteur (et les autres fiches du même email) |
| Voir toutes les notes, valider, refuser, marquer remboursée, exporter | trésoriers de l'organisation, Super User |
| Créer des dépenses et envoyer des notes pour quelqu'un (§7 ter) | trésoriers de l'organisation, Super User |
| Donner, retirer le rôle trésorier | admins |

Les admins non trésoriers ne voient pas les notes des autres. Via l'Assistant, chacun fait et voit
exactement ce que ses écrans permettent (règle générale de l'Assistant).

## 12. Lecture du justificatif par l'IA

Même service que l'Assistant (modèle Claude, image en entrée), compté dans le plafond mensuel de
l'organisation. Sortie attendue : date, montant TTC, commerçant, catégorie proposée parmi celles de
l'organisation, description courte. Si la lecture échoue ou si le plafond est atteint, le formulaire
reste vide et se remplit à la main.

## 13. Points ouverts

- Plafond par note ou double validation au-delà d'un montant : non, pour l'instant (un trésorier suffit).
- Barème kilométrique : plus tard, si besoin.
- Export comptable au-delà d'Excel : plus tard.
