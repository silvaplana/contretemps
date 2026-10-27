# AppBase — Spécification du core (socle commun)

Version 1.0 du 27 octobre 2026. Réécrite de zéro ; remplace la version 0.1 du 18 octobre.
Destinataire : Claude Code. Décisions de Seb des 18, 19, 20, 22, 24, 26 et 27 octobre 2026.

Le **core** est ce que toute appli bâtie sur AppBase a toujours, quels que soient les modules
choisis. Tout le reste est un **module**, décrit dans `spec/modules/`. Ce document dit la
**cible** ; quand le code de Contretemps fait autrement aujourd'hui, un paragraphe « Aujourd'hui »
le dit. `SPEC.md` reste la référence de ce qui est propre à Contretemps (cours, présence,
chorégraphies…) et sera réduit à cela.

Maquettes validées par Seb (les écrans les suivent exactement) :

| Écran | Maquette |
|---|---|
| Créer une saison | https://claude.ai/artifact/HBmtbMrhW3ec3GdAPCkzgz |
| Champs des membres (la fiche, l'affichage dans Admin, réglages avancés) | https://claude.ai/artifact/Hq9m7zuMaK6ZYwx3BMFSyx |
| Admin > Administrateurs avec la colonne Groupes | https://claude.ai/artifact/L9ak9YSbWkvGdrQPg48mSR |
| Tarifs de la saison (formules, options et codes promo) | https://claude.ai/artifact/GFYT9ZndL9hiwKxTHS57od |
| Connexion HelloAsso (module, `spec/modules/helloasso.md`) | https://claude.ai/artifact/FhTWcRKXpVfdf9toaTSeXS |

---

## 1. Ce qui est dans le core, ce qui n'y est pas

| Dans le core | Hors du core (module ou appli) |
|---|---|
| Organisation : création, étanchéité, adresse web, apparence, vocabulaire | Cours, planning, présence (modules Cours, Profs) |
| Membres : une fiche par personne, champs définis par l'organisation (§4) | Champs calculés et boutons apportés par les modules |
| Groupes et sous-groupes, droits (§5) | Les groupes que chaque module déclare (Cours, Profs, Bureau…) |
| Famille par l'email du payeur (§4.4) | Inscription publique, HelloAsso (`modules/helloasso.md`) |
| Connexion : mot de passe, invitation, session (§6) | Messagerie, vidéos, chorégraphies |
| Niveaux : Membre, Admin, Administrateur principal, Super User (§7) | Documents, Fichier de base, Signature |
| Saisons et leur création étape par étape (§8) | Financier, notes de frais |
| Tarifs : formules, options et codes promo (§9) | Catalogue, boutique |
| Installation sur le téléphone, barre du bas (§10) | Assistant |
| Enregistrement des modules, modules allumés par organisation (§11) | |
| Email, notifications push, sauvegarde, temps réel (§12) | |

---

## 2. Les mots

| Dans AppBase (code, tables) | À l'écran (Contretemps) | Ce que c'est |
|---|---|---|
| **organisation** (`org`) | École | Une association, un club, une pizzeria. Ses données sont étanches. |
| **membre** (`member`) | Élève, Prof, Admin… | Une personne dans une organisation, pour une saison. |
| **champ** (`field`) | Champ | Une question de la fiche, définie par l'organisation (§4). |
| **groupe** (`group`) | Groupe, Cours, Bureau… | Des personnes réunies sous un nom (§5). Un cours est un groupe. |
| **droit** (`right`) | 🔒 Accès au Financier | Un groupe spécial créé pour un droit déclaré par un module (§5.3). |
| **famille** | Famille | Les fiches qui ont le même email du payeur (§4.4). |
| **adresse de connexion** | Email | Une adresse email, avec son mot de passe. |
| **niveau** | — | Ce que la personne a le droit de faire dans le core (§7). |
| **saison** (`season`) | Saison | Une année d'activité. |
| **formule** | Formule | Ce qu'un membre choisit et paie pour la saison (§9). |

Vocabulaire à l'écran : l'organisation choisit ses mots pour École, Élèves, Profs et Cours
(Admin > École > Personnalisation de l'application > Vocabulaire, colonnes `mot_*` de `ecoles`,
vide = mot par défaut du produit). Jamais de mot technique à l'écran (« rôle », « type », « owner »,
« IA ») : on dit « nature », « module », « sous-module », « assistant ».

Le code ancien de Contretemps garde ses noms français (`ecoles`, `comptes`, `cours`). Tout code
nouveau, toute table nouvelle est en anglais.

---

## 3. Organisation

- **Étanchéité** : une organisation ne voit jamais les données d'une autre. Toute table qui
  appartient à une organisation porte son identifiant ; chaque route sait quelle organisation
  elle touche et la passe au contrôle des droits. Un admin d'une organisation n'a aucun droit sur
  une autre.
- **Création** : par le Super User. Nom, code postal, premier administrateur, qui devient
  Administrateur principal et reçoit une invitation (§6). Le **produit** (Contretemps Studio,
  Fight Lab, Asso in the Pocket…) fixe les modules allumés par défaut et les mots par défaut.
- **Fiche de l'organisation** : nom, code postal, adresse, SIRET, IBAN, email de contact, email du
  trésorier. Les mails de l'appli partent au nom de l'organisation et répondent à son email de
  contact.
