# Sous-module `proces-verbal-ag` (module Documents)

Version 0.1 du 20 octobre 2026, proposition de Claude à partir de la demande de Seb du même jour :
« une nouvelle action, une action Informer : rédiger le PV d'AG ». Maquette cliquable :
https://claude.ai/artifact/JAaRZA9NXEaNP9hvXzsrAf

Sous-module du module Documents, à la suite des procurations (`procurations.md`) : la convocation
donne la date, le lieu, la sorte d'assemblée (AGO / AGE), l'ordre du jour et les procurations signées ;
le PV y ajoute **la liste des présents**, calcule le quorum et propose le texte. Rien de propre à la
danse : il part tel quel dans AppBase.

Le PV est un **fichier de base de nature Questionner** (`fichier-de-base.md`), caché derrière le
parcours comme la convocation (décision de Seb du 20 octobre pour les procurations, même essai ici) : à
l'écran, ni « nature » ni « Questionner ». Seb, 20 octobre : « philosophiquement un Informer, mais on
demande quand même quelque chose, des signatures, donc c'est aussi Questionner ». La seule question du
fichier est le **bloc Signature**, qui existe déjà ; les signataires sont les destinataires de
Diffuser.

---

## 1. Le parcours (Seb, 20 octobre)

> « La première chose qu'il doit demander, c'est prendre en photo la liste des présents. C'est
> important pour les votes. Et ensuite, en analysant les procurations et la liste des présents, il sait
> faire les quorums. […] Il propose, comme pour les procurations, sa proposition. […] Il propose en
> aperçu, le secrétaire peut mettre son texte et après valider, et on peut télécharger un PDF. »

**Où on le lance** : dans le dossier de l'AG (Docs › Privé › Saison › Réunions › « AGO du
21 novembre 2026 »), un bandeau « L'assemblée a eu lieu » avec le bouton **Produire le PV d'AG**
(même libellé que la tuile ; dès que la date de l'AG est passée et tant qu'il n'y a pas de PV). Aussi : Docs › + › tuile
**Produire le PV d'AG**, juste à côté de **Convoquer l'AG** (Seb, 20 octobre : « dans l'écran, il y a
Convoquer l'AG et il y a aussi Produire le PV d'AG »), et l'assistant (« produis le PV de l'AG », Seb 20 octobre).
**Quelle AG** : la convocation d'AG Officielle la plus récente dont la date est passée et qui n'a pas
de PV ; s'il y en a plusieurs, une question « Quelle assemblée ? » avec la liste.

Puis un écran par étape, un seul bouton principal chacun :

1. **Prenez en photo la liste des présents** (la feuille signée à l'entrée ; une photo par page,
   ou une image choisie). Bouton **Lire la liste**. Lien « Pas de liste papier : cocher les présents »
   (la liste des membres convoqués, une touche = présent : la feuille d'émargement de `procurations.md`
   §4).
2. **N présents reconnus** : les noms lus sur la photo, rapprochés des membres convoqués. Les noms
   sûrs ont ✓ ; les doutes sont en jaune avec la raison (« Deux membres « Leroy » : Annie ou
   Claire ? ») et un bouton **Choisir**. « + Ajouter une personne ». **Continuer** reste grisé tant
   qu'il reste un doute.
3. **Le quorum** : présents, représentés, voix sur N convoqués, seuil (réglage du bloc de la
   convocation) atteint ou non ; la liste des porteurs de pouvoirs avec leurs voix, les procurations
   annulées (le mandant est venu) et les **pouvoirs perdus** (mandataire absent). Règles de comptage :
   `procurations.md` §3.5. Quorum non atteint : écrit tel quel dans le PV (« le quorum n'étant pas
   atteint… »), pas de blocage. Bouton **Proposer le procès-verbal**.
4. **Le PV proposé** (Brouillon), en aperçu modifiable : le secrétaire touche un texte et écrit, comme
   dans Préparer. Les chiffres comptés par l'appli sont en bleu, ce qu'elle ne sait pas est surligné en
   jaune « À compléter : … ». Bouton **Valider**.
