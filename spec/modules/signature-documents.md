# Sous-module `signature-documents` (module Documents)

Version 0.1 du 22 octobre 2026, écrite par Claude à partir de la maquette validée par Seb le même
jour : https://claude.ai/artifact/LMoq8PhsTGNuQV439e89k5

Seb, 22 octobre : « la signature électronique de documents comme un PV d'AG : moi, le président,
j'envoie un PDF au trésorier et au secrétaire pour qu'ils le signent ». Seb a choisi de le **coder
dans l'appli** plutôt que d'utiliser Yousign, DocuSign ou DocuSeal (`documents.md` §12, décision 13).

Sous-module de Documents. Il ne dépend pas de Contretemps et part tel quel dans AppBase. Il
**généralise** ce qui existe déjà pour le PV d'AG (`proces-verbal-ag.md`, `MinutesSign.jsx`,
`documents/minutes.py`) : n'importe quel PDF ou Word de Docs, signé par n'importe qui.

---

## 1. Ce que la loi exige (non négociable)

Une **signature électronique simple** vaut une signature papier (Code civil, art. 1366 et 1367 ;
règlement européen eIDAS, art. 25) si on peut prouver **trois choses** : **qui** a signé, qu'il a
**voulu** signer, et que le document **n'a pas changé** depuis. Le tracé au doigt ne prouve presque
rien à lui seul ; la preuve vient des six points suivants. Aucun ne peut être retiré ni rendu
facultatif.

| # | Obligation | Comment l'appli la remplit |
|---|---|---|
| 1 | **Figer le document** | **Valider** produit le PDF à signer et enregistre son empreinte SHA-256. Ensuite, plus rien ne change : seules les signatures s'ajoutent. Pour changer le texte, retour en Brouillon, qui annule les signatures. |
| 2 | **Savoir qui signe** | Chaque signataire reçoit par email un **lien personnel** (jeton aléatoire) qui expire au bout de **14 jours** et se ferme une fois signé. L'ouvrir prouve l'accès à la boîte mail. |
| 3 | **Faire lire avant de signer** | Le document entier s'affiche ; **Signer** reste grisé tant que la personne n'a pas fait défiler jusqu'en bas. Le serveur refuse une signature sans lecture enregistrée. |
| 4 | **Recueillir le consentement** | Une case à cocher : « Je soussigné(e) Karim Benali, trésorier, ai lu le document « … » et je le signe », puis la signature au doigt. Le serveur refuse une signature sans la case. |
| 5 | **Tout noter dans un journal** | Chaque événement (validé, envoyé, ouvert, lu, consenti, signé, refusé, relancé, produit) avec la date et l'heure **du serveur**, l'adresse IP et l'appareil. Le journal ne se modifie jamais : on y ajoute seulement. |
| 6 | **Remettre le document signé** | « Produire le document signé » fait le PDF avec les signatures visibles et une dernière page **Certificat de preuves**, le range à côté de l'original et l'envoie à chaque signataire. |

**Code à 6 chiffres par email avant de signer** : non (décision de Seb, 22 octobre). Le lien
personnel suffit pour une signature simple ; le code ne protège que du mail transféré à quelqu'un
d'autre.