- **Adresse web** (décision du 15 octobre, en ligne) : un sous-domaine par organisation,
  `https://<adresse>.<appli>.silvaplana.cloud` (ex. `le-beausset.contretemps.silvaplana.cloud`),
  pour que chacune ait **son nom et son logo sur l'écran d'accueil du téléphone** (le manifest est
  lu avant toute connexion) et ses propres session, cache et abonnements push. Colonne
  `sous_domaine`, unique, 3 à 40 caractères (minuscules sans accent, chiffres, tirets), normalisée
  pendant la frappe, disponibilité vérifiée en direct ; noms réservés : `www`, `api`, `admin`,
  `app`, `mail`, le nom du produit. Proposée à la création depuis le nom (puis la ville). Changer
  l'adresse est réservé à l'Administrateur principal, avec avertissement (réinstallation) ;
  l'ancienne adresse redirige 6 mois. Côté serveur : DNS `*.<appli>.silvaplana.cloud`, Caddy avec
  TLS à la demande (`GET /sous-domaines/existe`), rien à relancer quand une organisation est créée ;
  l'adresse générique du produit reste la page de connexion « dans toutes les organisations » et
  renvoie chacun vers l'adresse de son organisation après connexion. Routes publiques par adresse :
  manifest généré (nom sous l'icône, slogan, couleurs, icônes 192 et 512 px « maskable » depuis le
  logo), icônes, `index.html` avec `<title>`, `apple-mobile-web-app-title` et `theme-color`
  injectés. Sur iPhone, nom et icône sont figés à l'installation.
- **Personnalisation de l'application** (Admin > École), trois parties dans cet ordre :
  **Apparence visuelle** (logo, nom, slogan, couleurs, polices, adresse), **Fonctionnalités** (une
  case par module, §11.3) et **Vocabulaire** (§2). Apparence et Vocabulaire : tout admin ;
  Fonctionnalités : Administrateur principal et Super User seulement.

---

## 4. Membres et champs

### 4.1 Une personne = une fiche

Une seule fiche par personne, dans une organisation, pour une saison. Tout ce qu'elle est
(élève, prof, admin, membre du bureau…) s'ajoute sur cette fiche par ses groupes (§5) et ses
niveaux (§7), jamais par une deuxième fiche. Deux fiches de la même personne se **fusionnent**
(bouton « Fusionner avec… » : il n'en reste qu'une, avec tout ce qu'avaient les deux ; dès qu'une
des deux est admin, seul l'Administrateur principal ou le Super User le peut ; le Super User ne se
fusionne pas).

Saisir une personne qui a déjà une fiche (fiche papier, import, assistant, HelloAsso) complète la
fiche existante au lieu d'en créer une autre, sauf si cette fiche est admin : on n'y ajoute jamais
une adresse nouvelle (elle obtiendrait ses droits), on crée une fiche à part et l'Administrateur
principal fusionne.

### 4.2 Les champs du socle

Toujours là, non supprimables : **Nom, prénom** ; **Email** (plusieurs adresses possibles, toutes
équivalentes, aucune « principale ») ; **Email du payeur** (§4.4) ; téléphone. Tout le reste est un
champ de l'organisation (§4.3) ou vient d'un module.

### 4.3 La structure des membres : trois niveaux

L'organisation définit elle-même ce qu'elle demande à ses membres. La structure est **portée par
la saison**, recopiée de la saison précédente à la création (§8). Écran : étape « Membres » de la
création de saison, et Admin > Élèves > ⋯ > Champs. Maquette : Champs des membres.

**Niveau 1 — La fiche** : la liste de ce qu'on demande à chaque membre, dans l'ordre. Chaque
champ a :
- un **intitulé** ;
- un **statut** : Obligatoire ou Facultatif ;
- un **format de la réponse**, dans la liste de HelloAsso plus deux : Texte court, Texte long,
  Nombre, Date, Oui / non, Téléphone, Code postal, Fichier à télécharger, Liste déroulante (choix
  proposés, un par ligne), **Groupe** (on coche parmi les sous-groupes d'un groupe, ex. « Cours
  suivis » parmi Cours : la personne entre dans ces groupes) ; Liste et Groupe ont la case
  « Plusieurs choix possibles ».
Un champ ajouté par l'organisation est toujours **saisi** (par la personne ou par un admin).
« + Ajouter un champ », « Retirer ce champ » avec Annuler 10 s.

En haut de la fiche, si le module HelloAsso est allumé pour l'organisation, un choix :
**Nos champs** (ceux du socle plus les nôtres) ou **Imposés par HelloAsso**, avec la campagne à
choisir. Les champs de la campagne arrivent verrouillés, marqués « Calculé par HelloAsso », remplis
par HelloAsso ; on peut seulement ajouter les nôtres à côté. Détail : `modules/helloasso.md`.

**Niveau 2 — L'affichage dans Admin** : les colonnes du tableau des membres. Ce sont les champs
de la fiche, plus les **champs calculés** et les **boutons** que les modules allumés apportent
(ex. Ancienneté, Montant payé du module Paiement, « Inscrire au cours » du module Cours,
« Demander la licence » du module Licences FFST). Pour chaque colonne : **Afficher** (case) et
l'**ordre**, changé en glissant la poignée ⠿ (jamais de flèches). Un calcul masqué continue de
travailler en coulisse. L'organisation décide ; les admins voient toutes les colonnes affichées.

**Niveau 3 — Réglages avancés**, repliés sur chaque champ, et qui ne concernent que le **côté
membre** : la personne le voit, la personne peut le modifier, les autres membres le voient, pour
qui (tout le monde ou un groupe). Les admins voient tout. Les champs techniques ne sont jamais
montrés.

À l'écran, jamais le mot « type » : on dit « format de la réponse » ou « nature ».

**Données** (cible) : `member_fields` (organisation, saison, intitulé, statut, format, choix,
groupe, plusieurs, ordre, source `ours` / `helloasso`, clé HelloAsso) ; `member_values`
(membre, champ, valeur) ; `member_columns` (saison, colonne — champ, calcul ou bouton d'un
module —, affichée, ordre) ; réglages côté membre sur `member_fields`. Les champs calculés et les
boutons sont déclarés par les modules dans leur `module.py` (§11.1), jamais écrits en base.

**Aujourd'hui** : les champs des élèves sont en dur dans `comptes` et `eleves` (`SPEC.md` §6.3,
§6.4), les colonnes d'Admin > Élèves dans `AdministrateursTableau.jsx` et `ElevesTableau.jsx`.

