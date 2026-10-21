# Sous-module `procurations` (module Documents)

Version 0.1 du 20 octobre 2026, proposition de Claude à partir de la demande de Seb du même jour :
« concevoir, produire, diffuser et collecter des procurations pour une assemblée générale
d'association loi 1901 », « par mail : on enverra à chaque membre le fait de pouvoir faire une
procuration à quelqu'un pour pouvoir voter à l'assemblée générale de telle date ».

Sous-module du module Documents, posé sur le **fichier de base** (`fichier-de-base.md`) : rien de
propre à la danse, il part tel quel dans AppBase. Maquettes : côté membre (mail, choix du
représentant, signature, pouvoir signé en PDF) https://claude.ai/artifact/VV7x9zz1b5b8cu5rnYATkx ;
parcours « Convoquer l'AG » côté trésorière https://claude.ai/artifact/1Ptq5myAcGYw8d6rsmjBRj.

**Convocation et procuration : un seul envoi, deux documents** (question de Seb du 20 octobre). La loi
de 1901 n'impose rien, les statuts fixent délai de convocation, procuration permise, plafond de
pouvoirs et quorum ; l'usage courant est une convocation avec un pouvoir joint. Ici : un seul mail
(la convocation) avec trois boutons, et le pouvoir, document à part entière (PDF signé), se remplit
depuis « Je donne procuration ».

Ce n'est pas le volet financier de l'AG (Financier > AG, `financier.md` §5, le PowerPoint) : ici, la
convocation, les pouvoirs, le quorum et la feuille d'émargement.

---

## 1. Le résultat final

### 1.1 Ce que reçoit chaque membre (par email)

```
De : École de danse Contretemps <noreply@contretemps.silvaplana.cloud>
Objet : Assemblée générale du samedi 21 novembre 2026

Bonjour Karim,

L'assemblée générale aura lieu le samedi 21 novembre 2026 à 14 h,
salle des fêtes de Vandœuvre.

Ordre du jour : 1. Rapport moral … 5. Cotisation 2027-2028

Serez-vous là ?
 [ Je viens ]  [ Je donne procuration ]  [ Je ne viens pas ]

Pas de compte ni de mot de passe : ce lien est le vôtre.
```

Chaque bouton ouvre la page de l'AG avec ce choix déjà coché (lien personnel, `fichier-de-base.md`
§2.3). « Je donne procuration » mène à deux écrans, gros et simples :

1. **Qui vous représente ?** Un champ **Chercher un membre** (on tape quelques lettres du nom), puis
   la liste des membres convoqués par ordre alphabétique (nom seulement), plus en tête
   **« Je laisse le bureau choisir »** (pouvoir en blanc, §3.4). Un membre qui a déjà son nombre
   maximal de pouvoirs est grisé, avec « a déjà 2 pouvoirs ». Bouton **Continuer**.
2. **Signez avec le doigt.** La phrase du pouvoir en entier (§3.3), la zone de signature (bloc
   Signature existant), bouton **Signer**.

Puis « Votre procuration est enregistrée. Vous pouvez changer d'avis avec le même lien jusqu'au début
de l'assemblée. » La personne choisie reçoit un email « Karim Benali vous a donné procuration pour
l'assemblée générale du 21 novembre » (étape 3).

### 1.2 Ce que voit le bureau (onglet Résultats du fichier)

```
┌ ← AG du 21 novembre 2026        Officiel ⋯ ┐
│ Préparer │ Aperçu │ Diffuser │ Résultats    │
│                                             │
│   61 / 87 ont répondu                       │
│   34 viennent · 12 procurations · 15 non    │
│   Quorum : 46 voix sur 87, il en faut 22 ✓  │
│                                             │
│   Pouvoirs reçus                            │
│   Martine Colin (présidente)   3 + 2 en blanc│
│   Sophie Marchal               2            │
│   …                                         │
│   Réponses (une ligne par personne)         │
│        [ Feuille d'émargement ]             │
└─────────────────────────────────────────────┘
```

