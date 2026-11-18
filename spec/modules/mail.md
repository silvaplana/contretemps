# AppBase — Sous-module `mail` (Messagerie)

Version 0.1 du 18 novembre 2026. Repris du client mail de Sambo Admin (`silvaplana/test-python`,
`backend/src/webmail/`, `frontend/src/Webmail.jsx`, onglet Messagerie > Mail), à fonctions
identiques. Étude : https://claude.ai/artifact/7HPSBAeGZ5YrE4jahT213a (partie 7 ter). Méthode de
connexion : étude Gmail du 22 octobre 2026. Maquette validée par Seb le 18 novembre :
https://claude.ai/artifact/5wX9catY3i76qBEPo3fM4S. Étapes 1 à 3 codées (§12).

## 1. Ce que fait le sous-module

Les personnes choisies lisent et envoient les mails de **la boîte mail de l'école** (Gmail ou
Infomaniak) depuis
l'appli, sans ouvrir Gmail. Sous-module optionnel de la Messagerie instantanée, **éteint par
défaut** : rien ne change pour les écoles qui ne l'allument pas (Contretemps, Le Beausset).

Les mails restent chez Google : l'appli les relit à chaque ouverture (IMAP) et envoie par SMTP.
Aucun mail n'est copié en base.

## 2. Où il se trouve

- **Admin › École › Personnalisation › Fonctionnalités** : ligne **Mail**, en retrait sous
  Messagerie, « La boîte mail du club (Gmail ou Infomaniak), lue et envoyée depuis Messages ».
  Allumer Mail allume la Messagerie (`requires`). Une fois allumée, la ligne montre la boîte
  connectée et sert à la connecter (§4 ; Seb, 18 novembre).
- **Admin › École › Administrateurs** : groupe **🔒 Boîte mail du club**, coché dans la colonne
  Groupes comme « Accès au Financier » (le mécanisme existant des droits, à la place de la colonne
  à part de la maquette), visible seulement si Mail est allumé (§3).
- **Messages** : en haut, deux puces **Chat | Mail**, seulement pour qui a le droit. Les autres
  voient la Messagerie comme aujourd'hui, sans puce. Le mot reste « Chat » pour la messagerie
  instantanée, jamais « Discussions » (Seb, 18 novembre).
- Pastille des non lus (boîte de réception) sur la puce Mail et sur l'onglet Messages, pour qui a
  le droit.

## 3. Le droit « Boîte mail du club »

Un droit déclaré par le module, donc un groupe 🔒 (`core.md` §5.3) :
`Right("mail.read", "Boîte mail du club")`. Le courrier du club contient des certificats
médicaux, des RIB, des litiges : seules les personnes cochées le voient, et l'Administrateur
principal ne passe pas sans être coché. Phrase sous le titre de l'écran Administrateurs : « Les
mails du club peuvent contenir des certificats médicaux, des RIB ou des litiges : seules les
personnes cochées les voient. »

Le droit donne tout : lire, envoyer au nom du club, ranger, supprimer. L'Assistant n'a **aucun
outil** sur les mails (il ne les lit pas) ; il sait seulement guider vers l'écran.

## 4. Connecter la boîte (Admin › École › Connexions depuis le 18 novembre ; avant, Fonctionnalités, ligne Mail)

Seb, 18 novembre : la connexion se fait dans **Admin › École › Personnalisation ›
Fonctionnalités**, sur la ligne Mail (comme HelloAsso et FFST), et non plus dans Messages. Réservé
à l'**Administrateur principal** et au Super User, **sans avoir besoin du droit** « Boîte mail du
club » (connecter ne montre aucun mail ; lire en demande toujours le droit). La ligne dit
« Connectée : adresse », « adresse : à reconnecter » ou « Pas encore connectée. Seules les boîtes
Gmail et Infomaniak peuvent être connectées pour l'instant. », avec **Connecter** ou **Voir**.
Cocher Mail sans boîte ouvre directement le choix du fournisseur. Dans Messages › Mail, une boîte
pas connectée affiche : « La boîte mail du club n'est pas encore connectée. » et, pour
l'Administrateur principal, où la connecter.