**Fait (27 octobre 2026, étape 4a)** : le niveau 1, la fiche (`backend/src/members/`, tables
`member_fields` et `member_values`). Admin > Élèves > ⋮ > Champs ouvre « La fiche d'un membre »
comme la maquette : les champs du socle verrouillés (Nom, prénom ; Email ; Téléphone ; l'Email du
payeur arrive à l'étape 5), puis ceux de l'école, « + Ajouter un champ », le détail (intitulé,
statut, format de la réponse, choix, « Parmi les groupes de » avec Cours proposé d'office,
« Plusieurs choix possibles », réglages avancés repliés), « Retirer ce champ » avec Annuler 10 s
(les réponses sont gardées). La fiche de l'élève a une rubrique « Nos champs » où l'admin lit et
saisit les réponses ; un champ Groupe y coche les sous-groupes (cocher un cours y inscrit l'élève).
Un fichier est rangé comme les autres contenus protégés (`storage/`, dossier « membres », compté
dans l'usage des ressources). La fiche et les réponses des fiches reprises sont recopiées à la
nouvelle saison ; les réponses suivent la fusion, partent avec la fiche supprimée et sont dans la
sauvegarde technique (onglets « ChampsMembres », « ReponsesMembres »). Pas encore : le choix
Nos champs / Imposés par HelloAsso (avec le module HelloAsso), l'effet des réglages avancés (avec la
fiche vue par la personne), l'affichage dans Admin (étape 4b), la reprise des champs actuels des
élèves (étape 4c).

**Fait (27 octobre 2026, étape 4b)** : le niveau 2, l'affichage dans Admin (table `member_columns` :
organisation, saison, colonne, affichée, ordre ; pas de ligne = l'ordre d'origine, tout affiché).
« Affichage dans Admin › », sous la fiche, ouvre l'écran de la maquette : une ligne par colonne du
tableau des élèves avec sa nature (Saisi, ou **Calculé** / **Bouton** et d'où il vient), la poignée ⠿
pour l'ordre (au doigt, à la souris ou aux flèches du clavier) et la case Afficher (Annuler 10 s ;
la colonne Élève reste toujours affichée). Chaque changement est enregistré aussitôt et le tableau
d'Admin > Élèves le suit, colonnes des champs de l'école comprises (la réponse en clair, appui long
compris). Recopié à la nouvelle saison, dans la sauvegarde technique (onglet « ColonnesMembres »).
Les colonnes d'aujourd'hui (Paiement, Âge, Inviter, Statut de connexion…) sont décrites dans
`frontend/src/data/colonnesEleves.js` ; leur déclaration par les modules dans `module.py` (§11.1)
viendra avec les modules Paiement et Licences.

**Fait (27 octobre 2026, étape 4c)** : la reprise des champs d'`eleves`. Date de naissance,
Adresse, Allergies, Traitement médical et Informations importantes sont des champs de la fiche
comme les autres (en tête, Facultatif ; Date ou Texte long) : l'école les renomme, les range, les
retire. Chacun porte une marque cachée (`member_fields.key` : `birth_date`, `address`,
`allergies`, `medical_treatment`, `important_info`) par laquelle l'appli les retrouve : l'âge, le
dossier d'inscription, l'import et l'export Excel, l'assistant (qui ne reçoit toujours jamais la
santé). Leur format ne change pas. Un champ marqué retiré garde ses réponses, continue d'être
rempli par l'inscription et l'import, et passe retiré à la saison suivante. Les réponses ont été
recopiées dans `member_values` (migration) ; les colonnes de `profils_eleves` restent en base, plus
lues ni écrites. Dans Admin > Élèves, les colonnes Date de naissance, Adresse et Santé deviennent
les colonnes de ces champs (la Santé en trois colonnes), à la même place ; dans la fiche de
l'élève, ils sont dans « Nos champs » (l'âge à côté de la date). Une sauvegarde d'avant reprend ces
champs à la restauration. Restent sur `profils_eleves` : Contacts (plusieurs personnes),
Commentaire, Paiement (avec le module Paiement).

### 4.4 Famille = même email du payeur

Chaque fiche a un champ du socle **Email du payeur** : pour un adulte, son propre email ; pour un
enfant, l'email du parent qui paie. HelloAsso le remplit depuis la commande ; la reprise de
Contretemps le remplit depuis l'email du parent. La **famille** est l'ensemble des fiches qui ont le
même email du payeur, **calculée**, jamais éditée à la main. Le payeur se connecte avec cet email et
voit ses enfants (sélecteur de profil, §6). Une famille n'est pas un groupe.

**Aujourd'hui** : famille = fiches reliées par un email commun de proche en proche
(`recalculer_familles`, table `familles`). À remplacer par l'email du payeur, avec une commande de
reprise.

### 4.5 Sélecteur de profil

Façon Netflix : il montre les fiches rattachées à **l'adresse connectée**, pas toute la famille. Un
parent connecté avec son email bascule entre ses enfants sans se reconnecter ; un enfant connecté
avec son propre email ne voit que sa fiche. Les mails de l'appli partent vers toutes les adresses de
la fiche.

---

## 5. Groupes et droits

Décisions de Seb du 26 octobre 2026, inspirées d'AssoConnect, pour simplifier : tout ce qui réunit
des personnes est un **groupe**, et un cours, les profs, le bureau, un droit sont des groupes.

### 5.1 Groupes et sous-groupes

- Un groupe a un nom, une organisation, une saison ou « permanent », et des membres. Les groupes
  des modules ont un **parent** (un seul niveau) : le parent réunit automatiquement les membres de
  ses sous-groupes et dit le genre du groupe. Exemples : Cours › Salsa, Cours › Éveil ;
  Bureau › Président·e, Vice-président·e, Secrétaire, Trésorier·e ; Profs ; Bénévoles.
- Pas de colonne « nature » : un cours est un sous-groupe de « Cours », parent qui appartient au
  module Cours. Le module ajoute ses données **par composition** (clé étrangère vers le groupe,
  ex. `course_details` : jour, horaire, salle, profs), jamais par héritage.