Le jour de l'AG, **Feuille d'émargement** (étape 2) : la liste des membres, on touche un nom pour le
marquer présent ; le quorum se recalcule en direct ; on imprime ou on exporte la feuille (PDF, avec le
nombre de voix de chacun) pour le procès-verbal.

### 1.3 Ce que fait celui qui convoque

**Par l'écran, sans l'assistant (Seb, 20 octobre)** : Docs › + › **Convoquer l'AG**, puis **deux
questions seulement**, une par écran :

1. **Quelle assemblée ?** **Ordinaire** (cochée d'avance) ou **Extraordinaire**. Une seule tuile, pas
   deux. Le mot va dans le titre (« Assemblée générale extraordinaire du … »), dans le pouvoir et dans le
   nom du dossier ; le quorum par défaut de l'extraordinaire est réglé à part dans le bloc.
2. **Quand ?** Date et heure (rappel si la convocation part moins de 15 jours avant).

Le reste est rempli d'avance, modifiable ensuite dans Préparer :

- **le lieu** : celui de la dernière AG, sinon l'adresse de l'école ;
- **l'ordre du jour** : repris de la convocation de l'année précédente (même sorte d'assemblée) ; s'il
  n'y en a pas, un ordre du jour de base. Ordinaire : rapport moral, rapport financier et approbation
  des comptes, budget prévisionnel, renouvellement du bureau, questions diverses. Extraordinaire :
  modification des statuts, questions diverses.

(La maquette « Convoquer l'AG », https://claude.ai/artifact/1Ptq5myAcGYw8d6rsmjBRj, posait trois
questions date / lieu / ordre du jour : remplacée par ces deux-là.)

Puis, **trois temps** (Seb, 20 octobre) :

1. **Aperçu modifiable** : la convocation s'affiche telle que les membres la recevront, et on la corrige
   directement dedans (on touche un texte et on écrit, comme dans Préparer). Bouton principal **Valider**.
2. **Valider** fige la convocation : le fichier passe directement en **Officiel** (pas d'étape
   « Validé / relecteurs » pour ce parcours ; « Faire relire » reste dans le menu ⋯ pour qui le veut).
   Pour la corriger ensuite : ⋯ › Modifier, qui repasse en Brouillon tant que rien n'est envoyé.
3. Apparaissent alors **Envoyer aux 87 membres** (bouton principal ; confirmation « Envoyer la
   convocation ? », puis Annuler 10 s) et **Télécharger la convocation** (PDF A4, pour l'imprimer ou
   l'envoyer autrement). Sous le bouton : « Pour : 87 membres · par email », « Changer » ouvre Diffuser.
   Les destinataires proposés : ceux de la dernière AG, sinon tous les membres de la saison.
   Dessous, facultatif (Seb, 20 octobre) : **Faire un essai avec un membre** : on choisit une personne,
   elle reçoit le mail avec « [Essai] » ; sa réponse arrive dans Résultats marquée « Essai », sans
   compter (comme « M'envoyer un essai », `fichier-de-base.md` §2.3, mais à la personne choisie).

**Deux portes, même résultat (Seb, 20 octobre)** : l'**Assistant IA** suit exactement les mêmes
étapes que l'écran, par la même fonction du code (une seule fonction « préparer la convocation »,
appelée par la tuile et par l'action `convene_assembly` de `documents/actions.py`) :

1. **Les deux questions, sauf si la demande y répond déjà.** « Prépare l'AG extraordinaire du
   17 mars à 19 h » : rien à demander. « Prépare l'AG » : l'assistant demande « Ordinaire ou
   extraordinaire ? » puis « Quelle date ? », une question fermée à la fois. Même recherche du dossier
   (§4), même question s'il n'est pas sûr.
2. **L'aperçu** : l'assistant crée le fichier (Brouillon) et le montre ouvert à côté de la discussion
   (sur téléphone, une carte « Convocation AGE du 17 mars » qui l'ouvre). On le corrige **par la
   discussion** (« ajoute un point sur le spectacle », « change la salle ») ou à la main ; chaque
   modification avec Annuler, comme pour tout fichier de base (`fichier-de-base.md` §2.1).
3. **Valider puis Envoyer** : deux cartes **Faire / Annuler**, « Valider la convocation ? » puis
   « Envoyer la convocation à 87 membres ? ». Rien ne part sans ce toucher ; « Télécharger la
   convocation » est proposé à côté. L'assistant ne signe jamais à la place d'un membre et n'écrit
   aucun chiffre (dates et effectifs viennent du code).

### 1.4 Les outils de l'assistant (Seb, 20 octobre : « à toi de savoir quels outils il faut »)

Règle : **un bouton de l'écran = un outil de l'assistant**, qui appelle la même fonction du code.
Déclarés dans `documents/actions.py` (dataclass Action, format de l'Assistant IA), droits identiques à
l'écran (niveau `manage` sur le fichier, comme Diffuser).

| Étape à l'écran | Outil | Carte | Existe déjà ? |
|---|---|---|---|
| Convoquer l'AG + les deux questions + dossier | `convene_assembly(kind, date, time, folder_id?)` : crée la convocation en Brouillon ; si le dossier est incertain, renvoie les dossiers trouvés et l'assistant pose la question | aucune (un brouillon s'efface) | non, étape 1 |
| Corriger l'aperçu | `modifier_fichier_appli` | Annuler sous la modification | **oui** (`assistant/fichier_appli.py`) |
| Valider | `validate_app_file(node_id)` : passe en Officiel | Faire / Annuler | non, étape 1 |
| Envoyer aux N membres | `send_app_file(node_id, recipients?)` : destinataires par défaut comme à l'écran ; le nombre et les noms de la carte viennent du code | Faire / Annuler | non, étape 1 (reprend `app_sends.py`) |
| Télécharger la convocation | `app_file_pdf(node_id)` : renvoie le lien du PDF | aucune | non, étape 1 |
| Voir les réponses | `assembly_status(node_id)` : viennent, procurations (qui à qui), ne viennent pas, sans réponse, quorum ; chiffres calculés par le code | aucune | non, étape 4 |
| Relancer | `remind_non_respondents(node_id)` | Faire / Annuler | non, étape 4 |
| Télécharger le récapitulatif, les pouvoirs | `assembly_summary_pdf(node_id)`, `assembly_proxies_zip(node_id)` | aucune | non, étape 4 |

`validate_app_file`, `send_app_file` et `app_file_pdf` servent à tout fichier de base, pas seulement à
l'AG. Jamais d'outil pour signer, ni pour répondre à la place d'un membre.

## 2. Hypothèses (à confirmer par Seb)

1. **Un bloc, pas un écran à part.** La procuration est un bloc du fichier de base, nature Questionner :
   la diffusion par email, le lien personnel, la signature au doigt, la collecte dans `doc_responses`
   et l'onglet Résultats existent déjà et servent tels quels. Pas de nouveau module, pas de nouveau
   point de branchement.
2. **Les membres convoqués = les destinataires de Diffuser.** Celui qui convoque choisit qui vote
   (rôle, cours, personnes) ; l'appli ne décide pas qui est « à jour de cotisation ». *(Contretemps : une
   personne = une fiche ; pour un mineur, on convoque le parent dont l'adresse est sur la fiche, comme
   tous les envois d'aujourd'hui.)*
3. **On ne peut donner procuration qu'à un membre convoqué** (pas à une personne extérieure), ce que
   prévoient la plupart des statuts.
4. **Signature simple maison** (`documents.md` §12 décision 13) : le lien personnel prouve l'adresse
   email, le tracé au doigt et l'horodatage font le reste. Pas de code par SMS.
5. **Pas de page publique** pour ce bloc : une procuration exige de savoir qui la donne, donc un lien
   personnel. « Tout le monde » (adresse publique) est refusé avec la raison.
6. **Les votes eux-mêmes** (résolution par résolution) sont hors de ce sous-module : la feuille
   d'émargement donne le nombre de voix de chaque présent, le futur bloc Vote s'en servira.

## 3. Le bloc « Présence et procuration »

### 3.1 Réglages (dans Préparer, au toucher du bloc)

Trois au plus, avec des valeurs par défaut qui conviennent à la plupart des statuts :

| Réglage | Défaut | Remarque |
|---|---|---|
| **Pouvoirs au plus par personne** | 2 | fixé par les statuts ; 0 = pas de limite |
| **Pouvoir en blanc donné à** | la présidence | une personne choisie parmi les membres (présidente, secrétaire) |
| **Quorum** | aucun | aucun, un quart, un tiers, la moitié des membres convoqués, ou un nombre |

Le titre, la date et le lieu ne sont pas des réglages : ils sont dans le texte de la convocation, au
dessus du bloc. La phrase du pouvoir (§3.3) reprend le titre du fichier.

### 3.2 La réponse

Une seule question à trois choix, **Je viens / Je donne procuration / Je ne viens pas**, puis, pour la
procuration seulement, le mandataire et la signature. Rangée dans `doc_responses.values` sous
l'identifiant du bloc :

```json
{ "b_presence": { "answer": "proxy", "proxy_to": 128, "signature": "data:image/png;base64,…",
                  "signed_at": "2026-11-02T18:41:07Z" } }
```

`answer` vaut `attend`, `proxy` ou `absent` ; `proxy_to` est un `person_id` ou `"blank"`.

### 3.3 Le texte du pouvoir

Fixe, rempli par le code (jamais par l'IA) :

> Je soussigné(e) **Karim Benali**, membre de **École de danse Contretemps**, donne pouvoir à
> **Martine Colin** pour me représenter à l'**assemblée générale du 21 novembre 2026** et prendre part
> aux votes en mon nom. Fait le 2 novembre 2026.

Pouvoir en blanc : « … donne pouvoir à la personne désignée par le bureau (à défaut, **Martine
Colin**, présidente) … ».

### 3.4 Règles contrôlées par le serveur

À l'enregistrement de la réponse (refus avec une phrase claire, jamais d'enregistrement à moitié) :

- **pas à soi-même** ;
- **mandataire convoqué** : il a reçu le fichier par Diffuser (`doc_sends` non essai, même fichier) ;
- **plafond** : le mandataire n'a pas déjà le nombre maximal de pouvoirs (« Sophie Marchal a déjà
  2 pouvoirs, choisissez quelqu'un d'autre ») ; les pouvoirs en blanc ne comptent pas dans le plafond
  de la présidence (usage courant ; à confirmer, §6) ;
- **pas de chaîne** : on ne peut pas donner procuration à quelqu'un qui a lui-même donné procuration,
  ni donner procuration quand on a reçu des pouvoirs (« Vous avez reçu 2 pouvoirs : venez, ou
  prévenez Karim et Élodie pour qu'ils choisissent quelqu'un d'autre ») ;
- **signature obligatoire** pour `proxy` ;
- **changer d'avis** : même lien, jusqu'au début de l'assemblée (date et heure du bloc, sinon jusqu'à
  la clôture du fichier) ; une procuration retirée libère la place chez le mandataire.

Le jour de l'AG, **la présence l'emporte** : un mandant pointé présent sur la feuille d'émargement
reprend sa voix, sa procuration ne compte plus.

### 3.5 Comptage

Calculé par le code, jamais par l'IA :

- **voix d'un présent** = 1 + pouvoirs reçus de mandants absents ;
- **pouvoir perdu** : mandataire absent le jour J ; affiché à part (« 3 pouvoirs perdus : Sophie Marchal
  absente »), sans report automatique (à confirmer, §6) ;
- **quorum** = présents + représentés (pouvoirs valides), comparé au seuil réglé ; avant le jour J, la
  même formule avec « Je viens » à la place de « présent », marqué « prévision ».

## 4. Résultats et émargement

**Ce qu'on collecte (Seb, 20 octobre)** : les pouvoirs signés, un PDF par procuration, et un
récapitulatif (tableau à l'écran, PDF et Excel) : qui vient, qui ne vient pas, qui donne procuration à
qui, qui n'a pas répondu. Maquette : artboards « Côté bureau : les résultats » et « Le récapitulatif ».

- **Écran Résultats** : compteurs (viennent, procurations, ne viennent pas), quorum, filtres
  `Tous | Viennent | Procurations | Ne viennent pas | Sans réponse`, une ligne par membre avec un bouton
  **PDF** pour chaque procuration ; le filtre Procurations montre en tête **Pouvoirs reçus** (par
  mandataire : nombre, en blanc, noms des mandants). Bouton principal **Télécharger le récapitulatif** ;
  ⋯ › **Télécharger les pouvoirs** (tous les PDF en une archive) et **Exporter en Excel**.
- **Récapitulatif PDF** (A4, Chromium) : chiffres, quorum, liste de ceux qui viennent, tableau « qui représente qui » avec le
  nombre de voix, liste des absents sans procuration et des sans-réponse, date et heure de l'état.
- **Rangement automatique (Seb, 20 octobre : « dans Réunions / AG »)** : la tuile « Convoquer l'AG »
  crée le fichier dans **Docs › Privé › Saison en cours › Réunions › AGO du 21 novembre 2026** (ou
  **AGE du …**, Seb, 20 octobre).
  **L'appli cherche d'abord, et demande si elle n'est pas sûre** (Seb, 20 octobre) :
  - le dossier Réunions de la saison : nom comparé sans accents ni majuscules ni pluriel
    (« Réunions », « reunion », « Réunion du bureau » non) ; absent → créé ;
  - dedans, un dossier d'AG : nom contenant, sans accents ni majuscules, « AG », « AGO », « AGE » ou
    « assemblée générale » (Seb, 20 octobre), de la même sorte (ordinaire / extraordinaire, quand le nom
    le dit), sans convocation déjà diffusée.
    **Un seul** → on l'utilise ; **aucun** → « AGO du 21 novembre 2026 » est créé ; **plusieurs**, ou un
    dont la date ne colle pas → une question après « Quand ? » : « Où ranger la convocation ? »
    avec les dossiers trouvés et « Nouveau dossier AGO du 21 novembre 2026 » (proposé par défaut).
  L'assistant suit la même règle et pose la même question sur sa carte. Dans ce dossier : le fichier de convocation, un sous-dossier
  **Pouvoirs** (un PDF par procuration, enregistré à la signature, nommé « Pouvoir de Karim Benali à
  Martine Colin.pdf ») et le **récapitulatif** (remplacé à chaque téléchargement, une version par
  état). Mêmes droits que le dossier Privé de la saison (bureau, profs). Une procuration retirée garde
  son PDF, marqué « Retiré le … ». Si l'on déplace le fichier de convocation, les PDF suivent son
  dossier.

- **Formulaire de résultat par défaut** du modèle : Compteur (« 61 / 87 ont répondu »), un nouveau
  bloc de résultat **Quorum** (§3.5), un nouveau bloc **Pouvoirs reçus** (une ligne par mandataire,
  nombre de pouvoirs, noms des mandants au toucher), puis le Tableau des réponses (colonne « Procuration
  à … », signature visible au toucher).
- **Feuille d'émargement** (étape 2) : bouton dans Résultats, réservé à ceux qui peuvent modifier le
  fichier. Une ligne par membre convoqué, gros nom, une touche = présent (Annuler 10 s), recherche par
  nom ; en tête le quorum en direct. Un membre non convoqué qui arrive : « Ajouter une personne »
  (recherche dans les membres de l'école). Export PDF figé (Chromium, comme les autres PDF) : nom,
  présent / représenté par / absent, nombre de voix, signature des procurations ; il se range dans le
  dossier du fichier.

## 5. Données

- Étape 1 : **aucune table**. Le bloc est un nouveau type dans `app_content.py`
  (`QUESTION_TYPES`, contrôle dans `_check_value`) et le contrôle croisé (plafond, chaîne, convoqué)
  dans une fonction du module documents qui lit les autres réponses du même fichier.
- Étape 2 : une table **`doc_attendance`** (`id`, `org_id`, `node_id`, `person_id`, `present_at`,
  `marked_by`, `source` = `hand` ou `photo`) : l'émargement est saisi par le bureau, pas par le membre,
  il ne va donc pas dans sa réponse. Une seule liste des présents par AG, partagée avec le procès-verbal
  (`proces-verbal-ag.md`, qui la remplit depuis une photo de la feuille : `source = 'photo'`). Migration
  qui teste `has_table` (piège connu du `create_all`).
- Toutes les requêtes filtrent par `org_id`, avec un test d'étanchéité entre écoles.

## 6. À trancher par Seb

1. ~~Un bloc dans le fichier de base, plutôt qu'un écran à part~~ : **décidé par Seb le 20 octobre :
   oui, le fichier Questionner sert de socle, caché derrière le parcours** (tuile ou assistant : on ne
   voit ni la nature ni les quatre onglets, qui restent accessibles ensuite).
2. **Pouvoirs en blanc hors plafond de la présidence ?** Recommandation : **oui**.
3. **Pouvoir perdu quand le mandataire est absent**, sans report à la présidence ? Recommandation :
   **oui**, sauf si vos statuts disent autre chose.
4. **Plafond par défaut : 2 pouvoirs.** Recommandation : **2**, modifiable dans le bloc.

## 7. Étapes (une PR chacune, sur « vas-y »)

1. **Le bloc et la tuile.** Bloc Présence et procuration (écrans du membre, réglages, contrôles §3.4),
   boutons de réponse dans l'email, tuile « Convoquer l'AG » active avec son modèle, blocs de résultat
   Quorum (prévision) et Pouvoirs reçus, écran Résultats avec filtres, récapitulatif PDF et Excel,
   un PDF par pouvoir signé rangé dans « Pouvoirs ». *Vérification* : tests du contrôle (plafond, chaîne, soi-même,
   non convoqué, page publique refusée, étanchéité) ; essai sur téléphone avec « M'envoyer un essai ».
2. **La feuille d'émargement** : table `doc_attendance`, écran, quorum en direct, PDF.
3. **Les copies** (fait, §10) : email au mandataire, copie du pouvoir signé au mandant, relance
   aux non-répondants J-7 (`a-faire.md`, déjà prête à faire).
4. **L'Assistant IA, le reste** (fait, §11) : où en est le quorum, qui n'a pas répondu, relancer.

Les outils de l'assistant des étapes de la convocation (§1.4 : `convene_assembly`,
`validate_app_file`, `send_app_file`, `app_file_pdf`) viennent avec l'étape 1, à la demande de Seb
(20 octobre) : tout ce que fait l'écran doit marcher par l'assistant dès le départ.

## 8. Fait à l'étape 1 (PR #34), et écarts avec ce qui précède

Code : `backend/src/documents/assembly.py` (règles, décompte, PDF, convoquer),
`documents_contretemps/actions.py` (outils de l'assistant), écrans `ConvoquerAG.jsx`,
`app/AssemblySend.jsx`, bloc dans `app/Page.jsx`, `app/Editor.jsx`, `app/Results.jsx`. Tests :
`backend/tests/test_documents_assembly.py`.

Écarts, décidés en codant (à revoir avec Seb s'ils gênent) :

- **Lieu** : celui de la dernière AG de même sorte, sinon « [lieu à préciser] » dans le texte (le module
  documents ne connaît pas l'adresse de l'école).
- **Destinataires par défaut** : les convoqués de la dernière AG envoyée, sinon tous les membres de la
  saison (élèves, profs, admins : réglage `members` de `Documents`, posé par `app/main.py`).
- **Pouvoir en blanc** : un nom écrit dans le bloc, par défaut la personne qui convoque. Quand la
  colonne « Bureau » des administrateurs existera (`core.md` §6.4, PR #36), la présidence la remplacera.
- **Quorum** : aucun, un quart, un tiers ou la moitié des membres convoqués ; pas encore « un nombre ».
- **Pouvoir perdu** : seulement si le mandataire a répondu « Je ne viens pas » ; tant qu'il n'a pas
  répondu, le pouvoir est « en attente » (ni compté, ni perdu) dans la prévision.
- **À qui (Seb, 21 octobre)** : l'écran d'envoi propose **Tout le monde, Admins, Trésoriers, Professeurs,
  Élèves** (à cocher, pas les cours) et **Ajouter une personne** (recherche par nom) ; les convoqués de la
  dernière AG, proposés d'office, forment une seule étiquette retirable. « Recevront la convocation :
  N personnes » et un **œil** qui déplie la liste par ordre alphabétique, « Prénom Nom (adresse) ». Le lien
  « Changer » vers le Diffuser habituel est retiré. Groupes `role:tous` et `role:tresorier` dans
  l'annuaire (aussi pour partager un dossier).
- **Envoyer** : pas de question « Envoyer la convocation ? » ; le bouton lance un compte à rebours de
  10 s avec **Annuler** (« Annuler plutôt que confirmer »). Une fois envoyée, l'écran dit « Convocation
  envoyée à N membres » ; « Changer » ouvre le Diffuser habituel (ajouter des personnes).
- **Valider** passe directement en Officiel. Pour corriger ensuite : menu de l'état › Brouillon (admin),
  comme tout fichier ; « Faire relire » dans ⋯ n'est pas fait.
- **L'email** porte trois **vrais boutons** (Seb, 21 octobre ; avant, liens en clair), « Je viens », « Je donne procuration », « Je ne viens pas »
  (`…/r/<jeton>?c=proxy`) : la page s'ouvre avec ce choix déjà fait.
- **Mettre en ligne** (page publique) est refusé pour une convocation : chacun répond et signe par son
  lien personnel.
- **Résultats** : toucher un compteur (viennent, procurations, ne viennent pas, sans réponse) affiche
  la liste ; « Qui représente qui » ; boutons **Télécharger le récapitulatif** (PDF) et **Excel**. Les
  pouvoirs signés sont dans le dossier « Pouvoirs » (« Pouvoir d'Agathe Lambert à Capucine
  Martinez.pdf ») ; pas encore de bouton PDF par ligne ni d'archive de tous les pouvoirs. Le
  récapitulatif se télécharge, il n'est pas rangé dans le dossier.
- **PDF** faits par pymupdf, pas par Chromium (les tests tournent sans Chromium).
- **Assistant** : `convene_assembly`, `validate_app_file`, `send_app_file`, chacun sur une carte
  Faire / Annuler (les actions des modules n'ont que des cartes : préparer la convocation en a donc une
  aussi). Après « Faire », la convocation (ou le PV) **s'ouvre au-dessus de l'assistant** (Seb,
  21 octobre ; sur téléphone, le chat se ferme pour la montrer), et l'appli écrit dans le chat, sans appel
  payant : « Le texte vous va ? Dites-moi ce qu'il faut changer, ou modifiez-le vous-même ; quand il est
  bon, dites « valide » ou touchez Valider : rien ne part avant. » Le résultat de « Faire » porte le
  fichier à ouvrir (`ouvrir`, `assistant/actions.py`).
- **Aperçu modifiable** (Seb, 21 octobre, §1.3) : une convocation ou un PV tout juste préparés (tuile ou
  assistant) s'ouvrent sur l'**Aperçu** ; en Brouillon, on touche un titre ou un paragraphe et on écrit
  (enregistré en quittant le texte ; style gardé s'il était le même sur tout le bloc ; les questions et le
  bloc procuration se règlent dans Préparer). Bouton principal **Valider** dans l'Aperçu aussi. Plus de
  « Envoyer ma réponse (essai) » dans l'Aperçu : on essaie depuis Diffuser (« M'envoyer un essai »). La
  nature (Questionner) ne s'affiche pas sur une convocation ni sur un PV.
  `send_app_file` n'envoie qu'une convocation d'AG (aux destinataires par défaut). `app_file_pdf`
  passe à l'étape 4 (il faut un outil qui rend un lien, pas une carte).
- Pas encore fait : rappel si la convocation part moins de 15 jours avant ; « Changer » le pouvoir
  d'un membre par le bureau.

## 9. Fait à l'étape 2 (feuille d'émargement)

- Table `doc_attendance` (migration `e3f5a7b9c1d4`, crée la table seulement si absente) : une ligne par
  personne pointée présente, `source` = `hand` (écran) ou `photo` (procès-verbal). Décocher efface la
  ligne. Effacée avec le fichier (corbeille vidée).
- Décompte du jour (`assembly.sheet`) : présents pointés ; un pouvoir compte si son mandataire est
  pointé présent ou s'il est en blanc (porté par le bureau) ; il est perdu sinon ; il ne compte plus si
  le mandant est pointé présent (sa présence l'emporte). Voix = présents + pouvoirs qui comptent ;
  quorum sur le nombre de convoqués.
- Écran (Résultats › **Feuille d'émargement**, une fois la convocation envoyée) : chiffres et quorum
  en direct, recherche, une ligne par membre convoqué (touche = présent, Annuler 10 s), sous le nom :
  « Représenté par … », « Pouvoir à …, perdu s'il ne vient pas », pouvoirs portés ; **+ Ajouter une
  personne** (membre de l'école non convoqué). Bouton principal **Enregistrer la feuille (PDF)** : rangée
  à côté de la convocation (« Feuille d'émargement AGO du … .pdf »), nouvelle version à chaque fois.
- Réservé à ceux qui peuvent modifier la convocation, en Officiel seulement.
- Pas fait : signature des présents sur l'écran (la feuille papier reste), photo de la feuille (fil
  procès-verbal).

## 10. Fait à l'étape 3 (copies et relance)

- **Mail au mandataire** dès qu'un pouvoir nommé est signé : « Léon Perrin vous a donné procuration pour
  l'assemblée générale du 21 novembre 2026 », le pouvoir signé en pièce jointe (« Pouvoir.pdf »), et
  « sans vous, son pouvoir sera perdu ». Pas de mail pour un pouvoir en blanc (pas de personne nommée).
- **Copie au mandant** : « Votre procuration pour l'assemblée générale du … », qui le représente (ou
  « le bureau désignera »), le PDF joint et son lien pour changer d'avis.
- Les deux partent une seule fois par pouvoir signé : renvoyer la même réponse ne renvoie rien ; un
  nouveau mandataire reçoit son mail. L'ancien mandataire n'est pas prévenu qu'on lui retire un pouvoir.
- **Rappel sept jours avant**, automatique et une seule fois, aux convoqués sans réponse : le mail de la
  convocation avec « Rappel : » et ses trois liens. Seulement si la convocation est partie avant J-7.
  Fait par le processus de relance déjà en place (`app.relance_worker`), noté dans l'historique du
  fichier (« Rappel envoyé à N membres sans réponse ») ; l'écran Diffuser l'annonce.
- Le port `Mailer.send` du module accepte des pièces jointes (`attachments`), utilisées aussi par le
  procès-verbal.

## 11. Fait à l'étape 4 (l'assistant, le reste)

- **Où en est l'AG** : pas d'outil `assembly_status` à part. Quand l'assistant lit une convocation
  (`lire_fichier`), l'appli ajoute l'état des réponses en phrases, calculées par le code
  (`assembly.status_text`) : convoqués, réponses, qui vient, qui ne vient pas, sans réponse (noms),
  pouvoirs (qui porte quoi, perdus, en attente), voix prévues et quorum, puis le décompte du jour si la
  feuille d'émargement est commencée. Seulement pour qui peut voir Résultats (droit de modifier).
- **Relancer** : bouton **Relancer les N sans réponse** dans Résultats (avant le début de l'AG), le mail
  part après 10 s, **Annuler** d'ici là ; outil `remind_assembly(file)` sur une carte Faire / Annuler
  (« Relancer par email les 3 membres qui n'ont pas répondu à … (noms) »). Même fonction
  (`assembly.remind`) : le mail de la convocation précédé de « Rappel : l'assemblée a lieu bientôt, le …,
  et nous n'avons pas encore votre réponse. ». Noté dans l'historique ; le rappel automatique de J-7
  (§10) part quand même.
- **Télécharger** : l'assistant ne donne pas de lien (les fichiers ne s'ouvrent qu'avec la connexion).
  Outil `store_assembly_pdf(file, document)` sur une carte : range « Récapitulatif AGO du … .pdf » ou
  « Convocation AGO du … .pdf » dans le dossier de l'AG (nouvelle version s'il y est déjà). Pas
  d'archive des pouvoirs : ils sont déjà un par un dans « Pouvoirs », l'assistant le dit.
- Pas fait : l'outil générique `app_file_pdf` pour tout fichier de base (seule la convocation l'a).
