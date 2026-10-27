# AppBase — Module `video-combats`

Version 0.2, 27 octobre 2026. Statut : **brouillon** (captation et traitement discutés dans le projet
Claude « sambo-admin » ; écrans validés par Seb sur maquette le 27 octobre, fil « Module : Vidéos de
sparring » d'AppBase). Rien n'est codé, et **rien ne se code tant que le refactor en cours n'est pas
fini** (Seb, 27 octobre).

Maquette validée : [`spec/maquettes/sparring.html`](../maquettes/sparring.html) (tout est cliquable).

Écrit comme un module AppBase. Premier usage visé : un club de sambo (La Ciotat). Ce qui ne vaut que
pour ce club est marqué *(sambo)*.

---

## 1. Objectif

Un téléphone filme le cours, et l'appli en tire automatiquement **un clip par combat**, recadré comme
par un cadreur et rangé au nom des deux combattants. Chaque membre retrouve ses combats dans l'appli.

- **Pas de direct** : tout se traite après la séance, ce qui permet de cadrer en connaissant la suite.
- **Aucun produit existant ne couvre le besoin** : Hudl, Pixellot, Veo ou XbotGo visent le foot ou le
  basket, sans découpe par combat ni noms.
- **Priorité au rendu naturel** : pas d'effet caméra de surveillance. La qualité d'image passe après.
- **Module activable par organisation**, comme les autres modules : éteint dans Contretemps au début,
  prévu pour un club de combat (Fight Lab).
- **Le combat d'abord** (Seb, 27 octobre) : on conçoit et on met au point le module pour un club de
  combat, comme un prototype. La danse viendra ensuite (§6.6) ; d'ici là, on ne garde que ce qui ne
  coûte rien et ne bloque pas la danse : un clip a une **liste de participants** (1 à n), pas deux
  noms fixes.

## 2. Acteurs, séance et cas d'utilisation

### 2.1 Acteurs

| Acteur | Qui | Ce qu'il fait |
|---|---|---|
| **Coach** | Un admin ou un prof de l'organisation, depuis sa PWA (Android ou iPhone) | Lance et termine la séance, corrige les clips |
| **Combattant** | Un membre présent au cours | S'enregistre, signale le début et la fin de ses combats par des gestes |
| **Membre** | Tout membre, depuis sa PWA | Regarde ses clips, donne ou retire son accord pour être filmé |
| **Installateur** | Un admin, sur place | Fixe le téléphone, met l'enregistreur en attente, choisit le mode |
| **Enregistreur** | Le téléphone fixé au mur et sa petite appli Android | Filme, envoie la vidéo, donne son état |
| **Serveur** | Le backend et son worker de nuit | Reçoit la vidéo, la découpe en clips, les nomme et les range |

### 2.2 Organisation d'une séance (mode connecté)

| Moment | Acteur | Action | Réponse du système |
|---|---|---|---|
| Avant le cours | Coach | Ouvre Sparring et regarde le bouton caméra | Pastille verte « Prête » ; touchée, elle montre batterie et place restante |
| Début du cours | Coach | Appuie sur « Démarrer la séance » | L'enregistreur filme ; la PWA affiche « Enregistrement en cours » |
| Échauffement | Chaque combattant | Passe 2 s sur le repère au sol, face à la caméra, et dit son prénom | Rien à l'écran : l'enregistrement est repéré au traitement |
| Avant un combat | Les deux combattants | Entrent dans la zone, font le Y pendant 2 s | Rien à l'écran : le début est repéré au traitement |
| Fin d'un combat | Les deux combattants | Font le X, ou sortent de la zone | Rien à l'écran : la fin est repérée au traitement |
| Changement de tenue | Le combattant | Repasse sur le repère | Sa nouvelle tenue remplace l'ancienne pour la suite |
| Fin du cours | Coach | Appuie sur « Fin de séance » | L'enregistreur s'arrête, envoie la vidéo, puis se remet en attente |
| La nuit | Serveur | Traite la vidéo | Clips créés, nommés, rangés ; vidéo brute supprimée après validation |
| Le lendemain | Coach | Ouvre l'onglet « À vérifier » | Corrige les noms inversés ou manquants |
| Le lendemain | Membre | Ouvre « Mes combats » | Voit ses clips de la séance |

En mode autonome, les lignes « Démarrer » et « Fin de séance » sont remplacées par les créneaux du
planning, et l'envoi attend la sortie du mode avion (UC 3).

### 2.3 Cas d'utilisation

**UC 1 — Installer l'enregistreur** · Installateur

1. Fixe le téléphone, le branche sur secteur, installe l'APK.
2. Se connecte avec un compte admin et choisit l'organisation.
3. Règle Samsung : batterie « Non restreinte », « Protéger la batterie ».
4. Choisit le mode (connecté par défaut) et appuie sur « Mettre en attente ».
5. La PWA des coachs affiche l'enregistreur comme prêt.

Variante : après une coupure de courant, la PWA affiche « caméra hors service » ; un installateur
rouvre l'enregistreur (étape 4).

**UC 2 — Filmer une séance (mode connecté)** · Coach, Enregistreur

1. Le coach touche le bouton caméra de Sparring, puis « Démarrer la séance » (§6.3).
2. Le serveur prévient l'enregistreur, qui filme et confirme.
3. Le coach appuie sur « Fin de séance » ; l'enregistreur s'arrête et envoie la vidéo.

Erreurs : enregistreur injoignable → la PWA le dit et propose de réessayer ; un coach oublie « Fin »
→ arrêt automatique à la fin du créneau prévu, plus 30 min.

**UC 3 — Filmer une séance (mode autonome)** · Installateur, Enregistreur

1. Avant de passer en mode avion, l'installateur appuie sur « Passer en autonome » : l'enregistreur
   récupère les créneaux des cours.
2. Il filme seul pendant chaque créneau.
3. À la sortie du mode avion, il envoie les vidéos en attente.

Variante : démarrage et arrêt par un appui à l'écran.

**UC 4 — S'enregistrer en début de séance** · Combattant

1. Le combattant se place sur le repère, face à la caméra, 2 s, et dit son prénom.
2. Au traitement, le prénom est relié à un membre et sa tenue est mémorisée.

Erreurs : prénom inconnu ou ambigu → ses combats sont « à vérifier ».

**UC 5 — Signaler un combat** · Combattants

1. Les deux entrent dans la zone et font le Y 2 s.
2. Ils combattent, puis font le X (ou quittent la zone).

Variantes : un combat sans Y devient un « combat sans nom » ; un Y sans X se termine quand la zone
se vide.

**UC 6 — Traiter la séance** · Serveur

1. Repère les enregistrements, les Y et les X.
2. Identifie les deux combattants de chaque combat par leur tenue.
3. Découpe, recadre, encode chaque clip en 720p, le range au nom des deux combattants.
4. Écarte les combats d'un membre qui n'a pas donné son accord.

**UC 7 — Vérifier et corriger les clips** · Coach

1. Ouvre l'onglet « À vérifier » (§6.4).
2. Pour chaque clip : valide (« C'est bon »), inverse les deux noms, choisit un nom manquant parmi les
   présents ou supprime le clip (Annuler 10 s).

**UC 8 — Regarder ses combats** · Membre

1. Ouvre « Mes combats » (§6.2) : ses clips, du plus récent au plus ancien, avec l'adversaire et la date.
2. Regarde un clip (§6.5).

**UC 9 — Donner ou retirer son accord** · Membre (ou parent pour un mineur)

1. Coche ou décoche « J'accepte d'être filmé ».
2. Sans accord, ses combats ne sont plus gardés ; le retrait supprime aussi ses clips existants.

**UC 10 — Surveiller l'enregistreur** · Coach

1. Voit à tout moment, par le bouton caméra de Sparring (§6.3) : prête, filme, hors service ; batterie ;
   place restante ; dernier envoi.

## 3. Installation et matériel *(sambo)*

On filme une zone de 4 × 5 m, prise dans le tapis de 4 × 20 m, plutôt que toute la salle.

| Élément | Choix |
|---|---|
| Zone filmée | Environ 4 × 5 m, marquée au sol (scotch ou tatamis d'une autre couleur) |
| Position de la caméra | Côté long du tapis, côté mur, à 4–5 m du centre de la zone |
| Hauteur et angle | 3 à 3,5 m de haut, plongée d'environ 30°. Jamais à la verticale, ni au bout du tapis |
| Caméra | Samsung S24 de Seb pour le prototype. Plus tard, un vieux téléphone ou une caméra d'action. Pas de 360 |
| Réglages | 1080p, 25 ou 30 i/s (secteur 50 Hz), HEVC, exposition verrouillée, grand angle 0,6× si besoin |
| Fixation | Pied d'éclairage de 3 m pour tester, puis pince sur espalier ou support mural à rotule (chevilles placo) |
| Alimentation | Batterie externe ou secteur, câble USB de 3 m, dragonne de sécurité |
| Lumière | Tout l'éclairage allumé. Projecteurs LED si l'image est bruitée |

Volumes : environ 3 à 4 Go par heure en 1080p HEVC. Les clips finaux sont en 720p.

## 4. Captation

**Prototype** : on filme avec l'appareil photo du téléphone, pas avec l'appli web, car un navigateur
risque de couper un enregistrement d'une heure. Un mode Samsung « Modes et routines » active le mode
avion, met la luminosité au minimum et ouvre l'appareil photo. La vidéo est envoyée à la main dans
l'appli, par l'envoi par blocs du module `videos` (SPEC.md §6.8).

**Ensuite, une petite appli Android à part, l'« enregistreur »** : l'appli reste la PWA pour tout le
monde. L'enregistreur n'est installé que sur le téléphone qui filme. C'est une appli Kotlin minuscule
(CameraX), indépendante du frontend, distribuée en APK (choix confirmé par Seb le 27 octobre). On n'utilise pas Capacitor, qui obligerait à
maintenir un build Android de toute l'appli pour une seule fonction.

- **Téléphone dédié, fixé au mur et branché en permanence.** Une seule caméra pour l'instant ; s'il y
  en a plusieurs un jour, on choisira laquelle démarrer.
- **Mise en attente, une fois** : on ouvre l'enregistreur à l'installation. Il lance un service de
  premier plan « en attente » (écran éteint, caméra fermée). Android interdit d'allumer la caméra
  depuis une appli qui n'était pas déjà active : ce lancement à la main est donc nécessaire, ensuite
  on l'oublie.
- **Démarrage à distance** : n'importe quel admin ou prof appuie sur « Démarrer la séance » dans sa
  PWA, iPhone compris. Le serveur prévient l'enregistreur (push ou connexion maintenue), qui allume
  la caméra et active « Ne pas déranger » si l'autorisation est donnée. « Fin de séance » arrête et
  lance l'envoi dès qu'il y a du Wi-Fi. Pas de Bluetooth.
- **État visible dans la PWA** : bouton caméra de Sparring (§6.3), avec batterie et place restante.
- **Après une coupure ou un redémarrage**, quelqu'un rouvre l'enregistreur une fois ; la PWA affiche
  « caméra hors service » en attendant.
- **Réglages Samsung** : batterie « Non restreinte » pour l'appli, « Protéger la batterie » (charge
  limitée à environ 85 %) pour un téléphone toujours branché.
- **Deux modes, au choix dans l'enregistreur** :
    - **Connecté** (par défaut) : Wi-Fi seul, données mobiles coupées, « Ne pas déranger », rien d'autre
      qu'un lien très léger avec le serveur. Démarrage à distance, voyant d'état et envoi automatique.
    - **Autonome** : mode avion, aucune communication. L'enregistreur filme seul pendant les créneaux
      des cours, récupérés au moment du passage en autonome, ou sur un appui à l'écran. L'envoi se fait
      quand on sort du mode avion. L'appli ne peut pas activer le mode avion elle-même (Android
      l'interdit) : on le fait à la main ou avec une routine Samsung.
- C'est un enregistreur générique, réutilisable ailleurs (par exemple une appli de montagne).

## 5. Traitement

Le serveur traite la vidéo de la séance en quatre passes, de nuit. Il sait exploiter le fait de
connaître toute la vidéo à l'avance.

1. **Enregistrements** : il repère les passages sur le repère au sol, transcrit le prénom dit et le
   relie au bon membre. Il en tire une « empreinte » de tenue : couleurs du t-shirt et du short,
   silhouette.
2. **Signaux** : la détection de posture repère les Y tenus 2 secondes par deux personnes dans la zone
   (début) et les X (fin). Le combat se termine aussi si la zone se vide. Un combat repéré sans Y
   devient un « combat sans nom ».
3. **Identification** : il suit chaque personne image par image, et compare les deux combattants aux
   empreintes du jour. Si la confiance est faible, comme avec deux t-shirts noirs unis, le clip est
   marqué « à vérifier ». Pas de reconnaissance faciale.
4. **Découpe et recadrage** : un cadre virtuel englobe les deux combattants avec une marge. Sa
   trajectoire est calculée sur tout le combat d'un coup :
    - il bouge seulement quand les combattants sortent d'une zone centrale, avec accélérations et
      freinages doux ;
    - il anticipe, en commençant à glisser une demi-seconde avant une projection ;
    - il zoome légèrement quand le combat passe au sol ;
    - quand quelqu'un passe devant, il trace un mouvement fluide entre la dernière position connue et
      la suivante ;
    - un masquage de plus de 5 secondes peut être coupé du clip.

**Plus de deux personnes.** La détection de posture voit tout le monde : le clip garde tous ceux qui
tiennent le Y ensemble (1 à n) ; le cadre les englobe tous ; à plus de deux, le combat se termine quand
la majorité fait le X, ou quand la zone se vide. Pour le combat, on met au point le cas à deux.

Le clip est ensuite encodé en 720p et rangé comme une vidéo du module `videos`. La vidéo brute est
supprimée une fois le traitement validé.

## 6. Écrans, rôles, droit à l'image

Les écrans suivent exactement la maquette validée le 27 octobre
([`spec/maquettes/sparring.html`](../maquettes/sparring.html)). Règles de l'appli : texte ≥ 17 px,
touches ≥ 48 px, un bouton principal par écran, Annuler 10 s plutôt que confirmer, retour par la
flèche ←.

### 6.1 Place dans l'appli et nom

- **Un bouton de la barre du bas**, nommé **« Sparring »** dans un club de combat. Le nom à l'écran
  dépend de l'organisation ; le nom générique du module est proposé : « Clips de séance » (§10).
- **Sparring est un espace de consultation.** La seule commande, celle de la caméra, se cache derrière
  un bouton (§6.3).
- **Membre** : un seul écran, « Mes combats », sans onglets au-dessus.
- **Coach** (admin ou prof) : trois onglets, **Mes combats | Séances | À vérifier**. « À vérifier »
  porte le nombre de clips à vérifier dans une pastille rouge.
- Le module s'éteint par organisation (Admin > École > Personnalisation de l'application >
  Fonctionnalités) : éteint = bouton caché, routes « introuvable » (spec/core.md §9 bis).

### 6.2 Mes combats *(tous)*

- Les clips où la personne apparaît, du plus récent au plus ancien, regroupés par séance (« JEU. 23 OCT.
  · ADULTES »).
- Chaque ligne : vignette avec la durée, « contre Karim B. », « Combat 3 · 2 min 20 ».
- Un clip « à vérifier » n'y apparaît qu'une fois validé par un coach : jamais un mauvais nom sous les
  yeux d'un membre.
- Vide : « Vos combats filmés apparaîtront ici le lendemain de la séance. »
- Sans accord pour être filmé (§6.8) : « Vos combats ne sont pas filmés », et le lien vers la case du
  profil.

### 6.3 Séances et commande de la caméra *(coachs)*

**Les séances, en cartes.** Une carte par séance, de la plus récente à la plus ancienne :

- en haut, un aperçu des trois premiers combats (une grande vignette, deux petites) ;
- dessous, « Jeu. 23 oct. · Adultes · 19 h », puis l'état : « 4 combats » et « 1 à vérifier » (jaune)
  ou « Vérifié » (vert) ;
- une séance pas encore découpée a une carte rayée grise : « La vidéo arrive… » avec « Envoi 64 % » et
  une barre, ou « Découpe cette nuit » avec « Clips prêts demain matin ». Elle ne s'ouvre pas.

Une carte ouverte est le **dossier de la séance** : en tête, « Présents reconnus : Seb R., Karim B.… »
(ceux passés sur le repère au sol), puis ses clips dans l'ordre. Chaque clip s'appelle
**« Seb R. contre Karim B. »** ; si la même paire combat encore dans la séance, le suivant s'appelle
« Seb R. contre Karim B. 2 », etc. Un combat sans Y s'appelle « Combat sans nom ». Un clip à vérifier
porte la pastille « À vérifier ».

Le bouton **+** en bas à droite envoie à la main la vidéo d'une séance filmée avec l'appareil photo
(étape V1, avant l'enregistreur), par l'envoi par blocs du module `videos`.

**Le bouton caméra.** En haut à droite de Sparring, pour les coachs seulement (y compris sur
« Mes combats » et « À vérifier ») : une pastille en couleur avec une caméra et un mot.

| État | Pastille |
|---|---|
| Prête | verte, « Prête » |
| Filme | rouge, « Filme », qui pulse doucement |
| Hors service | grise, « Hors service » |

Le toucher fait **descendre le panneau de commande** depuis le haut, par-dessus l'écran ; « Fermer »
(ou un appui à côté) le remonte. Le panneau montre :

- Prête : « Caméra prête », « Batterie 86 % · 41 Go libres · dernier envoi jeu. 23 oct. », bouton
  principal **« Démarrer la séance »** ;
- Filme : « Enregistrement en cours », « Adultes · 19 h · 00:12:34 · batterie 84 % », bouton principal
  **« Fin de séance »** ;
- Hors service : « Coupure ou redémarrage du téléphone. Rouvrez l'enregistreur sur le téléphone de la
  salle. », sans bouton.

Pendant le film, une **bande rouge** « ● Enregistrement en cours · 00:12:34 — Ouvrir » reste sous les
onglets, et rouvre le panneau. Après « Fin de séance », la séance apparaît en tête de liste, en envoi.

### 6.4 À vérifier *(coachs)*

Les clips dont l'appli n'est pas sûre, **un par un**, en gros :

- « 1 sur 3 · Jeu. 23 oct. · combat 2 » ;
- la vidéo, avec les marques **R** (rouge) et **B** (bleu) au-dessus des deux combattants ;
- la raison en clair, sur fond jaune : « Deux t-shirts noirs unis : tenues trop proches. »,
  « Combattants emmêlés au sol : les noms ont pu s'inverser. », « Pas de Y au début : personne n'a été
  reconnu. » ;
- deux lignes « ● Rouge Karim B. › » et « ● Bleu Malik A. › » ; toucher une ligne ouvre la liste des
  présents de la séance, plus « Un autre membre… » ; un nom manquant s'affiche « Choisir… » en rouge ;
- **« Inverser »** (secondaire) et **« C'est bon »** (principal, inactif tant qu'il manque un nom) :
  « C'est bon » valide le clip, qui part dans « Mes combats » des deux, et passe au suivant ;
- « Supprimer ce clip », en lien discret, avec Annuler 10 s.

Vide : « Tout est vérifié. Les clips sont dans « Mes combats » de chaque membre. »

Rouge = celui de gauche au début du combat, Bleu = l'autre, comme les coins d'un combat de sambo. Les
couleurs ne servent qu'à deux.

### 6.5 Lecture d'un clip *(tous)*

- Plein écran, flèche ← et le nom du clip en titre, ⋯ à droite.
- La vidéo, lue par le lecteur du module `videos` (`VideoThumb`, plein écran compris).
- Dessous : les deux noms avec leur pastille rouge et bleue, puis « Mar. 21 oct. · Adultes · 19 h ·
  combat 1 ».
- Puis « Autres combats de la séance » (coach) ou « Vos autres combats ce jour-là » (membre).
- ⋯ pour tous (Seb, 27 octobre : chacun garde et diffuse ses combats) : « Télécharger » (le clip dans
  le téléphone), « Partager… » (le menu Partager du téléphone avec le fichier : WhatsApp, mail…, par
  le partage web de Chrome) et « Envoyer dans la messagerie… » ; pour un coach aussi « Inverser les noms » (Annuler
  10 s), « Changer un nom », « Supprimer ce clip » (Annuler 10 s).

### 6.6 Plus tard

Hors du premier code, notés pour ne pas les perdre (Seb, 27 octobre).

- **Place disque** : un clip s'efface seul après quelques jours (7 proposé, réglable), sauf ceux qu'on
  coche « Garder » ; chacun peut garder un nombre limité de clips. Le téléchargement (§6.5), lui, est
  là dès le début.
- **Docs** (Seb, 27 octobre) : les mêmes vidéos se voient aussi dans Docs, dans l'espace de la saison :
  un dossier **Sparring**, avec un sous-dossier par séance (« Jeu. 23 oct. · Adultes ») et ses clips
  nommés comme dans Sparring. Ce sont les mêmes fichiers, sans copie : effacer un clip d'un côté
  l'efface de l'autre. Le dossier suit les droits de l'espace de la saison (Privé : admins et profs).
- **Diffuser** : envoyer une séance ou un clip à d'autres.
- **La danse** : dans Contretemps, pas de bouton dans la barre du bas, mais un onglet **« Passages »**
  dans Chorégraphies (**Chorégraphies | Passages**), rangé par `session_clips_contretemps/`. Un
  passage regroupe de 1 à n danseurs ; leurs noms viennent des élèves de la chorégraphie (les costumes
  sont souvent identiques : pas de reconnaissance par la tenue).

### 6.7 Données

Le module est générique : il ne connaît ni la danse ni le combat. Comme une chorégraphie, il
référence ses vidéos dans le module `videos`, jamais l'inverse. Tout est filtré par organisation.

| Table | Rôle | Colonnes principales |
|---|---|---|
| `sc_sessions` | une séance filmée | `id`, `org_id`, `title` (« Adultes · 19 h », le cours choisi ou tapé), `held_on` (date), `raw_video_id` (vidéo brute dans `videos`, vide une fois effacée), `status` (`processing` / `ready` ; « en cours d'envoi » se lit sur la vidéo brute), `created_by`, `created_at` |
| `sc_clips` | un clip | `id`, `session_id`, `video_id` (le clip dans `videos`, unique), `position` (combat 1, 2…), `to_check` (booléen), `check_reason` (texte) |
| `sc_participants` | qui est dans un clip | `clip_id`, `slot` (0 = Rouge, 1 = Bleu à deux ; ordre simple au-delà), `person_id` (la personne, vide = pas encore nommée) |
| `sc_attendees` | présents reconnus à une séance | `session_id`, `person_id` |
| `sc_recorders` | le téléphone qui filme *(étape 3, pas encore créée)* | `id`, `org_id`, `state` (`ready` / `recording` / `offline`), `battery_percent`, `free_bytes`, `last_seen_at`, `last_upload_at` |

`person_id` est la personne, stable d'une saison à l'autre : dans Contretemps, c'est la première
fiche `comptes` de la chaîne des saisons (comme les documents), fournie par l'adaptateur
`session_clips_contretemps/`. Un clip créé avec un nom manquant ou un motif (`check_reason`) part
dans « À vérifier » ; tant qu'il y est, seuls les coachs le voient. Supprimer un clip efface sa
vidéo ; effacer une vidéo depuis « Usage vidéo » retire aussi son clip.

Le nom d'un clip (« Seb R. contre Karim B. 2 ») n'est pas stocké : il se calcule à l'affichage, pour
suivre les corrections. Le consentement (§6.8) est une case de la fiche membre.

### 6.8 Rôles et droit à l'image

| Rôle | Ce qu'il fait |
|---|---|
| Admin ou prof | Commande la caméra. Voit toutes les séances et tous les clips. Corrige et supprime |
| Membre | Voit « Mes combats », c'est-à-dire les clips validés où il apparaît |
| Téléphone caméra | Filme et envoie la vidéo |

**Droit à l'image** :

- On recueille un consentement « J'accepte d'être filmé » à l'adhésion ou dans l'appli (profil). Pour
  les mineurs, ce sont les parents qui donnent leur accord.
- Les combats impliquant quelqu'un qui a refusé ne sont pas gardés ; le retrait de l'accord efface
  aussi ses clips.
- Pas de reconnaissance faciale, pour rester hors des données biométriques.
- Les vidéos restent sur notre serveur, sans API cloud.

## 7. Pile technique

Tout est open source et tourne sur le VPS. Aucune API payante.

| Besoin | Outil |
|---|---|
| Extraire le son, découper, encoder | ffmpeg |
| Transcrire les prénoms | faster-whisper (local, français) |
| Relier un prénom à un membre | rapidfuzz |
| Détecter les personnes et les postures (Y, X) | Ultralytics YOLO, version pose (licence AGPL : OK en interne, à revoir si on distribue) |
| Suivre les personnes | ByteTrack, intégré à YOLO |
| Empreinte de tenue | Modèle de ré-identification (OSNet) et histogrammes de couleur OpenCV |
| Trajectoire du cadre | NumPy, SciPy |
| Recadrage | OpenCV et ffmpeg |
| Traitement de nuit | Un worker, comme les autres workers du Docker Compose |
| Stockage et envoi | Module `videos` existant (SPEC.md §6.8) |
| Enregistrement de séance | Petite appli Android à part (Kotlin, CameraX, service de premier plan), lancée par la PWA |

Le code suit les conventions du dépôt : `backend/src/session_clips/` et
`frontend/src/modules/session-clips/`, tables préfixées `sc_` (§6.7). Nom à valider avec Seb.

## 8. Étapes

Chaque étape est utilisable seule. On s'arrête dès qu'une étape ne vaut plus l'effort.

1. **V0, vidéo de test** : 5 à 10 minutes au S24, depuis l'emplacement prévu, avec un ou deux combats,
   des Y et des X. Sans elle, on code à l'aveugle.
2. **V1, clips en plan fixe** : envoi via le module `videos`, détection des Y et des X, découpe, noms
   choisis dans l'appli. *Facile.*
3. **V2, recadrage** : le cadre virtuel lissé. *Moyen, il faudra régler avec de vraies vidéos.*
4. **V3, noms automatiques** : enregistrement en début de séance et ré-identification par la tenue,
   avec le bouton « inverser » et la file « à vérifier ». *Expérimental.* En bonus, la liste des
   présents.
5. **V4, enregistreur Android** : démarrage depuis la PWA, pilotage à distance, envoi automatique.

Découpage du code en trois étapes (accord Seb du 27/10) :

1. **Fait (PR #79)** : tables, onglet Sparring (Mes combats, Séances, À vérifier, lecture,
   Télécharger, Partager), envoi d'une séance à la main par le bouton + (envoi par blocs et
   barre de progression du module `videos`). La séance attend la découpe (« Découpe cette nuit »).
   Pas encore : la pastille caméra et son panneau (rien à piloter avant l'étape 3), le dossier
   Sparring dans Docs, l'effacement automatique.
2. **Découpe** : conteneur à part `sparring-worker` (§11), qui range ses clips par
   `SessionClips.add_clip` puis passe la séance à `ready`.
3. **Enregistreur Kotlin** (§11), puis la pastille caméra.

## 9. Risques

- **Puissance du VPS** : le traitement prendra peut-être 2 à 5 fois la durée de la vidéo. À vérifier
  en V1, avec un PC local en repli.
- **Envoi** : 3 à 4 Go par séance sur la connexion du club.
- **Combattants emmêlés au sol, ou tenues identiques** : risque d'inverser les noms. C'est rattrapé
  par la correction manuelle.
- **Passages devant la caméra** : limités par la hauteur et la position côté mur.
- **Lumière du gymnase** : image bruitée, à juger sur la vidéo de test.

## 10. Questions ouvertes

- Les murs de la salle sont-ils en placo ou en plâtre sur brique ? Y a-t-il des espaliers ?
- Quelle est la marge de puissance du VPS une fois les autres services en place ?
- Quel débit d'envoi a-t-on depuis le club ?
- Combien de jours garde-t-on un clip non gardé (7 proposé), et combien de clips chacun peut-il garder (§6.6) ?
- Un membre peut-il voir les combats des autres ? Proposé : non, seulement les siens ; les coachs voient tout.
- Où recueillir le consentement au droit à l'image : à l'adhésion HelloAsso ou dans l'appli ?
- Les combats sans Y doivent-ils être gardés, ou ignorés ?
- Nom générique du module : « Clips de séance » proposé, « Sparring » à l'écran pour le combat (§6.1).
- Contretemps, où il est éteint : fait à l'étape 1 par une ligne `org_modules` éteinte pour chaque
  école existante (migration). Une nouvelle école l'aura allumé ; un défaut « éteint » dans `Module`
  serait un nouveau point d'extension, à décider avec Seb.

## 11. Installation et exploitation

But : pouvoir réinstaller le module sur un autre VPS sans rien deviner. Mis à jour à chaque étape.

**Code.** Backend `backend/src/session_clips/` (générique) et `backend/src/session_clips_contretemps/`
(branchement : qui est coach, annuaire des personnes, déclaration `module.py`), listé dans
`backend/src/app/modules.py`. Frontend `frontend/src/modules/session-clips/`, listé dans
`frontend/src/app/modules.js`, affiché par `App.jsx` (onglet `sparring`).

**Base.** Migration Alembic `ee886b89a201_session_clips` : crée `sc_sessions`, `sc_clips`,
`sc_participants`, `sc_attendees`, et éteint le module dans chaque école existante (une ligne
`org_modules` à `enabled = 0`). Une école créée ensuite l'a allumé (pas de ligne = allumé). Rien à
faire à la main : `deploy.sh` lance `alembic upgrade head`.

**Allumer le module pour une école.** Admin > École > Personnalisation de l'application >
Fonctionnalités > case « Sparring » (Administrateur principal ou Super User). Il faut aussi le
module Vidéos. Module éteint : onglet caché, routes `/session-clips/...` en 404.

**Fichiers.** Aucun dossier nouveau : la vidéo brute d'une séance et chaque clip sont des vidéos du
module `videos`, rangées dans `VIDEOS_DIR/<id de l'école>/` (dans l'image : `/app/data/uploads/videos`,
volume Docker `backend_data` monté sur `/app/data`, avec la base SQLite). Changer de VPS = copier ce
volume, comme pour le reste de l'appli. La vidéo brute n'est pas compressée par le conteneur
`video-compression` (envoyée « déjà compressée ») : elle sera découpée puis effacée.

**Conteneurs.** Étape 1 : aucun nouveau, tout passe par `backend`. Étape 2 : `sparring-worker`
(image à part avec PyTorch et YOLO, même volume `backend_data`) — Dockerfile, bloc
`docker-compose.yml`, variables et commandes à écrire ici à ce moment-là.

**Variables.** Aucune nouvelle à l'étape 1 (`DATABASE_URL`, `VIDEOS_DIR` existent déjà).

**Vérifier.** `cd backend && pytest tests/test_session_clips.py`.
