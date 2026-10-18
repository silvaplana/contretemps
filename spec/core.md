# AppBase — Spécification du core (socle commun)

Version 0.1 du 18 octobre 2026. Destinataire : Claude Code.

Le **core** est ce que toute appli bâtie sur AppBase a toujours, quels que soient les modules
choisis : l'organisation, les personnes, la connexion, les niveaux d'accès, l'installation sur
le téléphone. Tout le reste (Documents, Financier, messagerie, cours…) est un **module**
optionnel, décrit dans `spec/modules/`.

Ce socle est déjà spécifié et en grande partie codé dans Contretemps, dans `SPEC.md` §2 et §6,
avec les mots de la danse. Ce document le **généralise** : il dit la règle commune et renvoie
au paragraphe de `SPEC.md` qui en donne le détail, tant que ce détail n'a pas été déplacé ici.
En cas de désaccord entre les deux, ce document l'emporte pour AppBase ; `SPEC.md` reste la
référence de ce qui est propre à Contretemps.

Décisions de Seb du 18 octobre 2026 : spec du core à part (ce fichier) ; la saison reste dans
le core ; Professeur est un rôle ajouté par Contretemps, pas un niveau du core ; le trésorier
est toujours un admin, mais un admin n'est pas forcément trésorier, et seuls le trésorier et
le Super User ont l'onglet Financier et le dossier Financier de Docs.

---

## 1. Ce qui est dans le core, ce qui n'y est pas

| Dans le core | Hors du core (module ou appli) |
|---|---|
| Organisation : création, étanchéité, adresse web, apparence | Cours, planning, présence (Contretemps) |
| Personnes, emails, familles, sélecteur de profil | Fiche élève : santé, contacts, paiement (Contretemps) |
| Connexion : mot de passe, invitation, session | Inscription publique, import Excel |
| Niveaux : Membre, Admin, Administrateur principal, Trésorier, Super User | Rôles métier : Professeur (Contretemps), Serveur (pizzeria)… |
| Saisons | Messagerie, vidéos, chorégraphies |
| Installation de l'appli sur le téléphone | Documents, Fichier de base |
| Modules activés pour une organisation | Financier, notes de frais |
| Envoi d'emails, notifications push, sauvegarde | Assistant |

---

## 2. Les mots

| Dans AppBase | Dans Contretemps aujourd'hui | Ce que c'est |
|---|---|---|
| **Organisation** | École (`ecoles`) | Une association, un club, une pizzeria. Ses données sont étanches. |
| **Fiche** | Compte (`comptes`) | Une personne dans une organisation, pour une saison. |
| **Adresse de connexion** | `acces_emails` | Une adresse email, avec son mot de passe. |
| **Famille** | Famille (`familles`) | Les fiches reliées par une adresse email commune. |
| **Niveau** | Rôle du core | Ce que la personne a le droit de faire dans le core. |
| **Rôle métier** | Professeur | Un rôle ajouté par l'appli, avec ses propres droits. |
| **Saison** | Saison (`saisons`) | Une année d'activité. |

À l'écran, chaque appli choisit le libellé du niveau Membre : « Élève » dans Contretemps,
« Adhérent » dans un club, « Client » dans une pizzeria. Le reste des libellés est commun.
Jamais de mot technique à l'écran (ni « Owner », ni « rôle », ni « tenant »).

Le code de Contretemps garde ses noms français (`ecole_id`, `comptes`) tant que le core n'en
est pas extrait. Les modules nouveaux écrivent déjà en anglais (`org`, `member`, `group`).

---

## 3. Organisation

Détail : `SPEC.md` §2.1, §2.3, §2.7, §6.1.

- **Étanchéité** : une organisation ne voit jamais les données d'une autre. Toute table qui
  appartient à une organisation porte son identifiant, et chaque route sait quelle organisation
  elle touche et la passe au contrôle des droits (§6). Un admin d'une organisation n'a aucun
  droit sur une autre.
- **Création** : par le Super User seulement. Il saisit le nom, le code postal et le premier
  administrateur, qui devient **Administrateur principal** et reçoit une invitation (§5).
- **Fiche de l'organisation** : nom, code postal, adresse, SIRET, IBAN, email de contact,
  email du trésorier. Les mails envoyés par l'appli partent avec le nom de l'organisation et
  répondent à son email de contact.
- **Adresse web** : un sous-domaine par organisation (`<adresse>.<appli>.silvaplana.cloud`),
  choisi par l'organisation, pour que chacune ait son nom et son logo sur l'écran d'accueil du
  téléphone. L'ancienne adresse reste valable un temps après un changement.
- **Apparence** : logo, nom (texte ou image), slogan, couleurs, polices.
- **Modules activés** *(nouveau, à spécifier)* : la liste des modules dont l'organisation se
  sert. Un module non activé n'a ni onglet, ni route, ni table remplie pour elle. Choisi par le
  Super User à la création ; plus tard, peut-être par l'Administrateur principal.