**Ce qu'on ne promet pas** : ce n'est pas une signature « avancée » ou « qualifiée » (identité
vérifiée, certificat d'une autorité). Pour un contrat à fort enjeu, un prestataire reste possible
plus tard (`documents.md` §12, décision 13).

## 2. Le parcours

Comme la convocation d'AG (`AppFile.jsx`) : un **fichier de l'appli de nature Questionner** à
**trois onglets**, **1. Préparer**, **2. Diffuser**, **3. Voir les résultats**. Dans Préparer, le
menu **Mode** de l'en-tête choisit Édition, Aperçu smartphone ou Aperçu ordinateur. La nature ne
s'affiche pas (même choix que la convocation et le PV).

**Où on le lance** :

- Docs › **+** › tuile **Faire signer un document** (Questionner) : le fichier s'ouvre en Édition,
  sans document ;
- menu **⋯** d'un PDF ou d'un Word dans l'explorateur › **Faire signer…** : le fichier est créé à
  côté, avec ce document déjà choisi ;
- l'assistant (« fais signer le PV au trésorier et à la secrétaire »), §5.

Le fichier se nomme « Signature : <nom du document> » et se range dans le même dossier que le
document.

### 2.1 Préparer (Édition)

Trois questions, avec des valeurs par défaut :

1. **Le document** : une zone pour déposer un PDF ou un Word (`.docx`, `.doc`, `.odt`), ou le
   choisir dans Docs. Un seul document.
2. **Où signer ?** « Une signature à la fin » (par défaut) ou « Signature à la fin et paraphe en bas
   de chaque page ».
3. **Ce que chacun doit savoir** : la **mention** écrite au-dessus de chaque signature (« Lu et
   approuvé » par défaut, peut être vide) et le **message aux signataires** (repris dans le mail).

Ni le paraphe ni la mention ne sont exigés par la loi (l'empreinte protège déjà chaque page) ; ils
sont proposés parce que les gens y sont habitués.

### 2.2 Préparer (Aperçu)

Le document tel qu'il sera signé, avec les zones de signature (et de paraphe) en bleu, placées
toutes seules (§3).

- **Word** : en Brouillon, **le texte se corrige directement dans l'Aperçu**, comme celui de la
  convocation (Seb, 22 octobre). Pour cela, le Word est transformé en document de l'appli (même
  éditeur que le fichier de base) au moment où on le dépose : titres, paragraphes, listes, gras,
  italique et souligné sont gardés ; chaque ligne d'un tableau devient une ligne de texte (cases
  séparées par « · ») ; une mise en page compliquée (en-tête avec logo, colonnes, zones de texte)
  est simplifiée. Le Word d'origine ne change pas.
- **PDF** : il ne se modifie pas. Pour corriger, on dépose une nouvelle version dans Préparer.

Le Diffuser habituel (mail, essai) est refusé pour ce fichier : il s'envoie par « Faire signer à
qui ? » (§2.3).

Bouton principal **Valider** : le document est figé (obligation 1), le fichier passe en **Validé**
et l'on va à Diffuser.

### 2.3 Diffuser : « Faire signer à qui ? »

- **Bureau** (fonctions de la colonne Bureau, `core.md` §6.4) : Président·e, Vice-président·e,
  Secrétaire, Trésorier·e, une puce chacune (comme la maquette, sans le nom : les noms se lisent
  dans le récapitulatif « N signataires : … ») ;
- **Membres** : une puce Professeurs et une puce Élèves, avec le nombre de personnes (comme la
  maquette) ;
- **Quelqu'un d'autre** : un champ de recherche dans les membres et les cours de l'école ; sous
  les résultats, « Ajouter « <nom> » » demande son adresse email (un commissaire aux comptes, un
  intervenant, décision de Seb du 22 octobre).

Une fois envoyé, Diffuser reste ouvert pour ajouter des signataires ; renvoyer à quelqu'un qui a
déjà le lien le relance (même lien). Quelqu'un qui a déjà signé est laissé de côté.

Tout le monde signe **en même temps**, sans ordre (décision de Seb, 22 octobre). Celui qui envoie
peut se cocher : il signe depuis Voir les résultats (**Signer moi-même**), avec les mêmes étapes de
lecture et de consentement.

Récapitulatif nominatif, bouton principal **Envoyer aux N**, puis **Annuler** pendant 10 s. Une
personne sans adresse email est signalée avant l'envoi et ne bloque pas les autres.

Le mail : « À signer : <nom du document> », « <Nom>, <fonction>, vous demande de signer ce
document », le message aux signataires, le bouton **Lire et signer** (lien personnel),
« Ce lien vous est personnel, ne le transférez pas. Il expire le <date>. » Réponse au mail = à
l'expéditeur.

### 2.4 Côté signataire (lien personnel, sans compte)

Un écran par étape, un seul bouton principal chacun :

1. **Bonjour <prénom>** : qui demande, le nom du document, le nombre de pages. Bouton **Lire le
   document**.
2. **Lire le document** : le PDF figé en entier, page par page. Le bouton du bas dit « Faites
   défiler jusqu'en bas », puis **J'ai lu, je signe**.
