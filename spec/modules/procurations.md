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

1. **Qui vous représente ?** La liste des membres convoqués (nom seulement), plus en tête
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

**Deux portes, même résultat (Seb, 20 octobre)** : la tuile **Docs › + › Convoquer l'AG**, ou
l'**Assistant IA** : « convoque l'AG le 21 novembre à 14 h à la salle des fêtes ». L'assistant crée le
même fichier (même dossier, §4), le remplit avec la date, le lieu et l'ordre du jour (repris de la
dernière AG s'il y en a une), puis montre une carte **Faire / Annuler** : « Envoyer la convocation à
87 membres ? ». Rien ne part sans ce toucher ; l'assistant ne signe jamais à la place d'un membre.

Dans Docs, **+ › Questionner › Convoquer l'AG** (tuile aujourd'hui « bientôt ») : un fichier de base
déjà rempli (convocation, bloc **Présence et procuration**), ouvert sur Préparer. Il corrige la date,
le lieu et l'ordre du jour dans le texte, règle le bloc (§3.1), passe le fichier en Officiel, puis
**Diffuser › Des personnes choisies** (tous les membres à convoquer) › **Envoyer**. Tout ça existe déjà
dans le fichier de base, sauf le bloc.

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
  `marked_by`) : l'émargement est saisi par le bureau, pas par le membre, il ne va donc pas dans sa
  réponse. Migration qui teste `has_table` (piège connu du `create_all`).
- Toutes les requêtes filtrent par `org_id`, avec un test d'étanchéité entre écoles.

## 6. À trancher par Seb

1. **Un bloc dans le fichier de base, plutôt qu'un écran à part.** Recommandation : **oui** (§2.1).
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
3. **Les copies** : email au mandataire, copie du pouvoir signé au mandant, relance
   aux non-répondants J-7 (`a-faire.md`, déjà prête à faire).
4. **L'Assistant IA, le reste** : où en est le quorum, qui n'a pas répondu, relancer.

L'action **Convoquer l'AG** de l'assistant (`documents/actions.py`, §1.3) vient avec l'étape 1, à la
demande de Seb (20 octobre) : l'outil doit marcher par l'assistant dès le départ.