- Un groupe réunit des **personnes seulement**. Les produits (une pizza, un stage à vendre) sont
  dans le catalogue, pas dans les groupes ; un produit peut pointer vers un groupe
  (`products.group_id`) : l'acheter fait entrer dans le groupe.
- Qui change les groupes : les admins, sauf les groupes de droit (§5.3). Les groupes des modules
  (Cours, Profs, Bureau) sont créés par le core quand le module est allumé (§11.1) et ne se
  suppriment pas ; module éteint = groupe caché, données gardées.
- Tout ce qui vise des personnes vise un groupe : messagerie, Docs (un dossier peut être réservé à
  des groupes, voir / modifier, hérité par les sous-dossiers), envois d'emails, signatures, présence.
- Élèves = l'ensemble des membres (pas un groupe). **Profs** = groupe « Profs » (mot du Vocabulaire) ;
  le rôle Professeur de Contretemps disparaît. **Bureau** = groupe Bureau avec ses sous-groupes
  (plusieurs membres possibles, ajout d'une fonction possible) ; `comptes.bureau_functions` disparaît.
  Trésorier·e est un titre, qui ne donne aucun droit.

### 5.2 Écran

Admin > Administrateurs (maquette « Admins nouveau style ») : colonnes Nom | **Groupes** (pastilles,
toutes du même gris ; seul 🔒 distingue un groupe de droit ; « Bureau » apparaît quand la personne
est dans un de ses sous-groupes) | Principal | Statut. La feuille d'ajout propose Bureau et ses
fonctions, Profs, Bénévoles, les 🔒 droits (grisés sauf pour l'Administrateur principal et le Super
User), « + Nouveau groupe… ». Dans Asso in the Pocket, les cases **Cours** et **Profs** de
Personnalisation > Fonctionnalités allument ces modules et leurs onglets Admin > Cours et
Admin > Profs ; Bureau est toujours là.

### 5.3 Un droit = un groupe

Un droit ouvert par un module (voir l'onglet Financier, lire son dossier) n'est jamais implicite : c'est
un **groupe 🔒 au nom du droit**, ex. « Accès au Financier ». Le module le déclare dans son
`module.py` (`Right("finances.access", "Accès au Financier")`), le core crée le groupe et le
contrôle : `has_right(membre, "finances.access")` côté serveur, une seule fonction pour toutes les
routes. Le Super User passe toujours. L'Administrateur principal et le Super User sont seuls à mettre
ou retirer quelqu'un d'un groupe de droit ; l'Administrateur principal **ne passe pas** sans être dans
le groupe, il se coche lui-même s'il veut (décision de Seb du 27 octobre 2026, comme le 17 octobre :
le Financier pour les trésoriers seulement). Les autres groupes ne donnent aucun droit par eux-mêmes :
seulement là où on les a choisis (dossier réservé, envoi, conversation).

**Aujourd'hui** : la coche `is_tresorier` (« Accès au Financier »), à reprendre vers le groupe ;
les rôles cumulés de `comptes/roles.py` ; la table `cours` utilisée par la messagerie, les vidéos et
la présence. Gros chantier, par étapes, chacune sur le « vas-y » de Seb.

**Données** : `groups` (`org_id`, `season_id` ou vide pour « permanent », `parent_id`, `key` pour
les groupes que le code connaît — `board`, `board.president`… —, vide pour un groupe fait à la main,
`name`), `group_members` (`group_id`, `member_id` = la fiche de la saison). Code : `backend/src/groups/`.
Une fiche fusionnée garde ses groupes, une fiche supprimée les quitte ; les groupes d'une saison
partent avec elle et sont dans la sauvegarde technique (onglets « Groupes », « MembresGroupes »).

**Fait (27 octobre 2026, étape 1a)** : les tables, et le **bureau** en groupes (`groups/board.py`) : un
groupe « Bureau » et ses sous-groupes par école et par saison, créés à la première demande ; recopiés
à la création d'une saison. La migration reprend `comptes.bureau_functions`, qui n'est plus lue ni
écrite (colonne gardée en base, à supprimer plus tard). L'API et l'écran n'ont pas changé
(`bureau_functions` dans Admin > Administrateurs et l'action `change_roles` de l'assistant).

**Fait (27 octobre 2026, étape 1b)** : les **Profs** en groupe (`groups/teachers.py`) : un groupe « Profs »
par école et par saison, clé `teachers`. Le rôle Professeur n'est plus une ligne de `roles_compte` ; la
migration y reprend les profs. `comptes/roles.py` le présente toujours comme un rôle (`is_prof`, liste
`roles` de l'API, même rang) : un prof voit et fait exactement la même chose, rien ne change à l'écran.
Le groupe est recopié à la nouvelle saison (case « profs »), suit la fusion et la sauvegarde ; une
ancienne sauvegarde avec des lignes « professeur » est convertie à la restauration.

**Fait (27 octobre 2026, étape 3)** : chaque **cours est un groupe**, sous-groupe de « Cours » (clés
`courses` et `course`, `groups/courses.py`), un jeu par école et par saison. Ses membres sont les élèves
du cours. La table `cours` joue le rôle de `course_details` (elle garde son nom) : jour, horaire, salle,
profs (`cours_professeurs`), et `cours.group_id` vers son groupe. Créer, renommer, supprimer un cours
fait de même avec son groupe ; inscrire un élève le met dans le groupe. La migration reprend
`eleves_cours`, qui n'est plus lue ni écrite (table gardée en base, à supprimer plus tard).
Messagerie, vidéos, présence, Docs et assistant lisent toujours les élèves d'un cours par le cours,
donc maintenant par son groupe : rien ne change à l'écran. Les cours et leurs élèves sont recopiés à la
nouvelle saison avec leur groupe ; une ancienne sauvegarde (onglet ElevesCours) est convertie à la
restauration. Plus tard : viser n'importe quel groupe (pas seulement un cours) dans la messagerie et Docs.

**Fait (27 octobre 2026, étape 1c)** : Admin > École > Administrateurs, colonne **Groupes** à la place des
colonnes « Accès au Financier » et « Bureau » (les autres colonnes ne changent pas). Toucher la case ouvre
la feuille : Bureau et ses fonctions, Profs, les groupes faits à la main, 🔒 Accès au Financier,
« + Nouveau groupe… » ; chaque case s'enregistre tout de suite, Annuler 10 s. **Tout admin** change les
groupes, sa ligne comprise ; 🔒 Accès au Financier reste à l'administrateur principal et au Super User
(encore le rôle `tresorier`, étape 2). Groupes faits à la main (`groups/custom.py`) : nom unique dans la
saison, recopiés avec leurs membres à la nouvelle saison ; pas encore de renommage ni de suppression.

**Fait (27 octobre 2026, étape 2)** : `Right(key, label)` dans `registry/`, déclaré par le module
Financier (`Right("finances.access", "Accès au Financier")`) ; le core en fait un groupe 🔒 par école et
par saison, clé `right.finances.access` (`groups/rights.py`), recopié à la nouvelle saison. Le rôle
`tresorier` n'est plus une ligne de `roles_compte` ; la migration y reprend les trésoriers.
`comptes/roles.py` : `has_right(compte, droit)` (Super User, ou membre du groupe) contrôle le
Financier ; `is_tresorier` et la liste `roles` de l'API restent (rôle présenté depuis le groupe), si bien
que l'écran et le dossier Financier de Docs ne changent pas. Les notes de frais lisent encore
`is_tresorier` (même groupe). Reste : le contrôle des dossiers réservés de Docs par `has_right`, et un
écran qui liste les droits déclarés au lieu de la case « Accès au Financier » écrite en dur.

---

## 6. Connexion

Décisions du 1er et 2 octobre 2026, en ligne. Code : `auth/`, `acces/`, `securite/`, `comptes/rbac.py`.

### 6.1 Écran de connexion

Une seule page pour toutes les organisations : **« Nom Prénom ou Email »**, **« Mot de passe »**
(œil pour l'afficher), bouton **Se connecter**, lien **« Mot de passe oublié ? »**. Pas de
« Nouvelle organisation » : la création est réservée au Super User (§3). Sur l'adresse d'une
organisation, la personne est cherchée d'abord dans cette organisation, puis dans toutes (sans
majuscules ni accents) ; trouvée ailleurs, elle est envoyée vers l'adresse de son organisation.
- un seul compte trouvé : connexion directe ;
- plusieurs organisations possibles : fenêtre **« Choisissez votre organisation »**, seulement dans
  ce cas ;
- plusieurs profils de la même organisation à cet email (une famille) : on arrive sur le profil de
  plus haut rang, puis le plus ancien ; par son nom et prénom, chacun arrive sur sa fiche.
Seules les fiches de la saison courante se connectent (§8). Plusieurs appareils en même temps ;
déconnexion depuis Profil. Le Super User utilise le même écran.

### 6.2 Un mot de passe par adresse email

Le mot de passe appartient à une **adresse email** (table `acces_emails`), pas à une fiche : les
profils qui partagent un email partagent son mot de passe ; une fiche à plusieurs emails a un mot
de passe par email ; le mot de passe survit à la recopie des fiches à chaque saison. Une fiche sans
email ne se connecte pas ; un enfant utilise l'email d'un parent. Haché (scrypt), 8 caractères au
moins, sans autre règle. **Essais limités** : 5 mots de passe faux bloquent l'email 15 minutes, avec
un message qui ne révèle pas si le compte existe.

### 6.3 Session : un jeton signé

À la connexion, le serveur délivre un **jeton signé** qui désigne l'adresse connectée et le rang du
profil ; l'appli le garde sur l'appareil et l'envoie à chaque requête avec le profil actif
(`X-Compte-Id`), que le serveur vérifie contre l'adresse du jeton : un `X-Compte-Id` seul ne donne
aucun droit. Durée **30 jours, prolongés à chaque usage** ; 12 heures pour le Super User. Changer de
mot de passe déconnecte tous les autres appareils (le jeton porte une empreinte du mot de passe).
**Toutes les routes exigent une session**, sauf une courte liste publique (`ROUTES_PUBLIQUES` :
connexion, liens reçus par mail, mot de passe oublié, inscription publique, manifest et icônes par
adresse) qu'un test parcourt ; un module qui ajoute une route publique la déclare dans cette
liste. Le flux temps réel reçoit le jeton dans son adresse ; les fichiers se lisent par lien signé
à durée limitée.

**Bascule de profil** (famille) sans reconnexion, parmi les profils rattachés à l'email connecté ;
**une montée en privilège redemande le mot de passe** (Membre < Profs < Admin). **Dernier écran
retenu** : à la réouverture, l'appli revient sur le dernier onglet, et dans Admin sur le dernier
sous-onglet, conservé sur l'appareil même après déconnexion.

### 6.4 Invitation

1. L'organisation saisit la personne avec son email (à la main, import, HelloAsso).
2. **Un admin l'invite par un bouton**, jamais automatiquement (colonne « Inviter » et colonne
   « Statut » dans la liste des membres ; « Inviter tous les non-invités » en tête de colonne).
3. **Un seul mail par adresse**, même avec plusieurs profils : « <Organisation> vous invite sur
   l'application. Profils : Léa, Tom. [Créer mon mot de passe] ». Titre neutre, version texte et
   mise en forme, « Bonjour Prénom Nom, ».
4. **Le lien** `https://<adresse>/activer?jeton=…`, personnel, à usage unique, **15 jours**, haché
   en base ; renvoyable, le nouveau annule l'ancien.
5. Le clic ouvre l'appli Android si elle est installée (App Links https, `assetlinks.json` servi par
   Caddy, clé de signature stable), sinon la même page dans le navigateur, qui propose ensuite
   d'installer l'appli.