5. **Valider** fige le texte : le PV passe en **Validé**. Écran **Qui doit signer ?** (Seb,
   20 octobre) : les membres du bureau (colonne Bureau d'École › Administrateurs, §2 bis), présidence
   et secrétaire cochés d'avance, trésorerie et autres à cocher, « + Une autre personne ». Bouton
   principal **Envoyer pour signature** ; dessous, **Télécharger le PDF (sans signatures)**.
6. **Chaque signataire reçoit un email** « À signer : procès-verbal de l'AGO du 21 novembre 2026 »
   avec son lien personnel (pas de compte) : le PV en entier, la phrase « Je soussigné(e) Martine
   Colin, présidente, certifie ce procès-verbal exact », la signature au doigt, **Signer**. Lien
   « Je ne suis pas d'accord : écrire à <celui qui a envoyé> » (Messagerie instantanée). Celui qui
   envoie et qui doit aussi signer signe directement depuis l'écran de suivi (**Signer moi-même**).
7. **À chaque signature** (Seb, 20 octobre) : un email part à l'**adresse de contact de l'école**
   (`email_contact`, École › Personnalisation) : « Martine Colin (présidente) a signé le procès-verbal
   de l'AGO du 21 novembre 2026 (2 signatures sur 3) », avec le PDF à jour en pièce jointe. Et le
   **PDF est refait** avec les signatures déjà reçues (les zones des autres restent vides, mention
   « en attente de signature ») : on télécharge toujours la dernière version, rangée dans le dossier de
   l'AG à la place de la précédente.
8. **Suivi des signatures** : une ligne par signataire (« a signé le 23/11 ✓ » ou « pas encore
   signé », **Relancer**). Quand tous ont signé, le PV passe **tout seul en Officiel**, PDF A4 par
   Chromium avec les signatures (image, nom, fonction, date). Bouton principal **Télécharger le PDF** ;
   dessous, **Envoyer aux N membres…** (même envoi que Diffuser, confirmation puis Annuler 10 s).
   Pour corriger le texte après Valider : ⋯ › Modifier, qui repasse en Brouillon et efface les
   signatures déjà faites (avec un avertissement).

## 2. Le texte proposé

**Ce que l'appli écrit elle-même** (gabarit fixe, jamais le modèle de langage) : le titre
(« Procès-verbal de l'assemblée générale ordinaire / extraordinaire »), le nom de l'association, date,
heure, lieu, la date d'envoi et le nombre de convoqués, les présents, représentés, voix, le seuil du
quorum et s'il est atteint, l'ordre du jour (celui de la convocation), les noms sous les signatures, et,
pour le point « rapport financier », recettes, dépenses et résultat du **bilan Officiel** de la saison
(Financier › Bilan, `financier.md` §4 ; sans bilan Officiel, « À compléter »).

**Le reste du texte** (codé le 21 octobre, comme la convocation : **sans modèle de langage**, gratuit et
toujours le même) : sous chaque point de l'ordre du jour, les paragraphes du **PV de l'année
précédente** rangés sous le même titre (même sorte d'assemblée), précédés de « À compléter : texte repris
du procès-verbal de l'an dernier, à adapter », **chaque nombre repris surligné en jaune** (à vérifier) ;
sans PV de l'an dernier, « À compléter : ce qui a été dit et le résultat du vote ». Clôture : « la séance
est levée à À compléter : l'heure ». Pas d'écran des votes ni des résolutions : **le secrétaire écrit les
résultats des votes dans le texte** (Seb, 20 octobre). Pour reformuler, l'assistant du fichier
(`modifier_fichier_appli`) ; il n'écrit que ce que la personne lui dit, jamais un chiffre ni un vote.

**Présidence et secrétariat** : les membres qui ont la fonction Président·e et Secrétaire dans la
colonne Bureau (§2 bis), sinon « À compléter » ; corrigés dans le texte.

**À l'écran** : les chiffres de l'appli en bleu (`textColor: blue`), les « À compléter » et les nombres
repris en jaune (`backgroundColor: yellow`), styles ordinaires de l'éditeur.

**Mentions d'un PV d'AG loi 1901** (aucune n'est imposée par la loi, les statuts décident ; ce sont
celles de l'usage, toutes dans le gabarit) : association, nature AGO / AGE, date, heure et lieu, mode
et date de convocation, présidence et secrétaire de séance, présents, représentés, quorum, ordre du
jour, délibérations et résultat des votes point par point, heure de clôture, signatures du président et
du secrétaire. La liste des présents (photo et liste reconnue) et les pouvoirs sont joints en annexe du
PDF.

**Signatures** : dans l'appli, au doigt, par les membres du bureau choisis (étapes 5 à 7 du §1). Le
PDF montre une zone de signature par signataire choisi, remplie à mesure.

## 2 bis. Le bureau (core, École › Administrateurs)

Seb, 20 octobre : « dans École › Administrateurs, on rajoute une colonne Bureau où, pour chaque
admin, on peut mettre une ou plusieurs fonctions : président, trésorier, secrétaire ». Fonctions
proposées : **Président·e, Vice-président·e, Secrétaire, Trésorier·e** (accord selon le genre de la
fiche ou forme neutre). Elles servent à proposer les signataires, à écrire « Martine Colin,
présidente » dans le PV et le pouvoir en blanc des procurations (« donné à la présidence »). Elles ne
donnent **aucun droit** : les droits restent les niveaux du core (`core.md` §6.1). Décrit dans
`core.md` §6.4.

## 3. Rangement

Dans le même dossier que la convocation : « PV de l'AGO du 21 novembre 2026 » (fichier) et, au
passage en Officiel, son PDF. La photo de la liste des présents est rangée à côté (« Liste des
présents.jpg »). Mêmes droits que le dossier (bureau, profs).

## 4. L'assistant fait la même chose (un bouton = un outil)

Déclarés dans `documents_contretemps/actions.py` (comme ceux des procurations), mêmes droits que l'écran (niveau `manage` sur le dossier de l'AG).

| Étape à l'écran | Outil | Carte |
|---|---|---|
| Produire le PV d'AG (trouver l'AG) | dans `draft_minutes` : sans AG passée sans PV, ou si plusieurs, refus avec la liste (l'assistant demande laquelle) | aucune |
| Lire la liste, Choisir, Pointer les N présents | `mark_attendance(file, names)` : l'assistant lit lui-même la photo envoyée dans la discussion, vérifie les doutes avec la personne, puis donne les noms ; l'appli les rapproche des convoqués (un seul membre par nom, sinon refus avec les noms à préciser) et pointe ; le quorum est recalculé par l'appli | Faire / Annuler (noms et nombre écrits par le code) |
| Proposer le procès-verbal | `draft_minutes(assembly?)` : crée le PV en Brouillon ; refusé tant que personne n'est pointé présent (la photo d'abord) | Faire / Annuler (toute action de l'assistant a sa carte) |
| Écrire dans le texte | `modifier_fichier_appli` (existe déjà) | Annuler sous la modification |
| Valider | `validate_app_file(file)` : un PV passe en **Validé** (une convocation, en Officiel) | Faire / Annuler |
| Envoyer pour signature | `send_app_file(file, signers?)` : PV Validé, aux noms donnés, sinon présidence et secrétariat du bureau (refus si personne n'a ces fonctions) | Faire / Annuler (noms et fonctions écrits par le code) |
| Suivi, Relancer | où en sont les signatures : lu avec le fichier (`lire_fichier`) ; relancer : `send_app_file(file)` quand l'envoi est déjà parti (ceux qui n'ont pas signé) | aucune ; Faire / Annuler pour relancer |
| Télécharger le PDF | pas d'outil : le PDF à jour est rangé dans le dossier de l'AG à chaque signature | — |
| Envoyer aux N membres | `send_app_file(file)` sur le PV Officiel : aux membres convoqués à l'assemblée, à lire | Faire / Annuler |

L'assistant ne signe jamais à la place de quelqu'un. Il ne fait que transcrire dans le texte ce que la personne lui dit (« rapport moral adopté à
l'unanimité ») ; il n'invente jamais un résultat de vote.

## 5. Données

- **Présents** : la table `doc_attendance` de la feuille d'émargement (procurations, PR #38 :
  `id`, `org_id`, `node_id` de la convocation, `person_id` unique par convocation, `present_at`,
  `marked_by`, `source` `hand` ou `photo`). La photo pointe par `assembly.mark(..., source="photo")`
  et le décompte du jour (présents, représentés, pouvoirs perdus, quorum) vient de
  `assembly.sheet(...)` : une seule liste des présents par AG, **pas de nouvelle table** pour le PV.
  Un nom lu sur la photo et rapproché de personne n'est pas pointé : il est montré dans les doutes
  (« Ajouter une personne » ou « Ignorer »).
- **Lien PV → convocation** : le bloc Signature du PV porte l'id de la convocation dans un réglage
  `minutesOf` (le contenu enregistré ne garde que `schema`, `entry` et `result` : pas de
  `content_json.source`). C'est aussi ce qui fait d'un fichier un PV (`documents/minutes.py`,
  `block_of`). Sans nouvelle colonne.
- **Ce que Documents lit de Contretemps** : un port `Association` (`documents/ports.py`) : `board`
  (fonctions du bureau), `contact_email` (`ecoles.email_contact`, sinon l'Administrateur principal),
  `approved_report` (le dernier bilan Officiel de `fin_reports` : recettes, dépenses, résultat),
  branché par `AssociationContretemps` dans `documents_contretemps/adapter.py` : Documents ne dépend ni
  des comptes, ni des écoles, ni de Finances.
- **PDF à chaque signature** : refait (pymupdf, comme le pouvoir signé, sans Chromium) au moment où la
  signature est enregistrée, rangé à côté de la convocation sous « PV de l'AGO du … .pdf » (une
  version de plus, l'ancienne reste dans l'historique) ; le texte, une case par signataire (image,
  nom, fonction, date, ou « En attente de signature »), puis en annexe la feuille d'émargement.
  Email à l'adresse de contact par le port `Mailer`, PDF joint.
- **Signatures** : réponses du bloc Signature dans `doc_responses` (existant), une par signataire. Les
  signataires sont des envois `doc_sends` de canal `sign` (même lien personnel `/r/<jeton>`, ouvert
  tant que le PV est Validé ; l'envoi aux membres reste le canal `email`, à lire, sans signature).
  « Tous ont signé » = tous les envois `sign` ont une réponse → passage en Officiel par le code.
  Repasser le PV en Brouillon efface les signatures (les liens restent). **Pas de nouvelle table.**
- **Fonctions du bureau** (core) : une colonne `bureau_functions` (liste JSON) sur la fiche
  (`comptes`), recopiée avec elle à la création d'une saison. Ce ne sont pas des rôles (`roles`) :
  elles ne donnent aucun droit. Migration qui ajoute une colonne, sans `has_table`.
- Lecture de la photo : modèle avec vision, coût noté dans Ressources (« Procès-verbal d'AG »).
- Toutes les requêtes filtrent par `org_id`, test d'étanchéité entre écoles.

## 6. À trancher par Seb

1. ~~La fonction Trésorier·e du bureau donne-t-elle aussi l'onglet Financier ?~~ **Décidé par Seb
   le 20 octobre : non**, deux choses séparées : la fonction est un titre (qui signe, ce qu'on écrit dans le PV), la
   coche Trésorier est un droit (un trésorier adjoint peut avoir le Financier sans être au bureau).
   L'écran propose de cocher Trésorier quand on donne la fonction, sans le faire tout seul.
2. **Envoi aux membres** : en lien secondaire sous « Télécharger le PDF » une fois signé.
   Recommandation : **oui**, rien ne part sans le toucher.

## 7. Étapes (une PR chacune, sur « vas-y »)

Prérequis : l'étape 1 des procurations (PR #34, en ligne le 21 octobre) et la feuille d'émargement
(PR #38) dans `main`.

0. **Le bureau** (core, codé le 21 octobre : colonne `comptes.bureau_functions`, migration
   `a4c6e8f0b2d5`, `PUT /administrateurs/{id}` avec `bureau_functions`, action `change_roles`) : la coche Trésorier renommée « Accès au Financier » à l'écran, colonne
   Bureau dans École › Administrateurs, `bureau_functions`, recopie
   à la création de saison, outil de l'assistant pour la changer (mêmes droits que les coches).
1. **La liste des présents** (codée le 21 octobre). Dans la feuille d'émargement de la convocation,
   en tête : **Prendre en photo la liste des présents** (une ou plusieurs pages, réduites dans le
   téléphone avant l'envoi). Le serveur range les photos dans le dossier de l'AG (« Liste des
   présents.jpg », « Liste des présents (page 2).jpg », nouvelle version si elles y sont déjà) et
   les fait lire (`documents/attendance_photo.py`, Opus, coût noté dans Ressources « Assemblée
   générale : lecture de la liste des présents ») avec la liste des convoqués ; les numéros rendus
   sont recontrôlés (seulement des convoqués, sans doublon). Écran **N présents reconnus** : les
   doutes en jaune avec un bouton par membre possible et « Personne », les noms sûrs cochés, les
   noms qui ne sont pas des convoqués listés (à ajouter ensuite par « + Ajouter une personne »).
   **Pointer les N présents** reste grisé tant qu'un doute n'est pas tranché ; il pointe tout le
   monde d'un coup (`source = photo`), sans dépointer ceux déjà pointés, et l'on revient à la
   feuille avec le quorum recalculé. Routes `POST …/nodes/{id}/app/attendance/photo` (fichiers
   `files`, rien n'est pointé) et `POST …/app/attendance/batch` (`person_ids`). Sans clé d'API : 503
   « cochez les présents sur la feuille d'émargement ». Outil `mark_attendance` (§4).
   *Vérification* : tests de la lecture (sûrs, doutes, inconnus, doublon, numéro hors liste,
   photos rangées), du pointage groupé et du quorum, de l'étanchéité, de l'outil de l'assistant.
2. **Le PV** (codé le 21 octobre, `documents/minutes.py`). Tuile **Produire le PV d'AG** dans Docs › +
   (Questionner, après Convoquer l'AG) et bandeau « L'assemblée a eu lieu » dans le dossier de l'AG
   (`GET …/minutes/pending?folder_id=`) ; écran `ProduirePV.jsx` : quelle assemblée (si plusieurs),
   présents, représentés, voix et quorum, **La liste des présents** (feuille d'émargement, avec la photo)
   tant que personne n'est pointé, puis **Proposer le procès-verbal** (`POST …/minutes`) : le PV
   s'ouvre en Brouillon dans l'éditeur habituel. Valider → Validé ; onglet Diffuser du PV
   (`MinutesSign.jsx`) : **Qui doit signer ?** (bureau, présidence et secrétariat cochés, « + Une
   autre personne »), **Envoyer pour signature** (`POST …/app/minutes/sign`), suivi avec **Relancer**
   et **Signer moi-même** ; Officiel : **Télécharger le PDF**, **Envoyer aux N membres…** (Diffuser
   habituel). Le lien du signataire montre « Je soussigné(e) …, certifie ce procès-verbal exact » et le
   bouton **Signer**. Outils `draft_minutes`, `validate_app_file` et `send_app_file` élargis (§4).
   *Vérification* : tests (`tests/test_documents_minutes.py`) du texte proposé (chiffres, présidence,
   quorum atteint ou non, bilan officiel, texte de l'an dernier avec nombres surlignés), des AG en
   attente et de l'étanchéité entre écoles, des signatures (lien, mail au contact avec PDF, PDF rangé,
   Officiel quand tous ont signé, liens fermés, envoi aux membres sans signature, retour en Brouillon),
   de l'assistant ; parcours essayé à l'écran sur l'école de démo (bandeau, proposition, Valider, Qui doit
   signer, Signer moi-même, PDF signé).
