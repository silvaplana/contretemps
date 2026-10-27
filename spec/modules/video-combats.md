# AppBase — Module `video-combats`

Version 0.1, 27 octobre 2026. Statut : **brouillon, idée à valider avec Seb** (discutée dans le projet
Claude « sambo-admin », fil « Vidéo des combats : existant »). Rien n'est codé. Le module n'est pas
encore accepté : il est proposé ici, comme le demande `CLAUDE.md`.

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
- **Module activable par organisation**, comme les autres modules.

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
| Avant le cours | Coach | Ouvre « Vidéo » dans la PWA | Voyant de l'enregistreur : prêt, batterie, place restante |
| Début du cours | Coach | Appuie sur « Démarrer la séance » | L'enregistreur filme ; la PWA affiche « Enregistrement en cours » |
| Échauffement | Chaque combattant | Passe 2 s sur le repère au sol, face à la caméra, et dit son prénom | Rien à l'écran : l'enregistrement est repéré au traitement |
| Avant un combat | Les deux combattants | Entrent dans la zone, font le Y pendant 2 s | Rien à l'écran : le début est repéré au traitement |
| Fin d'un combat | Les deux combattants | Font le X, ou sortent de la zone | Rien à l'écran : la fin est repérée au traitement |
| Changement de tenue | Le combattant | Repasse sur le repère | Sa nouvelle tenue remplace l'ancienne pour la suite |
| Fin du cours | Coach | Appuie sur « Fin de séance » | L'enregistreur s'arrête, envoie la vidéo, puis se remet en attente |
| La nuit | Serveur | Traite la vidéo | Clips créés, nommés, rangés ; vidéo brute supprimée après validation |
| Le lendemain | Coach | Ouvre la file « à vérifier » | Corrige les noms inversés ou manquants |
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

1. Le coach appuie sur « Démarrer la séance ».
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

1. Ouvre la file « à vérifier ».
2. Pour chaque clip : valide, inverse les deux noms, choisit un nom manquant ou supprime le clip.

**UC 8 — Regarder ses combats** · Membre

1. Ouvre « Mes combats » : ses clips, du plus récent au plus ancien, avec l'adversaire et la date.
2. Regarde un clip.

**UC 9 — Donner ou retirer son accord** · Membre (ou parent pour un mineur)

1. Coche ou décoche « J'accepte d'être filmé ».
2. Sans accord, ses combats ne sont plus gardés ; le retrait supprime aussi ses clips existants.

**UC 10 — Surveiller l'enregistreur** · Coach

1. Voit à tout moment : prêt, en cours, hors service ; batterie ; place restante ; dernier envoi.

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
(CameraX), indépendante du frontend, distribuée en APK. On n'utilise pas Capacitor, qui obligerait à
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
- **État visible dans la PWA** : caméra prête ou hors service, batterie, place restante.
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

Le clip est ensuite encodé en 720p et rangé comme une vidéo du module `videos`. La vidéo brute est
supprimée une fois le traitement validé.

## 6. Rôles, écrans, droit à l'image

| Rôle | Ce qu'il fait |
|---|---|
| Admin ou prof | Démarre et arrête une séance. Voit tous les clips. Corrige les noms (bouton « inverser », nommer un combat sans nom) |
| Membre | Voit « Mes combats », c'est-à-dire les clips où il apparaît |
| Téléphone caméra | Filme et envoie la vidéo |

**Écrans** : séances (liste et statut du traitement), clips d'une séance avec vignette et noms,
mes combats, file « à vérifier ».

**Droit à l'image** :

- On recueille un consentement « j'accepte d'être filmé » à l'adhésion ou dans l'appli. Pour les
  mineurs, ce sont les parents qui donnent leur accord.
- Les combats impliquant quelqu'un qui a refusé ne sont pas gardés.
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

Le code suivrait les conventions du dépôt : `backend/src/fight_clips/` et
`frontend/src/modules/fight_clips/`, tables préfixées `fc_`. Nom à valider.

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
- Combien de temps garde-t-on les clips, et qui peut voir les combats des autres ?
- Où recueillir le consentement au droit à l'image : à l'adhésion HelloAsso ou dans l'appli ?
- Les combats sans Y doivent-ils être gardés, ou ignorés ?
- Le module est-il propre aux sports de combat, ou généralisable (« clips de séance ») ?
