# AppBase — Module `notes-de-frais`

Version 0.1, 16 octobre 2026. Statut : **brouillon, en cours de validation avec Seb** (fil « Notes de
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

Déplacements en voiture : **au ticket** (essence, péage) pour l'instant, pas de barème kilométrique
(décision de Seb, 16 octobre).

## 5. Statuts d'une note

```
envoyée ──valider──▶ validée ──marquer remboursée──▶ remboursée
   │                     (don : validée = terminée, voir §8)
   ├──refuser (motif)──▶ refusée
   └──reprendre──▶ (note supprimée, dépenses « À envoyer »)
```

- Un **seul trésorier** suffit pour valider (décision de Seb, 16 octobre).
- Le trésorier **refuse la note entière**, avec un **motif obligatoire** ; pas de refus ligne par ligne.
  La personne peut reprendre les dépenses d'une note refusée (elles repassent « À envoyer ») pour les
  corriger et renvoyer.
- Validation et remboursement sont deux étapes : on valide souvent tout de suite, on fait les virements
  plus tard, en une fois.

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

## 7. Côté trésorier : Financier › Notes de frais

Trois filtres, avec un compteur chacun (Terminées compris, décision de Seb, 19 octobre) :
1. **À valider** : notes envoyées. Ligne : titre, qui (et son rôle), date d'envoi, nombre de dépenses,
   total. Total général en bas.
2. **À rembourser** : notes validées sans don. Cases à cocher, RIB de chacun visible ; bouton
   **« Marquer remboursées (n) »** une fois les virements faits à la banque.
3. **Terminées** : remboursées, dons et refusées, pour l'historique et les comptes de fin d'année.
   Filtre par période ; export Excel (une ligne par dépense : date, personne, catégorie, description,
   montant, note, statut).

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
habituel (à valider, puis à rembourser). Réservé aux trésoriers et au Super User. Technique : l'appli
envoie l'id de la personne dans l'en-tête `X-Pour-Personne` ; le serveur vérifie le droit et que la
personne est de l'organisation.

### 7 bis Rangement dans Docs (Seb, 17 octobre)

Dès l'**envoi**, l'appli range la note dans les documents, sans rien demander :
**Privé › Saison en cours › Financier › Notes de frais › `<n° personne> <Nom>` ›
`<date d'envoi> <titre> (<n°>)`** (mêmes noms que les enveloppes du disque), avec le PDF récapitulatif et
les justificatifs. **Rien ne bouge ensuite**, ni dans Docs ni sur le disque, comme dans les logiciels
pro : le statut est dans la base et dans le PDF, et se lit dans Docs au **badge** du dossier de la note,
avec les statuts des documents (documents.md, État) (Seb, 17 octobre) :

| Note | Badge du dossier |
|---|---|
| en attente | Brouillon |
| refusée | Refusé (sens interdit, rouge) |
| validée, à rembourser | Validé |
| remboursée, ou don validé | Officiel (figé) |

À chaque étape, le PDF reçoit une nouvelle version, puis le badge change. Une note **reprise** par son
auteur (avant validation ou après un refus) part à la corbeille des documents. Le dossier Financier
existe dans chaque saison et n'est visible que des trésoriers, même pas des autres admins (documents.md
§4.7 bis) ; « Notes de frais » y est créé à la première note. La saison est celle du jour de l'envoi.
Si le rangement échoue, l'action reste faite (les photos restent dans l'enveloppe et le bouton
« Télécharger les justificatifs »).

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
- `nf_pieces` : id, depense_id, chemin du fichier (voir « Rangement sur le disque »), type, nom, taille,
  ordre. 5 pièces au plus par dépense, 20 Mo par fichier.
- `nf_notes` : id, organisation, personne, titre, statut (`envoyee`, `validee`, `refusee`, `remboursee`),
  don, RIB (copie au moment de l'envoi), motif_refus, envoyée le, traitée le / par, remboursée le / par.
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

### Rangement sur le disque (décision de Seb, 16 octobre)

Les justificatifs sont rangés en **enveloppes**, un dossier par personne :

```
<NOTES_FRAIS_DIR>/<organisation>/<n° de la personne> <Nom Prénom>/
    depenses/                                   tickets pas encore envoyés
    notes/<AAAA-MM-JJ> <titre> (<n° de note>)/  une enveloppe par note envoyée
        Note de frais.pdf                       récapitulatif + une page par photo
        <date> <description> <n°>-<n°>.jpg      les justificatifs
```

**Le dossier du serveur suffit à tout retrouver**, même si la base de données était perdue (Seb,
17 octobre) : chaque enveloppe contient « Note de frais.pdf », avec une page de récapitulatif (personne,
titre, dépenses avec date, catégorie, description et montant, total, statut avec ses dates et qui l'a
traitée, motif de refus, RIB ou don), puis une page par photo de ticket (les PDF joints restent à côté).
Il est refait à chaque étape : envoi, validation, refus, remboursement ; il part avec les photos dans
Docs › Financier à la validation, et y reçoit une nouvelle version au remboursement. Il est aussi dans le
zip « Télécharger les justificatifs ».

Fichier : `<date> <description> <n° de dépense>-<n° de pièce>.<ext>`. À l'envoi, les fichiers passent de
`depenses/` à l'enveloppe de la note ; une note reprise les y renvoie et son enveloppe vide disparaît. Le
numéro en tête du dossier de la personne (gardé, décision de Seb du 17 octobre) le retrouve même si son nom change ou si deux personnes ont le
même nom. Jamais servis en accès direct : seulement par les routes du module, à l'auteur et aux
trésoriers. *(Contretemps : `NOTES_FRAIS_DIR`, `/app/data/notes_frais` dans l'image Docker, dans le volume de données.)*

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