6. **Écran « Créer mon mot de passe »** : email affiché, prénoms des profils, mot de passe saisi deux
   fois, œil.
7. À la validation, la personne est **connectée directement**, avec la proposition de notifications.

**Suivi de l'invitation**, enregistré par l'appli elle-même, sur l'adresse email (une ligne par
adresse) : *Pas d'email* (bouton grisé) → *Pas invité* → *Invité le …* → *Invitation consultée
le …* (lien cliqué, jamais « mail ouvert », qui n'est pas fiable) → *Profil finalisé le …* (mot de
passe créé) → *Appli installée le …* (§10).

### 6.5 Mot de passe oublié

Demande le nom prénom ou l'email, répond toujours « Si ce compte existe, un lien vient d'être
envoyé » ; **toute personne dont l'email figure dans une organisation reçoit le lien, même jamais
invitée** (elle prouve qu'elle contrôle l'adresse). Lien valable **1 heure**, à usage unique, écran
« Nouveau mot de passe » identique à « Créer mon mot de passe ». Demandes limitées dans le temps.
Changement de mot de passe aussi depuis Profil (ancien mot de passe redemandé). Plus tard : double
authentification, en option dans Profil.

---

## 7. Niveaux

| Niveau | Ce qu'il peut faire | Qui le donne |
|---|---|---|
| **Membre** | Utiliser l'appli pour lui-même et sa famille | Un admin, en créant la fiche |
| **Admin** | Gérer l'organisation : personnes, groupes, réglages | L'Administrateur principal |
| **Administrateur principal** | Un admin qui gère en plus les admins, les groupes de droit et les Fonctionnalités | Un Administrateur principal ou le Super User |
| **Super User** | Tout, dans toutes les organisations | Une commande sur le serveur, jamais l'appli |

