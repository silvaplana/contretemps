# Le fichier de base (fichiers de l'appli)

Version 0.1 du 16 octobre 2026, proposition de Claude à partir de la demande de Seb du même jour.
Complète `documents.md` (§5.4 socle, §5.6 modèles et parcours, §5.8 blocs, §5.9 diffusion,
§5.10 collecte, §7.1 bis familles). Le design des formulaires (contenu de l'onglet Préparer) sera
précisé par Seb ensuite : cette section n'en fixe que le cadre.

## 1. Idée

Tous les fichiers de l'appli (Informer ⓘ, Questionner ?, Agir ⚡) sont **le même fichier**, le fichier
de base. Ce qui change d'un fichier à l'autre, c'est ce qu'on met dedans, jamais le code. Les tuiles du
« + » (Convoquer l'AG, Faire un sondage, Ouvrir les inscriptions…) sont des **modèles** de ce fichier,
livrés avec l'appli et modifiables par chaque école (§5.6).

Un fichier de base contient **au plus deux formulaires**, qui sont toujours des pages web :

| Formulaire | À l'écran | Ce que c'est | Informer | Questionner | Agir |
|---|---|---|---|---|---|
| **d'entrée** | **Formulaire d'entrée** | ce que les gens reçoivent et ouvrent | page à lire | page avec des questions | page avec des questions qui créent quelque chose (inscription, paiement…) |
| **de sortie** | **Formulaire de résultat** | le tableau qui rassemble les réponses | aucun | les réponses, restées dans le fichier | les réponses, plus ce qu'elles ont créé (membres, inscriptions, paiements, « À rapprocher ») |

**La nature se choisit** (Seb, 16 octobre, remplace « déduite du contenu » du 15 octobre) : un fichier
vierge s'ouvre sur « Que voulez-vous faire avec ce fichier ? » et trois cartes Informer · Questionner ·
Agir (une phrase et des exemples chacune). Un fichier créé depuis une tuile du « + » ou par l'assistant
arrive déjà avec sa nature. Elle décide de ce qui est proposé : les blocs du menu « + Ajouter un bloc »
(Informer : mise en page seulement ; Questionner : + questions ; Agir : + blocs qui écrivent dans
l'appli), la présence du formulaire de résultat et de l'onglet Résultats, les réglages de Diffuser. Elle
se change en touchant la pastille de nature dans l'en-tête, tant que le fichier est en Brouillon ; les
blocs devenus inutiles sont retirés, avec Annuler 10 s.

Comme tout fichier, il a **son état** (Brouillon / Validé / Officiel, §5.4 et §7.1 ter) et **ses
permissions** (§4.4, Qui a accès ?), déjà définis : le fichier de base s'y appuie sans rien y changer.

## 2. Les quatre onglets

Un fichier de l'appli s'ouvre en **plein écran** (comme la visionneuse actuelle) ; ses onglets
remplacent ceux de Docs, il n'y a donc pas de quatrième niveau de navigation (§6.1).

```
┌ ← Convocation AG 2026          ✎  ⋯ ┐   titre, badge de statut, menu
│ Préparer │ Aperçu │ Diffuser │ Résultats │   onglets (Résultats : Questionner et Agir)
│                                          │
│   …contenu de l'onglet…                  │
│                                          │
│            [ bouton principal ]          │   un seul, change avec l'onglet
└──────────────────────────────────────────┘
```

| Onglet | Rôle | Sélecteur interne | Bouton principal | Informer | Questionner | Agir |
|---|---|---|---|---|---|---|
| **Préparer** | concevoir les formulaires (design, à préciser par Seb) | `Formulaire d'entrée \| Formulaire de résultat` | **Valider** | ✓ (sans sélecteur) | ✓ | ✓ |
| **Aperçu** | voir exactement ce que les gens verront, et l'essayer | `Téléphone \| Ordinateur \| A4` | **Essayer** | ✓ | ✓ | ✓ |
| **Diffuser** | qui reçoit, comment, jusqu'à quand | `Des personnes choisies \| Tout le monde` (§5.9) | **Envoyer** ou **Publier** | ✓ | ✓ | ✓ |
| **Résultats** | le formulaire de sortie, rempli | aucun | **Exporter** | — | ✓ | ✓ |

Libellés courts pour tenir à quatre sur 360 px en 17 px (« Préparer », « Aperçu », « Diffuser »,
« Résultats » font moins de 90 px chacun).

### 2.1 Préparer

Le seul onglet où l'on modifie. Deux positions quand il y a des questions :

- **Formulaire d'entrée** : fait de blocs (texte, image, vidéo, questions, signature,
  paiement… §5.8). Pour Informer c'est tout l'onglet.
- **Formulaire de résultat** : lui aussi fait de blocs (voir plus bas). Il est **fabriqué tout seul** à partir des questions
  (une colonne par question, un compteur par choix, total des montants), donc on peut ne jamais y
  toucher. On peut le retoucher : ordre et visibilité des colonnes, compteurs en tête (« 48 / 63 ont
  répondu », « 2 340 € encaissés », « quorum atteint »), un graphique simple par question à choix,
  regroupement (par cours, par famille), calculs (bloc Calcul §5.8 : l'IA écrit la formule, jamais le
  chiffre).

**Comment on conçoit (Seb, 16 octobre)** :

Deux manières, **au choix et mélangeables** (Seb, 16 octobre) :

- **Par le chat**, **un seul chat par fichier**, pour la page et les résultats ensemble : les deux sont
  liés (une question de la page = une colonne des résultats), une demande comme « ajoute une question sur
  les allergies » modifie les deux d'un coup. Le chat sait quel formulaire est affiché et part de là ; on
  peut viser l'autre (« dans les résultats, fais le total par cours »). Toute la discussion est gardée en
  base avec le fichier ; chaque réponse de l'IA crée une version, sur laquelle on peut revenir (§5.4).
  L'IA répond par opérations sur les blocs, jamais par du HTML.
  **Sources d'inspiration (Seb, 16 octobre)** : dans le chat, on peut **glisser, coller ou joindre**
  une image (capture d'un formulaire vu sur WhatsApp, photo d'une affiche), **prendre une photo avec le
  téléphone** (appareil photo), ou coller un **lien** vers une page web, puis dire « fais la même
  chose ». Bouton trombone à gauche de la zone de saisie : Prendre une photo · Choisir une image ·
  Coller un lien ; sur ordinateur, glisser-déposer dans le fil ou Ctrl+V. L'IA lit l'image (modèle avec
  vision) ou la page (lecture web de l'assistant, déjà en place) et en tire la structure et les questions,
  jamais le texte ou les images tels quels si elles ne sont pas à l'école. Les pièces jointes restent dans
  l'historique du chat, avec le fichier ; une image peut aussi être reprise dans la page (bloc Image).
- **À la main avec BlockNote**, en « ce que vous voyez est ce que vous obtenez » : on clique dans le texte
  et on corrige, « / » ajoute un bloc, on glisse les blocs pour les réordonner. BlockNote lit et écrit le
  même JSON de blocs que le chat. Nos blocs à nous (question, signature, paiement…) sont déclarés comme
  blocs BlockNote **avec les mêmes composants React que l'Aperçu** : ce qu'on voit en modifiant est ce que
  les gens recevront.
- **Une seule source : le JSON** (Seb, 16 octobre). Le chat et BlockNote modifient le même JSON et
  l'écoutent tous les deux : une opération du chat apparaît aussitôt dans BlockNote, une correction à la
  main est enregistrée (version « modifiée à la main ») et le chat repart toujours de la version courante
  (§5.4).
- **Les deux formulaires s'éditent des deux façons**. Le formulaire de résultat est lui aussi une suite de
  blocs : texte libre (un titre, une phrase d'explication) et blocs de résultat propres au socle
  (**Tableau des réponses**, **Compteur** « 48 / 63 ont répondu », **Graphique** d'une question à choix,
  **Total** d'un montant, **À rapprocher** pour Agir). On les déplace et on les règle dans BlockNote
  comme n'importe quel bloc ; le contenu (les réponses) vient de la base, jamais écrit à la main.

### 2.2 Aperçu

La page telle que la recevra un membre, sans aucun outil autour : téléphone, ordinateur, ou A4 (le PDF
figé est imprimé par Chromium depuis cette même page). Pour Questionner et Agir, le sélecteur
`Formulaire d'entrée | Formulaire de résultat` existe aussi ici : les résultats sont montrés avec des réponses d'exemple tant
qu'il n'y en a pas de vraies.

**Essayer** remplit la page pour de vrai, en mode test : la réponse apparaît dans les résultats avec une
pastille « Essai » et ne crée rien dans l'appli (ni membre, ni paiement) ; « Effacer les essais » les
retire. C'est le « Essayer » des parcours (§5.6).

**Onglet d'ouverture selon l'état (Seb, 16 octobre)** : Brouillon → Préparer ; Validé → Diffuser ;
Officiel → Résultats (Aperçu pour Informer, qui n'a pas de Résultats). Ceux qui ne peuvent que voir le
fichier arrivent toujours sur la page elle-même.

### 2.3 Diffuser

Reprend l'écran « Diffuser » du §5.9 et la collecte du §5.10, en un seul endroit :

**Pourquoi un onglet à part et pas dans Préparer (question de Seb du 16 octobre)** : on diffuse quand le
fichier est Validé ou Officiel, donc justement quand Préparer est grisé ; la diffusion a une suite à
suivre (qui l'a reçu, ouvert, relances, adresse, QR code) ; et un envoi ne se rattrape pas, il faut un
écran récapitulatif avant d'envoyer. Mais **le chat peut tout remplir** : « envoie par mail et SMS au
cours Éveil, relance une semaine avant » dans la bulle (disponible dans tous les onglets) ouvre Diffuser
déjà rempli ; l'envoi ne part qu'au bouton **Envoyer**, sur la carte Faire / Annuler.

On diffuse **le formulaire d'entrée** seulement. Quand les répondants doivent voir les résultats (un
sondage, un choix de date), c'est le réglage « visibilité des réponses » (Résultats visibles ou Publique,
§5.10) : le formulaire de résultat s'affiche sous le formulaire d'entrée après qu'on a répondu.

**L'email envoyé (Seb, 16 octobre)** :

- **Expéditeur** : le nom de l'école avec une adresse de l'appli (« École de danse du Beausset »
  `<noreply@contretemps.silvaplana.cloud>`), et **réponse à** l'adresse de contact de l'école (souvent un
  Gmail) : quand quelqu'un clique Répondre, ça arrive dans le Gmail de l'asso. On n'envoie jamais *depuis*
  l'adresse Gmail elle-même : Gmail interdit à un autre serveur d'envoyer en son nom (DMARC), le mail
  finirait en indésirables ou serait refusé. Envoyer vraiment depuis le compte Gmail de l'asso (connexion
  Google) serait possible plus tard, limité à environ 500 messages par jour.
- **Contenu** : un email ne peut pas contenir un vrai site (pas de script, formulaires mal supportés,
  bloqués par Gmail et Outlook). Le mail affiche donc **une version lisible de la page**, fabriquée depuis
  le même JSON : pour Informer, tout le texte et les images, plus un bouton « Voir en ligne » ; pour
  Questionner et Agir, l'introduction, les questions affichées et un gros bouton **Répondre** (lien
  personnel). Quand la première question est un choix simple (« Je viens / Je donne procuration / Je ne
  viens pas »), chaque choix est **un bouton dans le mail** : un clic ouvre la page avec la réponse déjà
  cochée, il ne reste qu'à confirmer.

Canaux : **email** (core, §5 de la mémoire email), **notification de l'appli**, **SMS** (nouveau : via le
même prestataire que l'email, Brevo ou équivalent, payant au message, coût affiché avant l'envoi ; un SMS
ne contient que le texte court et le lien personnel).

- **Des personnes choisies** : membres, groupes (un cours, Professeurs…), rôles, adresses externes ;
  lien personnel par personne ; canal (email, notification de l'appli) ; pour Questionner et Agir :
  date limite, relances aux non-répondants, une ou plusieurs réponses, réponse modifiable ou non,
  visibilité des réponses (Privée, Résultats visibles, Publique).
- **Tout le monde** : adresse publique `https://<page>.<école>.contretemps.silvaplana.cloud`, nom de page créé automatiquement et jamais en double dans l'école (§5.5), bouton
  Copier, QR code pour l'affiche. Confirmation « Visible par tout le monde sur internet ».
- Les deux à la fois sont possibles ; toutes les réponses vont au même tableau (colonne Provenance).
- Règle de statut : on ne diffuse qu'une version **Validée ou Officielle**. Sur un brouillon, l'onglet
  s'affiche mais le bouton est grisé avec la raison (« Validez d'abord le fichier »).
- Pour Informer, l'onglet montre aussi **qui a ouvert** (« 23 / 30 ont lu »), grâce aux liens
  personnels : c'est ce qui remplace l'onglet Résultats.

### 2.4 Résultats

Le formulaire de sortie, rempli. En tête les compteurs choisis dans Préparer, puis le tableau (une ligne
par personne : répondu / en cours / pas répondu), filtres, Exporter (.xlsx). Pour Agir, en plus : ce que
chaque réponse a créé (lien vers le membre, l'inscription, le paiement) et la file **À rapprocher** quand
l'appli n'est pas sûre de la personne (§5.9). À la clôture, les résultats sont figés avec la version et
peuvent servir de fichier lié (le PV lit les votes).

## 3. Qui voit quoi

- **Ceux qui peuvent modifier le fichier** (profs et admins dans Privé, ou droit Modifier) voient les
  quatre onglets.
- **Ceux qui peuvent seulement le voir** n'ont pas d'onglets : ils ont la page, comme un destinataire.
  S'ils sont aussi destinataires, ils y répondent directement.
- **Les résultats** suivent la visibilité choisie dans Diffuser : avec « Résultats visibles » ou
  « Publique », un destinataire voit les totaux (ou les réponses) sous la page après avoir répondu.

## 4. Statut, onglets et droits (Seb, 16 octobre)

**L'état se change en un geste** : le badge de l'en-tête (✎ / ✓ / sceau, avec le mot en entier) est un
bouton ; le toucher ouvre `Brouillon | Validé | Officiel`, l'état actuel coché. Les règles du §5.4
restent : Officiel demande le niveau `manage` et fige le contenu ; pour modifier un fichier Officiel on
crée un nouveau brouillon ; un Validé peut revenir en Brouillon.

**Les onglets suivent l'état** :

| État | Préparer | Aperçu | Diffuser | Résultats |
|---|---|---|---|---|
| Brouillon | ✓ | ✓ | grisé | grisé |
| Validé | grisé | ✓ | ✓ | grisé (à confirmer, voir §7) |
| Officiel | grisé | ✓ | ✓ | ✓ |

Un onglet indisponible reste visible, **grisé avec sa raison** au toucher (« Repassez en Brouillon pour
modifier », « Validez d'abord le fichier ») : même règle que les actions interdites de l'explorateur
(§6.3 bis), et on comprend toujours où l'on en est. Pour Informer, l'onglet Résultats n'existe pas du
tout.

**Droits** : un bouton **Partager** (icône personnes) toujours visible dans l'en-tête ouvre « Qui a
accès ? » (§4.4 bis), et le menu ⋯ reprend la feuille d'actions de l'explorateur (Partager, Renommer,
Déplacer, Télécharger, Propriétés, Supprimer). Le ⋯ existe déjà dans la visionneuse actuelle.

**Modifications en cours de route** :

- Modifier un fichier déjà diffusé : on repasse en Brouillon ; ce qui est en ligne ne change qu'au
  bouton « Mettre à jour la page diffusée » (même règle que la publication, §5.5).
- Ajouter une question après les premières réponses : permis, la colonne est vide pour ceux qui ont déjà
  répondu. Supprimer une question qui a des réponses : la colonne est **masquée**, pas effacée.
- Officiel : le contenu est figé (PDF figé) ; les réponses continuent d'arriver jusqu'à la date limite,
  puis le tableau est figé à la clôture.

## 5. Modèles et parcours

- Un **modèle** (§5.6) est un fichier de base promu : page + réglages des résultats + réglages de
  diffusion par défaut, sans les réponses.
- **Faire un modèle (Seb, 16 octobre)** : action **« Faire un modèle »** dans le menu ⋯ du fichier ouvert
  (et dans « Plus… » de l'explorateur), réservée aux admins (niveau `manage`). Une feuille courte :
  **nom de la tuile, au verbe** (proposé par l'IA : « Organiser la fête de fin d'année »), **section du +**
  (la nature du fichier, déjà connue), et, facultatif, **« Ce qui change à chaque fois »** : l'IA repère
  dates, lieux, montants et propose d'en faire des questions posées à la création (cases à cocher).
  Bouton **Créer le modèle**. Copié : les deux formulaires et les réglages de diffusion ; jamais les
  réponses, les destinataires nommés ni l'historique du chat.
- **Dans le +** : la tuile apparaît dans la section de sa nature (Informer, Questionner, Agir), avec un
  petit coin plié et la mention « de l'école » pour la distinguer des modèles livrés. Toucher la tuile crée
  un fichier Brouillon déjà rempli (après les questions éventuelles), ouvert sur Préparer. Les modèles se
  renomment, se cachent ou se suppriment par appui long sur la tuile (admins).
- Un **parcours** (Convoquer l'AG) est un modèle qui pose d'abord quelques questions **à celui qui crée
  le fichier** (date, lieu, ordre du jour), pas aux membres. Ce n'est pas un formulaire de plus : quand on
  modifie le modèle lui-même, l'onglet Préparer gagne une troisième position
  `Formulaire d'entrée | Formulaire de résultat | Avant de commencer` (questions au créateur, §5.6), qui n'existe que sur les
  modèles. L'éditeur `Contenu | Questions | Envoi` du §5.6 devient donc ces onglets-ci, il n'y a qu'un
  seul éditeur.

## 6. Données

Pas de nouvelle table pour le cadre (le détail des blocs viendra avec le design) :

- `doc_nodes.kind = 'app'` pour un fichier de l'appli, `family` recalculée à chaque enregistrement à
  partir des blocs, `status` comme aujourd'hui ;
- `doc_versions.content_json` porte les deux formulaires, versionnés et figés ensemble :

```json
{ "schema": 1,
  "entry":   { "blocks": [ ... ] },
  "result":  { "blocks": [ ... ] },
  "starter": { "questions": [ ... ] } }
```

  `result` vide = fabriqué automatiquement depuis les questions (Tableau des réponses + un Compteur) ; `starter` seulement sur un modèle ;
- la diffusion dans `doc_collections`, les réponses dans `doc_responses` (§5.10), avec une colonne
  `is_test` pour les essais.

### 6.1 Où vont les réponses : pas de table créée à la volée (question de Seb du 16 octobre)

On ne sait pas à l'avance ce que contient un formulaire, mais **on ne crée jamais de table ni de fichier
par formulaire**. Une table créée à la volée, c'est des migrations par école impossibles à suivre, des
sauvegardes et des droits à refaire à chaque fois ; un fichier (CSV, Excel) ne supporte pas deux
personnes qui répondent en même temps ni les droits par personne. À la place, **une table générique
unique**, `doc_responses`, et c'est le **formulaire d'entrée lui-même qui sert de schéma** :

| Colonne | Remarque |
|---|---|
| `id`, `org_id`, `node_id` | le fichier |
| `version_id` | la version du formulaire à laquelle la personne a répondu |
| `person_id` null, `email`, `token` | qui (lien personnel) ou anonyme (adresse publique) |
| `status` | pas répondu / en cours / répondu ; `is_test` pour les essais |
| `values` | **JSON** : une entrée par question, sous son identifiant stable |
| `links` | JSON : ce que la réponse a créé (membre, inscription, paiement, fichier déposé) |
| `source`, `created_at`, `updated_at` | provenance (lien personnel, adresse publique), dates |

Exemple d'une inscription avec deux enfants :

```json
{ "q_payeur_nom": "Martin", "q_payeur_email": "c.martin@exemple.fr",
  "q_enfants": [
    { "q_prenom": "Léa", "q_naissance": "2017-03-02", "q_cours": ["eveil"], "q_certificat": {"file": 812} },
    { "q_prenom": "Tom", "q_naissance": "2014-11-20", "q_cours": ["jazz-1", "hip-hop"] } ],
  "q_droit_image": true, "q_signature": {"proof": 55}, "q_paiement": {"payment": 301} }
```

- **Formulaires complexes** : un bloc **Groupe répété** (« Ajouter un enfant ») donne une liste d'objets ;
  les conditions (« seulement si… ») masquent des questions sans changer le stockage ; les fichiers,
  signatures et paiements sont rangés dans leurs propres tables (`stored_files`, preuves de signature,
  paiements) et la réponse n'en garde que la référence.
- **Contrôle** : à l'envoi, le serveur valide `values` contre le formulaire de la version (types,
  obligatoires, choix permis, tailles) ; une réponse invalide est refusée, jamais stockée à moitié.
- **Affichage** : le formulaire de résultat lit les lignes et la définition des questions (libellés,
  types) pour faire colonnes, compteurs et graphiques. Volumes d'une asso : quelques centaines de lignes
  par fichier, calculés sans souci ; SQLite sait lire le JSON (`json_extract`), Postgres l'indexe (JSONB).
  Export .xlsx : une colonne par question, une ligne par enfant pour un groupe répété.
- **Le formulaire change après des réponses** : l'identifiant d'une question ne change jamais, même si on
  la renomme ; une question supprimée garde ses réponses (colonne masquée) ; chaque réponse sait à quelle
  version elle a répondu.
- **Agir : deux couches.** La réponse brute reste toujours dans `doc_responses`. En plus, les liaisons du
  §5.9 écrivent dans les **vraies tables existantes** (membres, inscriptions aux cours, paiements) par des
  actions déclarées par les modules ; une information que la base ne connaît pas va dans les **champs
  personnalisés** des membres (§5.9, JSON aussi). L'IA ne crée donc jamais de structure, elle choisit
  parmi les actions et les champs qui existent.

## 7. À trancher par Seb

1. **Noms des onglets** : `Préparer | Aperçu | Diffuser | Résultats`. Recommandation : **ceux-là**.
   « Diffuser » plutôt que « Publier », parce qu'il couvre aussi l'envoi à des personnes choisies.
2. ~~Noms des deux formulaires~~ : **décidé par Seb le 16 octobre : « Formulaire d'entrée » et
   « Formulaire de résultat »**, toujours ces deux noms.
3. **Informer sans onglet Résultats**, le « qui a lu » étant dans Diffuser. Recommandation : **oui**.
4. ~~Onglet d'ouverture~~ : **décidé par Seb le 16 octobre, selon l'état** (voir §2.2).
5. **En Validé, où vont les réponses ?** Avec le tableau du §4, un fichier Validé peut être diffusé mais
   n'a pas d'onglet Résultats. Recommandation : **en Validé, on diffuse seulement à soi et aux
   relecteurs (essai grandeur nature) ; la diffusion à tous et la collecte s'ouvrent en Officiel.**
   Autre possibilité : afficher Résultats dès qu'on diffuse, en Validé comme en Officiel.
