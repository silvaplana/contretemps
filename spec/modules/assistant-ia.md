# AppBase — Module `assistant-ia`

Version 0.1, 19 octobre 2026. Statut : **brouillon, en cours de validation avec Seb** (fil « Module :
Assistant IA » du projet). À ne pas confondre avec la messagerie instantanée (le chat entre membres).

Écrit comme un module AppBase : quand AppBase existera, ce fichier y part tel quel. Ce qui ne vaut que
pour Contretemps est marqué *(Contretemps)*.

---

## 1. Ce qui existe déjà

- Un seul assistant pour toute l'appli : un bouton dans l'en-tête, la même conversation dans tous les
  onglets. Chaque fichier de l'appli a aussi le sien (`spec/modules/fichier-de-base.md`).
- Ouvert aux administrateurs et aux professeurs, pas aux élèves. Chacun n'y voit et n'y fait que ce que
  ses écrans lui permettent déjà (« pas plus qu'en cliquant », Seb, 16 octobre).
- Coût affiché en euros, choix du modèle, plafond mensuel par école (jamais pour le Super User).
- Saisie façon appli Claude : + (photo, fichiers), micro pour dicter, flèche d'envoi.
- À l'ouverture, deux ou trois suggestions **propres à l'onglet ouvert** (Docs : le dossier ; Présence :
  les absences ; Administration : créer un cours…), plus « Fais une note de frais » partout. Créer un
  groupe n'est suggéré qu'aux administrateurs. Le fichier de l'appli a les siennes (Seb, 19 octobre).
- Code : `backend/src/assistant/`, `frontend/src/modules/documents/Assistant.jsx`, `AssistantGlobal.jsx`.

## 2. Règles

- **L'assistant ne change rien tout seul.** Toute action s'affiche sur une carte Faire / Annuler, et ne
  se fait qu'au clic. La carte dit en mots du métier ce qui va se passer (« Créer le cours « Salsa
  débutants », Mardi 19:00-20:00 »).
- **Les droits sont ceux de la personne**, vérifiés par le serveur au moment de proposer, avec les mêmes
  règles que les écrans.