- Les niveaux se cumulent, imposés par le serveur et pas seulement cachés à l'écran. Tout autre
  droit est un groupe (§5.3) ; Trésorier n'est plus un niveau.
- Il reste toujours au moins un Administrateur principal par organisation ; personne n'agit sur sa
  propre ligne. Seul le Super User dépanne une organisation sans Administrateur principal.
- Le **Super User** n'appartient à aucune organisation. Après connexion, il choisit où il intervient
  et la voit comme un Administrateur principal. Absent des listes de personnes, mais on peut le
  trouver et l'ajouter dans les conversations de toute organisation (nom et prénom seulement).
- **Un seul endroit pour lire les droits** : `is_admin`, `require_admin`, `has_right`… côté
  serveur ; `frontend/src/data/roles.js` côté appli. Aucune route ni écran ne teste un niveau
  lui-même.

---

## 8. Saisons

Une association vit par années ; la fiche d'une personne, sa structure (§4.3), ses groupes de
saison et ses tarifs (§9) sont par saison. Une organisation sans saisons (une pizzeria) en a une
seule, sans fin, et ne voit jamais le mot « saison ». *(Fil ouvert du 24 octobre : faire de
Saisons un module optionnel, la période restant dans le core ; attend le « vas-y » de Seb.)*

- Saison courante = la dernière créée ; elle seule est modifiable, les autres en lecture seule,
  imposé par le serveur (`saisons/portee.py` : un module ne filtre jamais la saison à la main).
  Seules les fiches de la saison courante se connectent ; le mot de passe traverse les saisons.
- **Créer une saison** (maquette « Créer une saison ») : **un seul écran prérempli** — nom, dates,
  puis une ligne par morceau, chacune avec ce qui sera fait et un bouton « Changer… » — et un seul
  bouton « Créer la saison ». Les morceaux, dans l'ordre :
  1. **L'école** : administrateurs et bureau repris, **tarifs** repris de la saison précédente (§9) ;
  2. **Membres** : la structure (§4.3, écran « Champs des membres » tel quel) reprise de la saison
     précédente ou imposée par HelloAsso, puis les données : recopier les fiches ou repartir vide ;
  3. **Profs**, 4. **Cours** (si ces modules sont allumés) : groupes repris ou non ;
  5. ce que chaque autre module propose de recopier (Documents : dossiers de la saison).
  Par défaut tout est repris de la saison précédente ; l'organisation ne change que ce qu'elle veut.
- Seuls les admins consultent une ancienne saison (bandeau lecture seule, §10.4). À la création
  d'une saison, chaque appareil bascule tout seul sur la nouvelle fiche (notifications comprises) ;
  une personne non reprise est déconnectée.
- **Supprimer une saison** (admins) : on choisit la saison, on lit ce qui sera supprimé, on retape
  son nom ; sauvegarde technique complète juste avant ; les fiches de la saison suivante sont
  reliées à celle d'avant.

---

## 9. Tarifs : formules, options et codes promo

Décisions de Seb du 26 octobre 2026, inspirées de HelloAsso et d'AssoConnect. Écran : étape
« L'école » de la création de saison et Admin > École > Tarifs ; « Reprendre ceux de
<saison précédente> » en haut. Maquette : Tarifs de la saison.

### 9.1 Formules

Une **formule** est ce qu'un membre choisit pour la saison : un **nom**, un **tarif**, une ou
plusieurs **échéances** (date et montant ; la somme fait le tarif ; une seule échéance
« À l'inscription » par défaut ; « + Ajouter une échéance » répartit le tarif, chaque date et montant
se corrige à la main). « Dupliquer » pour faire « en 3 fois » à partir de « en 1 fois ». Rien d'autre
sur la formule. Exemples : Contretemps = Adhésion + 1 cours, + 2 cours, + 3 cours, chacune en 1 fois
ou en 3 fois (six formules) ; ASC Sambo La Ciotat = Solo, Famille duo, Famille trio, en 1 ou 3 fois.

### 9.2 Options et codes promo

