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
Android Studio ni le SDK Android installés : le dossier `android/` a été
généré ici, mais il faut l'ouvrir sur une machine avec Android Studio pour
le compiler et le lancer sur un téléphone ou un émulateur.

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

Alternative en ligne de commande (nécessite le SDK Android installé et
`ANDROID_HOME` configuré) :

```bash
cd frontend/android
./gradlew assembleDebug   # génère un .apk de debug, non signé
# APK généré dans android/app/build/outputs/apk/debug/
```

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
