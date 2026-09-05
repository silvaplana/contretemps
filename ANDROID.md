# Application Android (Capacitor)

Le frontend React/Vite est emballé en appli Android native via
[Capacitor](https://capacitorjs.com/) : pas de réécriture, l'appli Android
charge le même build web dans une WebView, avec en plus les capacités
natives (caméra, notifications...) si on en ajoute plus tard.

Le projet Android natif est déjà généré dans `frontend/android/` (dossier
Gradle standard, à ouvrir directement dans Android Studio). Ce document
explique comment le construire et le garder à jour.

## Pourquoi un build séparé du site web

L'appli web déployée (`silvaplana.cloud/contretemps/`) et l'appli Android
partagent le même code source, mais **pas le même build** :

- Le site web est servi sous le chemin `/contretemps/` (voir DEPLOY.md) →
  `npm run build` (dans `frontend/`), sortie dans `frontend/dist/`.
- L'appli Android charge les fichiers depuis une WebView locale, à la
  racine → `npm run build:android`, sortie dans `frontend/dist-android/`.

C'est `vite.config.js` qui fait la différence (mode `capacitor` ou non).
Ne pas confondre les deux dossiers de sortie, ni utiliser le mauvais build
pour l'appli Android (elle ne trouverait pas ses fichiers).

## Prérequis (sur la machine qui va builder l'appli)

- [Android Studio](https://developer.android.com/studio) (installe le SDK
  Android en même temps que l'IDE — c'est le plus simple).
- Node.js (déjà nécessaire pour le frontend, voir frontend/README.md).

Cet environnement de développement (celui de Claude Code) n'a pas
Android Studio installé, mais un premier `.apk` de debug y a quand même
été construit en ligne de commande (SDK + JDK installés manuellement pour
l'occasion, voir "Build en ligne de commande" ci-dessous) — pratique pour
un premier test rapide sur téléphone, sans remplacer un vrai poste avec
Android Studio pour la suite du développement (émulateur, debug, etc.).

## Premier lancement

```bash
cd frontend
npm install
npm run build:android    # build web -> frontend/dist-android/
npx cap sync android      # copie dist-android/ dans android/app/src/main/assets/public
```

Puis ouvrir le dossier `frontend/android/` dans Android Studio (File >
Open), laisser Gradle synchroniser, et lancer sur un émulateur ou un
téléphone branché (bouton ▶ "Run").

## Build en ligne de commande (sans Android Studio)

Possible avec juste le SDK Android (cmdline-tools) et un **JDK 17 ou 21**
— ⚠️ pas un JDK plus récent (25 par ex.) : Gradle (8.14.3 ici, embarqué via
le wrapper `gradlew`) ne sait pas encore lire les class files des JDK
au-delà de la version qu'il supporte, et échoue avec
`Unsupported class file major version 69` sur un JDK 25.

```bash
export ANDROID_HOME=~/android-sdk       # SDK installé via `sdkmanager`
export JAVA_HOME=~/jdk21                # JDK 17 ou 21, pas plus récent
cd frontend
npm run build:android && npx cap sync android
cd android
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew assembleDebug --no-daemon
# APK généré dans android/app/build/outputs/apk/debug/app-debug.apk
```

Packages SDK minimum (`sdkmanager "platform-tools" "platforms;android-36"
"build-tools;36.0.0"`, licences acceptées via `sdkmanager --licenses`) —
les numéros de version viennent de `frontend/android/variables.gradle`
(`compileSdkVersion`/`targetSdkVersion`) : à ajuster si ce fichier change.

C'est un `.apk` de **debug**, non signé pour le Play Store : suffisant
pour l'installer directement sur un téléphone Android (autoriser les
"sources inconnues") ou dans un émulateur, pas pour une publication.

## Après chaque modification du frontend

À chaque changement dans `frontend/src/`, refaire :

```bash
cd frontend
npm run build:android
npx cap sync android
```

Puis relancer depuis Android Studio (ou refaire `./gradlew assembleDebug`).
`npx cap sync` recopie le nouveau build web dans le projet Android — sans
ça, l'appli continue d'afficher l'ancienne version.

## Identité de l'appli

- `appId` : `com.contretemps.app` (identifiant unique, voir
  `frontend/capacitor.config.json` et `android/app/build.gradle` — à
  changer avant une vraie publication sur le Play Store si besoin).
- `appName` : "Contretemps".
- Icône et écran de démarrage : ceux par défaut de Capacitor pour
  l'instant (`android/app/src/main/res/`) — à personnaliser plus tard avec
  le logo "Ct" (voir spec/SPEC.md section 7, charte visuelle).

## Backend et vidéos une fois hors du navigateur web

L'appli mockup actuelle n'appelle aucune API (données en dur, voir
`frontend/src/data/mockData.js`) : elle fonctionne donc telle quelle dans
l'appli Android. Le jour où un vrai backend existera, penser à ce que
l'appli Android appelle une URL absolue (`https://silvaplana.cloud/...`) et
non un chemin relatif (`/contretemps/api/...`) : la WebView de l'appli n'a
pas le même contexte d'origine qu'un navigateur sur le site web.