Une seule liste, un seul objet : un **nom**, un **montant en plus ou en moins**, en € ou en %, et
**comment l'obtenir** :
1. **La personne coche** (t-shirt +15 €, stage +60 €), avec quantité limitée possible ;
2. **Avec un code** (BIENVENUE −10 %, FAMILLE −5 %), nombre d'utilisations et date limite ;
   case **Montrer dans le formulaire** : montré, la personne le coche ; secret, elle doit le taper ;
   plusieurs codes séparés par des virgules ;
3. **Règle** écrite en français (« Enlever 10 € par année d'ancienneté, 50 € maximum ») : le bouton
   « Faire comprendre la règle » l'envoie à l'assistant, qui répond « Compris : … » avec un exemple
   sur un membre et un calcul Python gardé en base ; la règle s'applique toute seule au paiement, à
   partir de la fiche. L'assistant n'écrit jamais un chiffre lui-même : c'est le calcul qui tourne.
Chaque option ou code dit sur quelles formules il s'applique (toutes par défaut) et s'il est proposé
cette saison.

### 9.3 Avec HelloAsso

Si la saison impose une campagne HelloAsso (§4.3), **les tarifs sont ceux de HelloAsso** : formules,
options et codes promo de la campagne, en lecture seule chez nous ; les membres s'inscrivent et
paient sur HelloAsso, on récupère la fiche, la formule choisie et les paiements
(`modules/helloasso.md`). Sans HelloAsso, les formules sont à nous et servent au formulaire
d'inscription de l'appli, **à concevoir plus tard** (pas de maquette validée).

**Données** (cible) : `season_plans` (saison, nom, tarif, actif, ordre), `season_plan_installments`
(formule, date, montant), `season_adjustments` (saison, nom, montant, unité, mode coche / code /
règle, code, montré, utilisations max, date limite, règle en français, calcul, actif), lien
formule ↔ ajustement ; `member_plan` (membre, formule, ajustements appliqués, codes saisis).

**Aujourd'hui** : `inscriptions/tarifs.py` (adhésion 40 €, réduction famille 35 € / 31,60 €, paliers
par cours, barèmes mensuel et trimestriel) et `SPEC-inscription.md`, à remplacer par les formules.

---

## 10. Installation, notifications et navigation

### 10.1 Installation sur le téléphone

Appli web installable (PWA, manifest et service worker), appli Android en plus (`ANDROID.md`,
Capacitor). Chaque organisation a son adresse (§3), donc **son nom et son icône** sur l'écran
d'accueil, une installation, un cache et des abonnements push par organisation. Après la création
du mot de passe, l'appli propose de s'installer (écran d'installation, `frontend/src/api/installation.js`).
L'installation est enregistrée sur l'adresse de connexion (« Appli installée le … ») : sur Android
Chrome et sur ordinateur, à l'événement `appinstalled` ; sur iPhone, Safari Mac et Samsung Internet,
qui n'en ont pas, à la première ouverture depuis l'icône (mode standalone) ; appli native, à la
première ouverture. Le premier signal fixe la date. Changer de logo ou d'adresse demande de
réinstaller sur iPhone ; un avertissement le dit avant d'enregistrer ; Android se met à jour seul.

### 10.2 Notifications push

Web Push (norme W3C, `backend/src/notifications/`, clés VAPID, `pywebpush`, `public/sw.js`
`push` / `notificationclick`) : abonnement **par appareil**, demandé sur un vrai clic (jamais au
chargement), bouton « Notifications » de Profil qui reflète l'abonnement réel de cet appareil,
**réabonnement silencieux à chaque connexion** (`reabonnerSiAutorise`), donc les notifications
suivent la nouvelle fiche après un changement de saison. Déclenchées par un nouveau message à
chaque membre sauf l'expéditeur, et par les modules qui le demandent (envois de Docs, signatures).
Appli Android native : Firebase Cloud Messaging viendra si elle est un jour distribuée.

### 10.3 Profil

Identité de la personne connectée, autres profils de la famille (bascule, §6.3), paramètres
(notifications, changer mon mot de passe), lignes ajoutées par les modules (« Mes notes de frais »,
« Mes heures »), bouton **Se déconnecter**.

### 10.4 Navigation et style

- **Barre du bas** = les fonctions (onglets des modules, entre Admin et Profil, dans l'ordre de la
  liste des modules, §11.2) ; les onglets d'un écran = ses sous-fonctions ; jamais de 4e niveau.
  Quand les onglets ne tiennent pas, les derniers passent sous « Plus » (⋯) en bas à droite, menu
  modal au-dessus de tout ; l'onglet actif caché allume « Plus », les pastilles s'y additionnent.
  Le bandeau du haut est épuré : ← et le nom quand un fichier est ouvert, une place par onglet
  pour ses boutons.
- **Ancienne saison** : bandeau « lecture seule » avec « Revenir à la saison courante », boutons
  d'écriture masqués, écriture refusée par le serveur.
- « Gros et simple » : texte ≥ 17 px, touches ≥ 48 px, un bouton principal par écran, 3 questions
  max, menu ≤ 6 actions + « Plus… », **Annuler 10 s** plutôt que confirmer, retour par ← (geste
  Android), jamais de croix. Mobile d'abord ; les mêmes fonctions sur ordinateur.

---

## 11. Enregistrement des modules

Décision de Seb du 19 octobre 2026, codée et en ligne le 24 octobre (PR #60 à #68) : le core ne
connaît pas les modules, ce sont eux qui se présentent. Code : `backend/src/registry/`.

### 11.1 La déclaration d'un module

Un fichier côté serveur, `backend/src/<module>/module.py` (ou `<module>_contretemps/module.py` quand
c'est l'appli qui relie le module à ses fiches), et un côté écran,
`frontend/src/modules/<module>/module.js`. Rien d'autre ne décrit le module.

```python
MODULE = Module(
    key="finances", label="Financier",
    mount=mount,                                   # mount(app, core) monte les routes
    requires=("documents",),                       # modules à monter avant lui
    actions=lambda core: actions(core.finances),   # actions ouvertes à l'assistant (actions.py)
    rights=(Right("finances.access", "Accès au Financier"),),  # cible : un groupe 🔒 par droit (§5.3)
    groups=(Group("Bureau", children=("Président·e", "Vice-président·e", "Secrétaire", "Trésorier·e")),),
    columns=(Column("Montant payé", compute=amount_paid),),    # cible : colonnes d'Admin (§4.3)
    buttons=(Button("Demander la licence", action="ffst.request"),),
)
```

- `mount` reçoit l'appli FastAPI et les services du core (fiche appelante, droits, email,
  notifications, saison, stockage) ; il range dans `core` ce qu'il construit. Un module n'importe
  jamais un autre module : l'appli les relie dans `<module>_contretemps/`.
- `actions` : la liste de l'assistant, prise telle quelle dans `actions.py`
  (`spec/modules/assistant-ia.md` §3). Un bouton de l'écran = une action de l'assistant.
- `rights`, `groups`, `columns`, `buttons` *(cible, étude du 26 octobre)* : ce que le module apporte
  au core ; le core crée les groupes et les droits quand le module est allumé, et propose les
  colonnes dans l'affichage d'Admin. Le champ `roles` d'aujourd'hui (Professeur, « Accès au
  Financier ») disparaît au profit de `rights` et `groups`.
- Les tables d'un module restent dans son `models.py`, préfixées par le module (`doc_`, `nf_`),
  créées par Alembic.
- Côté écran, `module.js` déclare `tabs` : les onglets de la barre du bas (clé, libellé, icône, qui
  les voit, écran). Montrer ou cacher seulement ; le vrai contrôle reste sur chaque route.

### 11.2 La liste des modules de l'appli

Une seule liste, une ligne par module, `backend/src/app/modules.py` et `frontend/src/app/modules.js`.
Au démarrage, le core vérifie les `requires` (sinon refuse de démarrer, message clair), monte les
routes, donne à l'assistant les actions de tous les modules. Les onglets du core : Admin, Profil,
Supervision (Super User). Chaque produit a sa propre liste, avec le même core.

### 11.3 Modules allumés par organisation

- Table `org_modules` (organisation, module, allumé, date) ; **pas de ligne = allumé**.
- Module éteint pour une organisation : pas d'onglet, pas de bouton d'en-tête, pas d'action de
  l'assistant, routes « introuvable » (vérifié une fois pour toutes par le core, juste après la
  session ; pas pour les routes publiques ni le Super User), groupes cachés. **Éteindre n'efface
  rien.** On n'éteint pas un module dont un autre a besoin ; allumer un module allume ceux qu'il
  requiert.