**Fournisseurs** (Seb, 18 novembre) : **Gmail** et **Infomaniak** (adresses @ik.me de my kSuite et
adresses d'un nom de domaine chez Infomaniak, serveur `mail.infomaniak.com`, IMAP 993 et SMTP 587).
Premier écran : « Quelle boîte connecter ? », deux boutons Gmail / Infomaniak et la phrase « Seules
les boîtes Gmail et Infomaniak peuvent être connectées pour l'instant. »

Écran guidé, celui de la maquette du 22 octobre, selon le fournisseur :
1. **Adresse Gmail (ou Infomaniak) du club** ; encadré « **Toute la boîte sera visible** : les
   personnes qui ont le droit « Boîte mail du club » verront tous les mails de cette adresse et
   pourront écrire en son nom. Utilisez la boîte du club, jamais une boîte personnelle. » ; trois
   étapes numérotées. Bouton principal **Ouvrir Google** / **Ouvrir Infomaniak** (nouvel onglet) :
   - Gmail : page des mots de passe d'application ; phrase sur la validation en deux étapes.
   - Infomaniak @ik.me (aussi etik.com, ikmail.com) : appli Mail de kSuite, ⋮ à côté de
     l'adresse › Paramètres › Gérer le mot de passe › Ajouter un appareil, IMAP / SMTP. Autre
     adresse : Manager › Service Mail › domaine › adresse › Appareils › Ajouter un appareil.
     Phrase : Infomaniak ne montre ce mot de passe qu'une fois.
2. **Code Google** / **Mot de passe Infomaniak**, bouton **Coller**, lien **Rouvrir…**, bouton
   principal **Connecter**. Les espaces sont retirés (le code Google s'affiche en quatre groupes).
3. « Connexion à Gmail… » / « Connexion à Infomaniak… » : l'appli essaie IMAP et SMTP.
4. **Boîte connectée** (toast) ou **Code refusé** (lien « Recoller le code », bouton **Rouvrir…**).

Le code est chiffré en base (`securite/chiffrement.py`), jamais réaffiché. **Voir** : adresse,
fournisseur, date de connexion, lien **Connecter une autre boîte**, bouton **Déconnecter la
boîte** (efface le code ; Annuler 10 s). Menu ⋮ de la boîte dans Messages : l'adresse connectée.

**Le fournisseur coupe l'accès** (changement du mot de passe du compte, code révoqué) : bandeau en
haut de la boîte « La boîte mail n'est plus connectée. Google (ou Infomaniak) a coupé l'accès,
souvent après un changement du mot de passe du compte. », avec pour l'Administrateur principal
« Reconnectez-la dans Admin › École › Personnalisation › Fonctionnalités, ligne Mail. » (bouton
**Reconnecter** dans « Voir »), sinon « L'Administrateur principal doit la reconnecter. »

## 5. La boîte (Messages › Mail)

- En haut : liste des **dossiers** (Boîte de réception, Suivis, Envoyés, Brouillons, Spam,
  Corbeille, Tous les messages) et champ **Rechercher**.
- Une ligne par mail, 40 par page, le plus récent en haut : rond aux initiales, expéditeur (« À :
  destinataire » dans Envoyés), date (heure aujourd'hui, « 16 nov. », date complète les autres
  années), objet avec trombone s'il y a une pièce jointe, début du texte. Non lu en gras.
  Étoile **Suivre / Ne plus suivre** à droite. En bas, **Mails plus anciens**.
- Toucher le rond **coche** le mail ; la barre du haut devient : croix (tout décocher), nombre,
  **Archiver**, **Corbeille**, **Marquer comme non lu**, ⋮ (Marquer comme lu, Spam). Dans la
  Corbeille : **Supprimer définitivement**.
- Bouton principal **Nouveau message**, rond allongé en bas à droite.
- Liste relue chaque minute tant que l'écran est ouvert ; pastille relue toutes les 2 minutes.
- Sur ordinateur, la liste reste à gauche et le mail s'ouvre à droite.

## 6. Un mail

← retour à la liste, **Archiver** et **Corbeille** en haut, ⋮ (Répondre à tous, Marquer comme non
lu, Spam ou « Ce n'est pas du spam »). Objet, expéditeur et adresse, « À : », date, étoile, texte
(HTML nettoyé, images intégrées affichées), pièces jointes (PDF dans la visionneuse, Word et Excel
dans OnlyOffice, le reste téléchargé). Ouvrir un mail le marque lu. En bas : **Répondre** (bouton
principal) et **Transférer**.

## 7. Écrire

Écran plein : « De : adresse du club », **À**, lien **Cc / Cci** qui ouvre les deux lignes,
**Objet**, message, pièces jointes (**Joindre un fichier**, croix pour retirer ; 18 Mo au plus),
bouton principal **Envoyer**. Répondre met « Re: » et le texte cité ; Transférer met « Fwd: » et
garde les pièces jointes. Sans destinataire : « Indiquez à qui envoyer le mail ».

## 8. Annuler plutôt que confirmer

Les confirmations de Sambo Admin deviennent un toast **Annuler** de 10 s (`core` : « Annuler
10 s ») : Archivé, Mis à la corbeille, Mis dans le spam, Supprimé définitivement, Boîte
déconnectée, et **Mail envoyé** (l'envoi part au bout des 10 s : on ne rattrape pas un mail
parti). Seul écart de comportement avec Sambo Admin.

## 9. Données

Une table `mail_accounts` : `organization_id` (unique), `address`, `provider` (`gmail` ou
`infomaniak`, défaut `gmail`), `app_password` chiffré,
`connected_at`, `cut_at` (rempli quand Google refuse, vidé à la reconnexion). Une ligne par école :
la boîte appartient à l'école, pas à une personne. Rien d'autre en base : ni mails, ni pièces
jointes, ni cache.

## 10. Risques

- **Toute la boîte est ouverte** : le mot de passe d'application donne tout le compte Gmail. D'où
  le droit à part (§3), l'avertissement (§4) et la règle « boîte du club, jamais personnelle ».
- **Google peut couper** les mots de passe d'application (changement de mot de passe, Protection
  avancée, compte pro bloqué par son admin) : bandeau §4, on reconnecte.
- **Google interdit d'automatiser** la création du code : l'écran guide, la personne le crée.
- **Une seule boîte par école** ; pas d'autre fournisseur que Gmail et Infomaniak pour l'instant.

## 11. Technique

Code de Sambo Admin repris : `backend/src/mail/` (lecture IMAP, envoi SMTP, une connexion par
requête, cache des dossiers 10 min, routes protégées par le droit `mail.read`) et
`frontend/src/modules/mail/`. Module déclaré dans `module.py` : `key="mail"`,
`requires=("messaging",)`, défaut éteint. Les puces Chat | Mail sont le seul ajout à l'écran de la
Messagerie. `guide.md` du module mis à jour dans la même PR que les écrans.

## 12. Étapes (chacune une PR, sur le « vas-y » de Seb)

1. Module, case Fonctionnalités, droit, table `mail_accounts` et écran de connexion (§2 à §4, §9).
   **Fait (18 novembre 2026)** : `Module(enabled_by_default=False)`, comme HelloAsso et FFST (pas de ligne `org_modules` =
   éteint, aussi pour les écoles créées ensuite) ; la migration l'allume dans les écoles de nature
   « combat » (ASC, Seb 18 novembre). Écran : la boîte connectée affiche son adresse, la liste vient
   à l'étape 2.
2. La boîte et un mail (§5, §6).
   **Fait (18 novembre 2026)** : lecture IMAP reprise telle quelle de Sambo Admin
   (`backend/src/mail/imap.py`), boîte coupée marquée au premier refus de Google. Ranger et
   supprimer partent au bout des 10 s d'Annuler (Gmail change le numéro d'un mail déplacé : on
   ne peut pas le remettre après coup). Pièces jointes : téléchargées, comme dans Sambo Admin ;
   l'ouverture dans la visionneuse ou OnlyOffice (§6) reste à faire.
2 bis. Connexion dans Fonctionnalités, Gmail ou Infomaniak (§2, §4, §9 ; Seb, 18 novembre).
   **Fait (18 novembre 2026)** : colonne `provider` (migration), l'Administrateur principal
   connecte sans le droit de lecture. Infomaniak à essayer avec la boîte du club
   (alliancesambocombatprovence@ik.me) : dossiers et Archiver non vérifiés sur un vrai compte.
3. Écrire, répondre, transférer, pièces jointes, Annuler 10 s (§7, §8).
   **Fait (18 novembre 2026)** : envoi SMTP repris de Sambo Admin, route `POST …/mail/send`
   (multipart, droit `mail.read`) ; « De : » nom de l'école et adresse de la boîte. « Envoyer »
   ferme l'écran ; le mail part au bout des 10 s d'Annuler, Annuler rouvre l'écran avec le mail
   (et ses pièces jointes) ; un envoi refusé rouvre aussi l'écran avec l'erreur. Pas de question
   « Envoyer sans objet ? » de Sambo Admin (l'Annuler la remplace).