- À l'écran, jamais le mot « IA » : c'est « l'assistant ».
- **Il répond court** (Seb, 19 octobre : « il parle trop, on croit qu'il n'a pas compris ») : une à
  trois phrases, en commençant par la réponse ou par ce qu'il a fait, sans reformuler la demande ni
  commenter ce qu'il fait pendant qu'il cherche (l'écran le montre déjà).
- **Il propose au lieu d'expliquer** (Seb, 19 octobre) : si un outil permet la suite, il la met sur une
  carte Faire / Annuler plutôt que de laisser des étapes à la personne. S'il doit demander, c'est une
  seule question fermée, avec deux ou trois choix à répondre d'un mot.

## 3. Les actions des modules (Seb, 19 octobre)

L'assistant ne connaît aucun module. **Chaque module déclare les actions qu'il lui ouvre** dans son
propre fichier `actions.py`, et l'appli les lui remet au démarrage. Une action devient un outil de
l'assistant.

### 3.1 La forme d'une action

```python
@dataclass(frozen=True)
class Action:
    name: str                    # nom de l'outil, ex. "create_group_chat"
    module: str                  # titre de la carte, ex. "Messagerie"
    description: str             # ce que l'assistant lit pour choisir l'action
    params: type[BaseModel]      # paramètres (Pydantic), vérifiés avant tout
    prepare: Callable            # (db, compte, org_id, params) -> Ligne
    admin_only: bool = True      # outil montré seulement aux administrateurs
```

- `prepare` vérifie les droits et les données, puis rend une `Ligne` : le libellé de la carte et la
  fonction à lancer au clic. Il ne change rien. Un refus (droits, donnée introuvable) revient à
  l'assistant avec sa raison, pour qu'il l'explique ou corrige.
- La fonction lancée au clic est **celle que les écrans utilisent déjà** : mêmes vérifications, et les
  écrans ouverts se mettent à jour pareil.
- Les paramètres désignent les choses comme l'assistant les connaît : un numéro lu avec les outils de
  lecture, ou un nom quand aucun outil ne donne le numéro (un groupe de la messagerie, une personne pour
  une note de frais). Un nom introuvable est refusé avec la liste des noms possibles.
- Code : `backend/src/assistant/actions.py` (la forme et la carte), `<module>/actions.py` (les actions).
  Quand le module a besoin de l'appli hôte pour agir, ses actions vont dans `<module>_contretemps/`.

### 3.2 Le ramassage

Chaque module donne ses actions dans sa déclaration (`module.py`, champ `actions`, voir
`spec/core.md` §9 bis), et `app/main.py` *(Contretemps)* les remet à l'assistant dans l'ordre de
`app/modules.py`, après celles du socle de Contretemps (école, administrateurs, élèves, profs,
cours), qui y restent listées une par ligne *(23 octobre 2026)*.

### 3.3 Les premières actions

| Module | Action | Qui |
|---|---|---|
| Messagerie | Créer un groupe (personnes et cours), le renommer, le supprimer, ajouter ou retirer des membres (aussi dans le groupe d'un cours). Les groupes automatiques des cours ne se suppriment pas. Le Super User, qui n'a pas de fiche d'école, s'ajoute comme dans l'écran Nouveau groupe. | Administrateurs |
| Cours *(Contretemps)* | Créer un cours, le supprimer. Le modifier passe déjà par la carte des modifications de données. | Administrateurs |
| École | Modifier les coordonnées d'Admin > École (nom, adresse, SIRET, IBAN, emails). | Administrateurs |
| Rôles | Nommer ou retirer un administrateur, un trésorier, un administrateur principal ; créer une personne qui n'est qu'administrateur. Comme le tableau des administrateurs : jamais sur sa propre ligne, sauf la case Trésorier. | **Administrateurs principaux** et Super User (Seb, 19 octobre) |
| Professeurs | Créer, modifier, supprimer un professeur. L'affecter à un cours passe par la carte des modifications de données. | Administrateurs |
| Élèves | Supprimer un élève. Le créer et le modifier passent par la carte des modifications de données. | Administrateurs |
| Chorégraphies *(Contretemps)* | Supprimer une chorégraphie avec ses vidéos. La créer et la modifier passent par la carte des modifications de données. | Administrateurs |
| Notes de frais | Faire une note (une ou plusieurs dépenses) et l'envoyer aux trésoriers, pour soi ou, si on est trésorier, pour quelqu'un d'autre. Sans RIB enregistré, seulement en don. Les justificatifs s'ajoutent ensuite dans l'appli. | Tous ceux qui ont l'assistant |
| Financier | Produire le bilan, le PowerPoint de l'AG (à partir du bilan et d'un PowerPoint modèle) ou un prévisionnel d'une saison (`financier.md` §7). | Trésoriers et Super User |

En lecture (Seb, 19 octobre : « tout ce que contient l'onglet Admin »), réservé aux administrateurs :
toutes les personnes avec leurs rôles, Super Users compris, filtrables par rôle ; les coordonnées de
l'école (de l'IBAN, l'assistant ne voit que les 4 derniers chiffres) ; les groupes de la messagerie et
leurs membres. Le reste d'Admin (élèves, profs, cours, chorégraphies, saisons) se lisait déjà.

### 3.4 Plus tard

- Ajouter une vidéo à une chorégraphie : le fichier passe aujourd'hui par l'écran de la chorégraphie
  (envoi par morceaux, compression) ; les fichiers joints à l'assistant sont limités à 20 Mo et lus par
  lui. À décider avec Seb.
- Admin > École encore sans action : saisons, personnalisation (logo, couleurs), sauvegardes.

- Déplacer dans leurs modules les outils écrits aujourd'hui dans `assistant/` : documents, données de
  l'école en lecture, modifications de données (`donnees.py`, `modifications.py`).

## 4. Dictée

- Pendant la dictée (comme l'appli Claude, Seb 19 octobre) : sous le texte qui s'écrit, une barre avec ✕
  (annule et remet le texte d'avant), un fil de points qui s'agite quand une voix est entendue, ■ (arrête,
  garde le texte) et ↑ (envoie). Le fil suit la voix détectée, pas le volume exact : mesurer le micro en
  même temps que la reconnaissance la gênerait sur Android.
- Le micro utilise la reconnaissance vocale du navigateur, gratuite (absente de Firefox : pas de micro).
- Sur Chrome Android, les morceaux entendus reprennent chacun le précédent : le texte est reconstruit à
  chaque fois, sans répéter les mots (correctif du 18 octobre, `Dictee.js`).
- Chrome Android arrête l'écoute après chaque phrase : la dictée écoute une phrase à la fois et se relance
  aussitôt, jusqu'à ce qu'on touche le micro ou après un long silence (deux écoutes sans rien entendre,
  une dizaine de secondes). Correctif du 19 octobre.

## 5. Pistes (non décidées)

- **Serveur MCP** : les mêmes actions ouvertes à Claude ou ChatGPT, où l'on ajoute l'appli comme
  connecteur. À régler : connexion avec le compte de l'appli (droits de la personne), confirmation faite
  par Claude ou ChatGPT, coût payé par l'abonnement de la personne.
- **Démarrage guidé** : un mode d'emploi court (saison, cours, élèves, profs, paiements), plus une action
  « où en est l'école » (« 0 cours, HelloAsso pas branché »), pour que l'assistant ou Claude propose
  l'étape suivante. Le même texte sert à l'assistant, au serveur MCP et au site public.
- Conversations gardées en base (aujourd'hui en mémoire du serveur, voir `spec/a-faire.md`).