- Écran : Admin > École > Personnalisation de l'application > Fonctionnalités, une case par module
  (Administrateur principal et Super User). À la création d'une organisation, les défauts du produit.
- Pas encore : routes publiques de Documents non bloquées ; choix des modules à la création d'une
  organisation.

---

## 12. Services communs aux modules

Déjà codés dans Contretemps :
- **Email** : relais SMTP Brevo (domaine authentifié, DKIM et DMARC), adresse d'expédition du
  produit au nom de l'organisation, réponses vers son email de contact, suivi de remise (webhook),
  pièces jointes. Code : `auth/mails.py`, `send_email`.
- **Notifications push** : §10.2.
- **Sauvegarde** : par organisation (Excel, Google Drive, périodicité réglable), sauvegarde technique
  complète avant toute suppression lourde. Code : `ecoles/`, `app/sauvegarde_worker.py`.
- **Temps réel** : flux par session (messagerie).
- **Stockage** : contenus par empreinte, liens signés à durée limitée. Code : `storage/`.
- **Assistant** : chaque module lui déclare ses actions ; l'assistant n'écrit jamais un chiffre, ne
  voit jamais la santé des membres (`spec/modules/assistant-ia.md`).

---

## 13. Étapes de code (chacune une PR, sur le « vas-y » de Seb)

1. **Groupes**, en trois PR :
   a. tables `groups` et `group_members`, Bureau en groupes, reprise de `bureau_functions`
      *(faite le 27 octobre 2026)* ;
   b. Profs en groupe, reprise du rôle Professeur *(faite le 27 octobre 2026)* ;
   c. Admin > Administrateurs nouveau style (colonne Groupes, maquette) *(faite le 27 octobre 2026)*.
2. **Droits** : `Right` dans `module.py`, groupe « Accès au Financier », `has_right`, reprise de
   `is_tresorier` *(faite le 27 octobre 2026)*.
3. **Cours = groupes** : `course_details`, messagerie, vidéos et présence sur les groupes *(faite le
   27 octobre 2026 ; la table `cours` tient lieu de `course_details`)*.
4. **Champs des membres**, en trois PR :
   a. `member_fields`, `member_values`, écran « La fiche d'un membre », réponses dans la fiche de
      l'élève *(faite le 27 octobre 2026)* ;
   b. `member_columns`, écran « Affichage dans Admin », colonnes du tableau des élèves *(faite le
      27 octobre 2026)* ;
   c. reprise des champs d'`eleves` (date de naissance, adresse, santé…) dans la fiche *(faite le
      27 octobre 2026)*.
5. **Famille** par l'email du payeur, commande de reprise.
6. **Création de saison** en un écran, étape par étape.
7. **Tarifs** : formules, options, codes promo, règles par l'assistant.
8. **HelloAsso** (`modules/helloasso.md`) : connexion, campagne imposée, synchronisation.
9. Formulaire d'inscription de l'appli (à concevoir).

---

## 14. Reste à décider

- Le mot pour « membre + compte de connexion » (membre, compte utilisateur).
- Saisons en module optionnel (fil du 24 octobre).
- Postgres : dès l'extraction du core, ou plus tard.
- Catalogue (produits, `products.group_id`) : spec à écrire quand un produit en aura besoin.