3. **Signer** : la case de consentement (§1, obligation 4), la mention qui sera écrite, la zone de
   signature au doigt, et, si le paraphe est demandé, une petite zone **Vos initiales** (dessinées
   une fois, reprises en bas de chaque page). **Effacer**, puis **Signer** (grisé tant que la case
   n'est pas cochée et que les tracés manquent).
4. **C'est signé** : date et heure, « Vous recevrez le document signé par mail ». Le lien est fermé.

Sous l'étape 2, un lien discret **Je ne signe pas** (décision de Seb, 22 octobre) : un motif à
écrire (obligatoire), **Envoyer**. Le refus est noté au journal, l'expéditeur reçoit un mail avec
le motif, le lien reste ouvert (la personne peut changer d'avis après une correction ou une
explication).

Lien expiré : « Ce lien a expiré. Demandez à <expéditeur> de vous le renvoyer. » Lien d'un document
repassé en Brouillon : « Le document est en cours de correction. Vous recevrez un nouveau mail. »

### 2.5 Voir les résultats

L'onglet s'ouvre dès le premier envoi (le fichier est encore Validé ; il devient Officiel avec le
document signé), et le fichier s'ouvre dessus. Une fois Officiel, Diffuser est fermé (« Le document
est signé par tous »).

- « N sur M ont signé » ; une ligne par signataire : **Signé le 23/11 à 18 h 04**, **Pas encore**,
  **A ouvert**, ou **A refusé** avec le motif ;
- **Relancer les N** (ceux qui n'ont ni signé ni refusé), **Relancer** sur une ligne ;
  **Signer moi-même** si l'expéditeur fait partie des signataires ;
- **Journal de preuves** (replié) : les événements dans l'ordre, heure de Paris, en clair
  (« Signature de Karim Benali enregistrée »), avec l'appareil et l'adresse IP en dessous ;
- bouton principal **Produire le document signé**, grisé avec « Possible quand tout le monde a
  signé » tant qu'il manque une signature (décision de Seb, 22 octobre : pas de document signé
  partiel).

**Produire le document signé** :

- fait le PDF signé (§3) et le range **à côté de l'original** : « <nom du document> (signé).pdf » ;
- l'envoie par mail, en pièce jointe, à chaque signataire et à l'expéditeur, et le signale à
  l'adresse de contact de l'école (`email_contact`), PDF joint ;
- passe le fichier de signature en **Officiel** ;
- ouvre le PDF dans la visionneuse du téléphone ; ensuite le bouton principal devient **Voir le
  document signé** (comme la maquette).

Le refaire (par l'assistant, `produce_signed`, après une erreur d'envoi par exemple) range une
nouvelle version du même PDF ; pas de second bouton à l'écran.

**Corriger après Valider** : ⋯ › Modifier repasse en Brouillon, avec un avertissement « Les N
signatures déjà faites seront annulées ». Elles sont annulées (pas effacées du journal), les liens
restent les mêmes, il faudra renvoyer.

## 3. Le PDF

