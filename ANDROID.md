# Application Android « Tournage » (Capacitor)

Le dossier `frontend/android/` est l'appli Android **« Tournage <école> »** (décision de Seb du
12/11/2026, `spec/modules/video-combats.md` §4 et §11). Elle sert au téléphone qui filme la salle ;
tout le monde garde la PWA pour le reste.

- **Elle ouvre le site en ligne de l'école** (`server.url` de Capacitor) : chaque mise en ligne s'y
  voit sans réinstaller. Sans réseau, elle affiche `frontend/android-shell/hors-ligne.html`.
- **Elle reçoit les partages** (Seb, 13/11) : dans la liste « Partager » d'Android, un lien ou un
  texte ouvre `/partage?…` de l'école, l'écran « Envoyer à… » (`MainActivity.partage`, filtre
  `ACTION_SEND` dans `AndroidManifest.xml`).
- **Elle envoie les vidéos de toute l'appli** (Seb, 23/11) : le Timer de Fights, les
  chorégraphies, les publications. La page écrit la vidéo dans `<filesDir>/video-uploads/`
  (plugin `EnvoisVideo`, `uploads/VideoUploadsPlugin.kt`), puis une tâche WorkManager en premier
  plan l'envoie par blocs de 4 Mo (`uploads/UploadWorker.kt`) : l'envoi finit appli fermée, repart
  au retour du réseau et survit à un redémarrage du téléphone. La page suit l'avancement
  (`state`) ; hors de l'appli, c'est elle qui envoie, avec reprise à la réouverture
  (`frontend/src/utils/videoUploads.js`, `spec/SPEC.md` §6.8).
- **Elle filme** quand Fights › Tournage est sur « Caméra » : plugin `camera/TournagePlugin.kt` et
  service de premier plan `camera/RecorderService.kt` (repris de l'appli caméra `recorder/`). Elle
  filme aussi le Timer étendu de Fights (`camera/TimerCamera.kt`, mêmes réglages, Seb 23/11) : le
  film est confié tel quel à la file d'envoi (`EnvoisVideo.adopt`).
- **L'icône est celle de l'école** : l'action prend `<adresse>/icons/icon-512-maskable.png` (la même
  que la PWA) et en fabrique les icônes Android. Après un changement de logo, relancer l'action
  « Appli Tournage (APK) » à la main (Actions › Run workflow).
- **Une appli par école** dont le Super User a choisi « Oui » dans Admin › École ›
  Personnalisation › Appli Android (visible si Fights est allumé ; depuis le 18/11/2026, remplace
  `frontend/android/ecoles.json`). L'action lit la liste sur le serveur
  (`/api/applis-android` : `{"cle", "nom", "adresse"}`), et le serveur la lance lui-même au « Oui »
  avec le jeton `GITHUB_APK_TOKEN` de `backend/.env` (jeton GitHub à grain fin, dépôt
  `silvaplana/contretemps`, droit « Actions : lecture et écriture »). Le nom affiché est
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
