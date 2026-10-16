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

- **Membres** : une ligne **« Mes notes de frais »** dans l'écran **Profil**, pour tous les rôles, avec un
  compteur (« 3 à envoyer », « 1 en attente »). Elle ouvre un écran à part, hors de la barre du bas (même
  principe que Profil › « Mes heures », SPEC.md §5.7). Pas de nouvel onglet : la barre du bas est déjà
  pleine (décision de Seb, 16 octobre).
- **Trésoriers** : onglet **Financier**, visible des seuls trésoriers, sous-onglet « Notes de frais » (§7).
  Financier accueillera plus tard d'autres sous-onglets (budget…).
- Autres entrées possibles plus tard, qui mènent au même écran : l'Assistant (« j'ai payé 48 € de
  costumes », avec la photo) et le modèle « Faire une note de frais » du module documents
  (`documents.md` §5.6).

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

Liste par organisation, modifiable par les trésoriers. Par défaut : Costumes, Déplacement, Matériel,
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

- Nouveau rôle **`tresorier`**, cumulable avec les autres (un élève ou un admin peut être trésorier).
  Il ne change pas le rang (bascule de profil, libellé principal) : c'est un droit en plus, comme Owner.
- Donné et retiré par un **admin** de l'organisation : dans Admin › École, le tableau des
  administrateurs a une **colonne « Trésorier » à cocher** (décision de Seb, 16 octobre).
- Une organisation peut avoir plusieurs trésoriers. Sans trésorier, les notes envoyées attendent, et
  l'envoi prévient la personne que personne ne peut encore les traiter.
- Un trésorier ne valide pas ses propres notes s'il y a un autre trésorier ; s'il est seul, il peut.

## 7. Côté trésorier : Financier › Notes de frais

Trois filtres, avec un compteur chacun :
1. **À valider** : notes envoyées. Ligne : titre, qui (et son rôle), date d'envoi, nombre de dépenses,
   total. Total général en bas.
2. **À rembourser** : notes validées sans don. Cases à cocher, RIB de chacun visible ; bouton
   **« Marquer remboursées (n) »** une fois les virements faits à la banque.
3. **Terminées** : remboursées, dons et refusées, pour l'historique et les comptes de fin d'année.
   Filtre par période ; export Excel (une ligne par dépense : date, personne, catégorie, description,
   montant, note, statut).

Détail d'une note : chaque dépense avec sa photo (agrandissable), la mention « sans justificatif » le cas
échéant, le total, le RIB ; boutons **Valider** et **Refuser…** (motif obligatoire).

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

- `depenses` : id, organisation, compte (qui a payé), date, montant (centimes), devise (EUR), catégorie,
  description, sans_justificatif (calculé : aucune pièce), note_id (null = « À envoyer »), créée le,
  lu_par_ia (bool).
- `depense_pieces` : id, depense_id, fichier (photo ou PDF, stockage privé de l'organisation), ordre.
- `notes_frais` : id, organisation, compte, titre, statut (`envoyee`, `validee`, `refusee`, `remboursee`),
  don (bool), rib (copie au moment de l'envoi), motif_refus, envoyée le, validée le / par, refusée le /
  par, remboursée le / par.
- `categories_frais` : id, organisation, libellé, ordre, active.
- RIB du membre (titulaire, IBAN, BIC), facultatif : champs de son compte (Profil › Paramètres › Mon RIB),
  visibles de lui et des trésoriers seulement.
- Organisation : `email_tresorier` (à côté de l'email de contact).
- Rôle `tresorier` dans la table des rôles du compte *(Contretemps : `roles_compte`, SPEC.md §6.3bis)*.

Montants en centimes entiers ; total d'une note = somme de ses dépenses, jamais stocké à part.
Une dépense ou une note appartient à une saison comme le reste des données *(Contretemps, SPEC.md
§2.6)* ; les trésoriers voient aussi les notes des saisons passées dans « Terminées ».

## 11. Droits

| Action | Qui |
|---|---|
| Créer, modifier, supprimer une dépense « À envoyer » | son auteur |
| Envoyer, reprendre une note (tant que pas validée) | son auteur |
| Voir ses dépenses et ses notes | son auteur (et les autres fiches du même email) |
| Voir toutes les notes, valider, refuser, marquer remboursée, exporter | trésoriers de l'organisation |
| Gérer les catégories | trésoriers |
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
