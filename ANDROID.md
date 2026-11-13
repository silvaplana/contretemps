# Application Android « Tournage » (Capacitor)

Le dossier `frontend/android/` est l'appli Android **« Tournage <école> »** (décision de Seb du
12/11/2026, `spec/modules/video-combats.md` §4 et §11). Elle sert au téléphone qui filme la salle ;
tout le monde garde la PWA pour le reste.

- **Elle ouvre le site en ligne de l'école** (`server.url` de Capacitor) : chaque mise en ligne s'y
  voit sans réinstaller. Sans réseau, elle affiche `frontend/android-shell/hors-ligne.html`.
- **Elle reçoit les partages** (Seb, 13/11) : dans la liste « Partager » d'Android, un lien ou un
  texte ouvre `/partage?…` de l'école, l'écran « Envoyer à… » (`MainActivity.partage`, filtre
  `ACTION_SEND` dans `AndroidManifest.xml`).
- **Elle filme** quand Fights › Tournage est sur « Caméra » : plugin `camera/TournagePlugin.kt` et
  service de premier plan `camera/RecorderService.kt` (repris de l'appli caméra `recorder/`).
- **L'icône est celle de l'école** : l'action prend `<adresse>/icons/icon-512-maskable.png` (la même
  que la PWA) et en fabrique les icônes Android. Après un changement de logo, relancer l'action
  « Appli Tournage (APK) » à la main (Actions › Run workflow).
- **Une appli par école**, listée dans `frontend/android/ecoles.json` :
  `{"cle": "asc-la-ciotat", "nom": "ASC La Ciotat", "adresse": "https://…"}`. Le nom affiché est
  « Tournage » suivi de `nom` ; l'identifiant Android est `com.contretemps.tournage.<clé>`, donc
  plusieurs applis cohabitent sur un même téléphone.
- **Mises à jour sans Play Store** : `Updater.java` (repris de l'appli Mountain) lit
  `version.json` dans la release GitHub « tournage-latest » à l'ouverture et toutes les 12 h, et
  propose « Nouvelle version disponible › Installer ». Il ne faut un nouvel APK que quand on touche
  à `frontend/android/` (la partie native), pas quand on change le site.

## Construire

L'action GitHub « Appli Tournage (APK) » (`.github/workflows/tournage-apk.yml`) le fait : à chaque
PR qui touche `frontend/android/`, `frontend/android-shell/` ou `frontend/capacitor.config.json`, elle
vérifie la construction ; à chaque fusion dans `main`, elle publie
`https://github.com/silvaplana/contretemps/releases/download/tournage-latest/tournage-<clé>.apk`.

Signature : le secret GitHub `SIGNING_PASSWORD` (Settings › Secrets and variables › Actions) chiffre
la clé fixe, créée au premier passage et rangée dans la release « tournage-cle ». Ne jamais
supprimer cette release ni changer le mot de passe. Sans le secret, la clé est jetable et chaque
mise à jour demande de désinstaller.

En local (Android Studio ou SDK + JDK 21) :

```bash
cd frontend
npm install
# Mettre l'adresse de l'école dans server.url de capacitor.config.json, puis :
npx cap sync android
cd android
./gradlew assembleRelease -Pecole=asc-la-ciotat -PnomEcole="ASC La Ciotat"
```

Sans clé, l'APK local est signé en debug.

## Installer sur un téléphone

Ouvrir le lien `tournage-<clé>.apk` dans Chrome sur le téléphone, accepter « Installer des applis
inconnues » pour Chrome, ouvrir « Tournage <école> » et se connecter. Ensuite l'appli propose
elle-même ses mises à jour (la première fois, Android demande d'autoriser l'appli à installer des
mises à jour).