**Le PDF à signer** (produit à Valider, figé) : **le document seul**, sans zone de signature
(choix de l'étape 1 : la mise en page des cases dépend des signataires, connus seulement à
Diffuser ; l'Aperçu montre où elles iront) :

- **Word** : le texte du document de l'appli mis en page A4 (même moteur que le PV, pymupdf) ;
- **PDF** : le PDF déposé tel quel (refusé s'il est illisible ou protégé par un mot de passe).

**Les signatures** s'ajoutent au PDF signé (« Produire le document signé ») : pour un Word, la
section **Signatures** à la suite du texte ; pour un PDF, **une page Signatures** ajoutée à la fin
(on n'écrit pas par-dessus le contenu d'un PDF venu d'ailleurs : on ne sait pas où il y a de la
place).

La section Signatures a une case par signataire : mention, signature, nom, fonction (bureau) ou
qualité, « Signé en ligne le … à … », ou vide (« En attente de signature »). Le paraphe : une
petite case par signataire en bas à droite de chaque page, dans la marge.

**L'empreinte** est celle de ce PDF à signer, sans signatures. Elle est enregistrée à Valider
(événement `validated` du journal, avec le fichier rangé, le nombre de pages et le document
d'origine).

**Le PDF signé** (produit par « Produire le document signé ») : le PDF à signer, recalculé à partir
du fichier rangé (on vérifie que son empreinte n'a pas changé, sinon refus et alerte), avec les
signatures et les paraphes posés dans leurs cases, puis la dernière page **Certificat de preuves** :

- le document (nom, nombre de pages), qui l'a envoyé et quand ;
- **l'empreinte SHA-256 du document validé** ;
- les signataires : nom, adresse email du lien, fonction, date et heure de signature ;
- le journal complet : date et heure (Paris), événement, adresse IP, appareil (navigateur et
  système, en clair : « Chrome sur Android ») ;
- « Signature électronique simple au sens de l'article 1367 du Code civil et du règlement (UE)
  n° 910/2014. Les preuves sont conservées par <école> dans <appli>. »

L'empreinte du PDF signé ne peut pas figurer dans le PDF lui-même : elle est enregistrée au journal
(événement « produit ») et affichée dans Voir les résultats.

## 4. Rangement et droits

- Le fichier de signature et le PDF signé sont dans le dossier du document, avec ses droits.
- Préparer, Diffuser, Voir les résultats : niveau `manage` sur le fichier (comme le PV).
- Les preuves (journal, réponses, PDF figé) restent tant que le fichier existe, corbeille comprise ;
  vider la corbeille efface le fichier mais **pas le journal** (pas de clé étrangère, comme
  `doc_publications`), pour qu'une preuve reste disponible en cas de litige.

## 5. L'assistant fait la même chose (un bouton = un outil)

Déclarés dans `documents_contretemps/actions.py`, à côté de ceux du PV et des procurations, mêmes droits que l'écran.

| Bouton | Outil | Carte |
|---|---|---|
| Faire signer un document, Faire signer… | `prepare_signature(document, mode?, mention?, message?)` : crée le fichier de signature en Brouillon avec ce document | Faire / Annuler |
| Corriger le texte (Word) | `modifier_fichier_appli` (existe) | Annuler sous la modification |
| Valider | `validate_app_file(file)` (existe, élargi) : fige et passe en Validé | Faire / Annuler |
| Envoyer aux N, Relancer | `send_app_file(file, signers?)` (existe, élargi) : aux noms donnés (membres, fonctions du bureau, « Professeurs »…) ; sans noms, relance ceux qui n'ont pas signé | Faire / Annuler (noms écrits par le code) |
| Où en sont les signatures | lu avec le fichier (`lire_fichier`) | aucune |
| Produire le document signé | `produce_signed(file)` : refusé tant qu'il manque une signature | Faire / Annuler |

**L'assistant ne signe jamais**, ni pour la personne qui lui parle ni pour une autre, et ne coche
jamais le consentement : signer ne se fait que sur l'écran du signataire.

## 6. Données

Choix pour la base : **réutiliser ce que le PV utilise déjà** (envois, réponses, stockage) et
ajouter **une seule table**, le journal de preuves, parce qu'il doit garder l'adresse IP et
l'appareil, ne jamais être modifié et survivre à l'effacement du fichier, ce que ne permet pas
l'historique `doc_activity` (pensé pour l'onglet Historique, lié au nœud).

- **Le fichier de signature** : un fichier de l'appli (`doc_nodes`, Questionner). Son formulaire
  d'entrée contient un bloc `signDocument` (déclaré dans `blocks.js` et `app_content.py`) avec les
  réglages `source` (id du document dans Docs), `mode` (`end` ou `initials`), `mention`,
  `message`. Pour un Word, les blocs du texte importé sont **au-dessus** du bloc, dans le même
  contenu (ils se corrigent comme tout fichier de l'appli) ; pour un PDF, le bloc est seul et
  l'Aperçu montre les pages du PDF.
- **Import d'un Word** : LibreOffice (déjà dans l'image pour les aperçus, `preview.py`) le passe
  en HTML (filtre « HTML (StarWriter) », qui garde le gras), puis le serveur le transforme en
  blocs (`signing.html_to_blocks`) et l'enregistre comme une modification ordinaire. Côté serveur
  plutôt que navigateur : l'assistant et « ⋯ › Faire signer… » importent aussi un Word.
- **Le PDF figé** : rangé dans le stockage protégé par son empreinte (`doc_stored_files`), sans
  nœud visible dans le dossier. Sortir du Brouillon (Valider, ou Officiel directement) le produit ;
  revenir en Brouillon note `reset` au journal, et la prochaine validation fige de nouveau.
- **Les signataires** : des envois `doc_sends` de canal `sign` (comme le PV) ; `person_id` vide et
  `name` + `email` remplis pour quelqu'un hors de l'école. Expiration : `sent_at` du dernier envoi
  \+ 14 jours, calculée, pas de colonne.
- **Les signatures** : une réponse `doc_responses` par signataire, sous l'id du bloc :
  `{"signature": "data:image/png;base64,…", "initials": "…" | null, "consent": "<la phrase cochée>",
  "mention": "Lu et approuvé"}`. Repasser en Brouillon efface ces réponses (le texte va changer) ;
  le journal garde la trace (« signatures annulées »).
- **Nouvelle table `doc_sign_events`** (journal de preuves, on n'y fait que des `INSERT`) :
  `id`, `org_id` (index), `node_id` (index, sans clé étrangère), `send_id` (nullable), `event`
  (`validated`, `sent`, `reminded`, `opened`, `read`, `consented`, `signed`, `refused`, `reset`,
  `produced`), `at` (heure du serveur, UTC), `ip` (String 45), `user_agent` (String 255),
  `detail` (JSON : empreinte pour `validated` et `produced`, motif pour `refused`, nombre pour
  `sent`). Une migration Alembic qui crée la table (avec `has_table`, `create_all` passe avant).
- **Adresse IP** : la première adresse de `X-Forwarded-For` posé par Caddy, sinon
  `request.client.host`. Il y a deux Caddy (le partagé, puis celui du frontend) : `frontend/Caddyfile*`
  déclare `trusted_proxies static private_ranges` (accord de Seb, 22 octobre, étape 3) pour que le
  second garde l'adresse du téléphone au lieu de mettre celle du premier.
- **Appareil** : le texte brut du navigateur (`User-Agent`) au journal ; à l'écran et sur le
  certificat, en clair (« Chrome sur Android », `signing.device`).
- **Ouvert** : chaque ouverture du lien est notée (`opened`), pas seulement la première.
- **Refusé** : se lit dans le journal (dernier `refused` depuis le document figé), pas de colonne ;
  « Relancer les N » ne relance pas ceux qui ont refusé, « Relancer » sur leur ligne, oui.
- **Expiration** : 14 jours après `sent_at` du dernier envoi (posé quand le mail part) ; une
  relance rouvre donc un lien expiré.
- **Lecture jusqu'en bas** : le navigateur prévient le serveur quand la fin de la dernière page
  paraît à l'écran (`POST /documents/public/signing/<jeton>/read`), qui note l'événement à son
  heure ; `…/sign` est refusé sans `read` enregistré pour ce lien depuis le document figé, sans
  case cochée, sans tracé, ou sans initiales quand le paraphe est demandé. Les tracés sont des PNG
  (300 Ko au plus) ; le journal garde leur empreinte et la phrase de consentement.
- Toutes les requêtes filtrent par `org_id` ; test d'étanchéité entre écoles.
- Code : `backend/src/documents/signing.py` (comme `minutes.py`), écrans dans
  `frontend/src/modules/documents/app/` (`SignPrepare.jsx`, `SignPreview.jsx`, `SignSend.jsx`,
  `SignResults.jsx`, `SignLink.jsx` pour le signataire). Le lien reçu par mail reste
  `<adresse de l'école>/r/<jeton>` : la page du lien personnel (`PagePublique.jsx`) voit qu'il
  s'agit d'un document à signer et affiche `SignLink.jsx`.
- **Routes de l'étape 1** (`receiver.py`) : `POST …/signings` (créer, avec ou sans document),
  `PUT …/nodes/{id}/app/signing/document` (choisir le document), `GET …/nodes/{id}/app/signing`
  (document, pages, empreinte), `GET …/nodes/{id}/app/signing/pages/{n}` (image d'une page pour
  l'Aperçu).
- **Routes de l'étape 2** : `GET …/nodes/{id}/app/signing/signers` (bureau et suivi),
  `POST …/signing/preview` (récapitulatif), `POST …/signing/send` (membres, rôles, cours et
  `others` : nom + email), `POST …/signing/remind` (`send_ids`, ou tous ceux qui n'ont ni signé ni
  refusé) ; publiques, déclarées dans `comptes/rbac.py` : `GET /documents/public/signing/<jeton>`,
  `GET …/pages/{n}`, `POST …/read`, `POST …/sign`, `POST …/refuse`.
- **Étape 3** : `GET …/signing/signers` rend aussi `journal` (en clair) et `produced` (le dernier
  document signé : id, nom, empreinte) ; `POST …/nodes/{id}/app/signing/produce` (409 tant qu'il
  manque une signature, ou si l'empreinte du PDF figé relu ne correspond plus) ; les mails partent
  après la réponse. Le PDF signé est rangé à côté de l'original encore présent (sinon à côté du
  fichier de signature), avec les droits de la personne qui le produit. L'assistant lit l'état des
  signatures avec le fichier (`signing.status_text`).

## 7. Le PV d'AG passe par ce circuit

Décision de Seb, 22 octobre : un seul circuit de signature. Dans la dernière étape, l'écran
« Qui doit signer ? » du PV (`MinutesSign.jsx`) et `minutes.send_for_signature` /
`after_signature` utilisent `signing.py` : le PV gagne le lien qui expire, la lecture obligatoire,
la case de consentement, le journal et la page Certificat de preuves. **Rien d'autre ne change à
l'écran du PV** : présidence et secrétariat cochés d'avance, mail à l'adresse de contact à chaque
signature, passage en Officiel tout seul quand tous ont signé (le PV garde ce comportement, qui
était déjà décidé pour lui), annexe de la feuille d'émargement.

## 8. Décisions de Seb (22 octobre)

1. Coder la signature dans l'appli (pas de prestataire).
2. Trois étapes comme la convocation d'AG : Préparer (Mode Édition / Aperçu), Diffuser, Voir les
   résultats.
3. Préparer : PDF ou Word ; signature à la fin ou avec paraphe ; mention et message.
4. Un Word se corrige dans l'Aperçu ; un PDF ne se modifie pas.
5. Diffuser : Bureau, Professeurs, Élèves, ou n'importe qui par une recherche.
6. Voir les résultats : qui a signé, **Produire le document signé** rangé à côté de l'original.
7. Pas de document signé tant que tout le monde n'a pas signé.
8. Pas de code à 6 chiffres.
9. Tout le monde signe en même temps.
10. On peut refuser de signer, avec un motif.
11. On peut faire signer quelqu'un qui n'est pas membre (nom et adresse email).
12. Le PV d'AG passe par ce circuit (§7).

## 9. Étapes (une PR chacune, sur « vas-y »)

1. **Préparer** *(codée)* : tuile Faire signer un document, ⋯ › Faire signer…, les trois questions, import
   du Word, Aperçu (pages du PDF, zones de signature), **Valider** qui fige (PDF à signer,
   empreinte), table `doc_sign_events` et sa migration, outils `prepare_signature` et
   `validate_app_file`.
   *Vérification* : tests du PDF à signer (Word et PDF, avec et sans paraphe), de l'empreinte,
   du journal `validated`, du retour en Brouillon, de l'étanchéité ; parcours essayé à l'écran
   sur l'école de démo.
2. **Diffuser et signer** *(codée)* : Faire signer à qui ? (bureau, membres, quelqu'un d'autre), mails,
   Annuler 10 s, page du signataire (lecture, consentement, signature, initiales, refus), lien qui
   expire et se ferme, journal avec IP et appareil, Relancer, outil `send_app_file`.
   *Vérification* : tests du lien (expiré, fermé après signature, Brouillon), du refus d'une
   signature sans lecture ou sans case, du refus de signer, du journal, d'une personne hors école,
   de l'étanchéité ; signature essayée au doigt sur téléphone.
3. **Voir les résultats et le document signé** *(codée)* : suivi, journal, Signer moi-même, **Produire le
   document signé** (signatures, paraphes, certificat), mails avec le PDF, Officiel, outil
   `produce_signed`.
   *Vérification* : tests du PDF signé (cases remplies, certificat complet, empreinte d'origine
   vérifiée, refus si une signature manque), des mails ; PDF ouvert dans la visionneuse du
   téléphone.
4. **Le PV d'AG par ce circuit** (§7).
   *Vérification* : les tests du PV (`tests/test_documents_minutes.py`) passent toujours, plus
   lecture, consentement et certificat sur le PV.