---

## 4. Personnes, emails et familles

Détail : `SPEC.md` §2.1, §6.2, §6.3.

- Une **fiche** par personne, dans une organisation, pour une saison (§7). Nom, prénom,
  téléphone, et **plusieurs emails** tous équivalents (aucun « principal »). Les champs propres
  à un rôle métier (date de naissance, santé, paiement d'un élève) vivent dans le module ou
  l'appli, jamais dans la fiche du core.
- **Famille** : toutes les fiches reliées par au moins un email commun, de proche en proche,
  dans une même organisation. Recalculée automatiquement, jamais éditée à la main. C'est ce
  que voit l'admin.
- **Sélecteur de profil** (façon Netflix) : il montre les fiches rattachées à **l'adresse
  connectée**, pas toute la famille. Un parent connecté avec son email bascule entre ses enfants
  sans se reconnecter ; un enfant connecté avec son propre email ne voit que sa fiche.
- Les mails de l'appli partent vers **toutes** les adresses de la fiche ; les invitations, une
  par adresse.

---

## 5. Connexion

Détail : `SPEC.md` §2.2, §6.3ter. Code : `auth/`, `acces/`, `securite/`, `comptes/rbac.py`.

- **Un mot de passe par adresse email**, pas par fiche. Haché (scrypt), 8 caractères au moins.
  Une fiche sans email ne se connecte pas ; un enfant utilise l'email d'un parent.
- **Écran de connexion unique** pour toutes les organisations : « Nom Prénom ou Email » et mot
  de passe. Si la même personne est dans deux organisations, une fenêtre « Choisissez votre
  organisation » s'ouvre, et seulement dans ce cas.
- **Invitation** : un admin invite par un bouton, jamais automatiquement. Un seul mail par
  adresse, avec les prénoms des profils. Lien à usage unique valable 15 jours, renvoyable.
  Suivi de chaque étape dans la liste des personnes (invitée, mail remis, lien ouvert, mot de
  passe créé, appli installée).
- **Mot de passe oublié** : même lien, même écran.
- **Session** : jeton signé, 30 jours prolongés à chaque usage, 12 heures pour le Super User.
  Changer de mot de passe déconnecte les autres appareils. Le profil actif est envoyé à chaque
  requête et vérifié contre l'adresse du jeton.
- **Montée en privilège** : passer à un profil de niveau plus élevé de la même famille redemande
  le mot de passe.
- **Essais limités** : 5 mots de passe faux bloquent l'adresse 15 minutes.
- **Toutes les routes exigent une session**, sauf une liste publique courte et testée. Un module
  qui ajoute une route publique la déclare dans cette liste.
- **Plus tard** : double authentification, en option dans Profil.

---

## 6. Niveaux et rôles

Détail : `SPEC.md` §2.1, §2.4, §2.5, §3, §6.3bis. Code : `comptes/roles.py`, `comptes/rbac.py`.

### 6.1 Les niveaux du core

| Niveau | Ce qu'il peut faire | Qui le donne |
|---|---|---|
| **Membre** | Utiliser l'appli pour lui-même et sa famille | Un admin, en créant la fiche |
| **Admin** | Gérer l'organisation : personnes, réglages, modules | L'Administrateur principal |
| **Administrateur principal** | Un admin qui gère en plus la liste des admins | Un Administrateur principal ou le Super User |
| **Trésorier** | Un admin qui a en plus l'onglet **Financier** | Un Administrateur principal ou le Super User |
| **Super User** | Tout, dans toutes les organisations | Une commande sur le serveur, jamais l'appli |

Règles, imposées par le serveur et pas seulement cachées à l'écran :
- **Les niveaux se cumulent** et les droits s'additionnent.
- **Administrateur principal et Trésorier sont toujours des admins.** Retirer Admin retire les
  deux. Ce sont des droits en plus, pas des rangs au-dessus.
- **Un admin n'est pas forcément trésorier.** **Seuls le trésorier et le Super User voient
  l'onglet Financier** et peuvent lire le dossier **Financier** de l'onglet Docs ; même
  l'Administrateur principal ne les voit pas s'il n'est pas trésorier. Il peut y avoir
  plusieurs trésoriers.
- **Seuls un Administrateur principal et le Super User** cochent ou décochent « Administrateur
  principal » et « Trésorier » dans la liste des admins. Un admin ordinaire voit ces coches sans
  pouvoir les changer.
- Il reste **toujours au moins un Administrateur principal** par organisation, et personne
  n'agit sur sa propre ligne (ne se retire pas son niveau, ne se supprime pas), sauf
  un Administrateur principal qui peut cocher ou décocher Trésorier pour lui-même. Seul le Super
  User peut dépanner une organisation sans Administrateur principal.
- Le **Super User** n'appartient à aucune organisation et ne se cumule avec rien. Après
  connexion, il choisit l'organisation où il intervient et la voit comme un Administrateur
  principal. Il reste absent des listes de personnes, mais **on peut le trouver et l'ajouter
  dans les conversations de toute organisation** (décision de Seb du 18 octobre), comme une
  personne de l'organisation.

### 6.2 Les rôles métier, ajoutés par l'appli

Une appli peut ajouter ses propres rôles. Chacun déclare :
- son nom et son libellé à l'écran ;
- son **rang** par rapport aux niveaux du core (entre Membre et Admin, en général), qui sert à
  la montée en privilège (§5) et au libellé principal affiché ;
- avec quoi il se cumule ou non ;
- les onglets et droits qu'il ouvre.

Exemple, Contretemps : **Professeur**, rang entre Membre (« Élève ») et Admin, ne se cumule pas
avec Élève (un adulte à la fois élève et professeur a deux fiches dans la même famille), peut
être promu Admin. Ses droits sont dans `SPEC.md` §3.

### 6.3 Un seul endroit pour lire les droits

Aucune route, aucun écran ne teste un niveau lui-même : tout passe par les fonctions centrales
(`is_admin`, `is_tresorier`, `require_admin`… côté serveur ; `frontend/src/data/roles.js` côté
appli). Changer la façon de stocker les niveaux ne touche qu'un fichier.

---

## 7. Saisons

Détail : `SPEC.md` §2.6, §6.1bis. Code : `saisons/`.

La saison reste dans le core : une association vit par années, et la fiche d'une personne est
par saison. **Une organisation qui n'a pas de saisons (une pizzeria) en a une seule, sans date
de fin**, et ne voit jamais le mot « saison » à l'écran.

- Saison courante = la dernière créée ; elle seule est modifiable, les autres sont en lecture
  seule, imposé par le serveur.
- Seules les fiches de la saison courante peuvent se connecter. Le mot de passe, lui, appartient
  à l'adresse email et traverse les saisons.
- Créer une saison recopie toujours les admins (avec leurs niveaux, trésorier compris) ; chaque
  module dit ce qu'il propose de recopier (cases à cocher), et dans quel ordre.
- Seuls les admins consultent une ancienne saison.
- La portée par saison est fournie aux modules par le core (`saisons/portee.py`) : un module ne
  filtre jamais la saison à la main.

---

## 8. Installation sur le téléphone

Détail : `SPEC.md` §2.2 (« Suivi de l'invitation »), §2.7. Code : `personnalisation/`,
`frontend/src/api/installation.js`.

- L'appli est une appli web installable (PWA), avec une appli Android en plus (`ANDROID.md`).
- Chaque organisation a son adresse, donc **son nom et son icône** sur l'écran d'accueil, lus
  avant toute connexion (manifest et icônes servis par adresse).
- Après la création du mot de passe, l'appli propose de s'installer. L'installation est
  enregistrée sur l'adresse de connexion (« appli installée le … ») quand le téléphone le permet.
- Changer de logo demande de réinstaller sur iPhone ; un avertissement le dit avant
  d'enregistrer.

---

## 9. Services communs aux modules

Déjà codés dans Contretemps, à spécifier en détail plus tard dans ce document :
- **Email** : envoi par Brevo, au nom de l'organisation, réponse vers son email de contact ;
  suivi de remise (webhook). Code : `auth/mails.py`.
- **Notifications push** : Web Push, abonnement par appareil, réabonnement silencieux à chaque
  connexion. Code : `notifications/`.
- **Sauvegarde** : sauvegarde d'une organisation (Excel, Google Drive, périodicité réglable),
  sauvegarde technique complète avant toute suppression lourde. Code : `ecoles/`,
  `app/sauvegarde_worker.py`.
- **Temps réel** : flux par session, utilisé aujourd'hui par la messagerie.

---

## 10. Reste à décider

- **Groupes** : un groupe générique dans le core (un cours = un groupe + horaires), pour que
  messagerie, vidéos et présence ne dépendent plus du cours. Recommandé dans
  `01-architecture` §10, pas encore tranché.
- **Modules activés** (§3) : qui les choisit, et ce qui arrive aux données d'un module qu'on
  désactive.
- **Base de données** : Postgres dès l'extraction du core, ou plus tard.

## 11. Écarts entre ce document et le code (18 octobre 2026)

- **Corrigé dans la même PR** : le Super User entre maintenant dans le dossier Financier de
  Docs (il en était exclu), et « Qui a accès ? » d'un dossier réservé n'affiche plus
  « Admins, toujours ».
- **Mentions périmées dans `SPEC.md`** : §2.4 (Administrateur principal) et §2.6 (Saisons)
  disent « pas encore implémenté » alors que le code existe.
