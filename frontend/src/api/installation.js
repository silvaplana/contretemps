// Installer Contretemps comme une appli (PWA) — demande du 2026-09-21 :
// inviter à l'installation tant que l'appli n'est pas installée.
//
// Selon le navigateur :
// - Android (Chrome, Samsung Internet), Chrome et Edge sur PC/Mac : le
//   navigateur prévient quand l'appli est installable (événement
//   `beforeinstallprompt`) ; on garde cet événement et NOTRE bouton ouvre la
//   vraie fenêtre d'installation du système en un appui — en plus de la
//   proposition du navigateur lui-même, laissée intacte.
// - Samsung Internet (Android) : sait installer, mais seulement dans
//   l'"écran Applis", en appli web rattachée au navigateur — pas d'icône sur
//   l'écran d'accueil. Chrome, lui, fait une vraie appli Android (écran Applis
//   + écran d'accueil) : on propose d'ouvrir la page dans Chrome (demande du
//   2026-09-21), l'installation Samsung restant possible en second choix.
// - Tout autre navigateur Android (Firefox, Opera...) qui n'annonce pas
//   l'appli installable : même trajet qu'avec Samsung Internet ci-dessus,
//   ouvrir la page dans Chrome (demande du 2026-09-22) — sur Android, seul
//   Chrome sait créer une vraie icône sur l'écran d'accueil.
// - Safari sur Mac (macOS Sonoma et suivants) : pas d'API non plus, mais
//   menu Fichier > "Ajouter au Dock" — on l'explique.
// - Firefox (PC/Mac) : ne sait pas installer une appli web — on conseille
//   Chrome ou Edge.
// - iPhone/iPad : Apple ne laisse aucun site lancer l'installation. On ne
//   peut qu'expliquer le geste : Partager, puis "Sur l'écran d'accueil".
//   Dans le navigateur intégré d'une autre appli (lien ouvert depuis
//   Facebook, Instagram...), même ça est impossible : il faut d'abord ouvrir
//   la page dans Safari.

import { useEffect, useState } from 'react'
import * as sessionApi from './session.js'

let invitationDifferee = null
const abonnes = new Set()

function prevenir() {
  abonnes.forEach((f) => f())
}

// À appeler UNE fois, le plus tôt possible (main.jsx) : l'événement peut
// arriver avant même que React ait affiché quoi que ce soit.
export function ecouterInstallation() {
  window.addEventListener('beforeinstallprompt', (e) => {
    // Surtout PAS de e.preventDefault() : il supprimait la proposition
    // native de Chrome ("Installer l'application", qui installe une vraie
    // appli Android) — régression signalée le 2026-09-21. On garde juste
    // l'événement pour que notre bouton ouvre la même fenêtre.
    invitationDifferee = e
    prevenir()
  })
  window.addEventListener('appinstalled', () => {
    invitationDifferee = null
    prevenir()
  })
}

export function estInstallee() {
  return window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true
}

function estIOS() {
  const ua = navigator.userAgent
  // iPadOS se présente comme un Mac, mais tactile.
  return /iphone|ipad|ipod/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1)
}

// Navigateurs intégrés à d'autres applis, où "Sur l'écran d'accueil"
// n'existe pas.
function estNavigateurIntegre() {
  return /FBAN|FBAV|Instagram|Line\/|GSA\//i.test(navigator.userAgent)
}

// Navigateur de l'iPhone/iPad : Safari, Chrome (CriOS) ou un autre
// (Firefox, Edge, Opera...). Tous passent par "Partager", mais pas au même
// endroit.
function navigateurIOS() {
  const ua = navigator.userAgent
  if (/CriOS/i.test(ua)) return 'chrome'
  if (/FxiOS|EdgiOS|OPiOS/i.test(ua)) return 'autre'
  return 'safari'
}

function estSamsungInternet() {
  return /SamsungBrowser/i.test(navigator.userAgent) && /android/i.test(navigator.userAgent)
}

function estAndroid() {
  return /android/i.test(navigator.userAgent)
}

function estSafariMac() {
  const ua = navigator.userAgent
  return /macintosh/i.test(ua) && /safari/i.test(ua) && !/chrome|chromium|crios|edg|firefox|fxios/i.test(ua)
}

function estFirefoxOrdinateur() {
  return /firefox/i.test(navigator.userAgent) && !/android|mobile/i.test(navigator.userAgent)
}

// 'ouvrir-chrome' : Samsung Internet, ouvrir la page dans Chrome pour
//   installer une vraie appli (voir ouvrirDansChrome) ;
// 'bouton' : installation en un appui (Android/Chrome) ;
// 'ios' / 'ios-chrome' / 'ios-autre' : iPhone/iPad (Safari, Chrome, autre) —
//   mêmes étapes Partager -> Sur l'écran d'accueil, la 1re ramenant dans
//   Safari (voir InstructionsInstallation) ;
// 'ios-ouvrir-safari' : il faut d'abord ouvrir la page dans Safari ;
// 'mac-safari' : menu Fichier > Ajouter au Dock ;
// 'firefox' : ouvrir la page dans Chrome ou Edge ;
// null : déjà installée, ou rien à proposer sur ce navigateur (ex. Chrome
// qui n'a pas — ou pas encore — annoncé l'appli installable).
export function modeInstallation() {
  if (estInstallee()) return null
  if (estSamsungInternet()) return 'ouvrir-chrome'
  if (invitationDifferee) return 'bouton'
  // Tout autre navigateur Android (Firefox, Opera, DuckDuckGo...) qui n'a
  // pas annoncé l'appli installable : seul Chrome sait le faire (demande
  // utilisateur du 2026-09-22) — mêmes instructions génériques que pour
  // Samsung Internet ci-dessus.
  if (estAndroid()) return 'ouvrir-chrome'
  if (estIOS()) {
    if (estNavigateurIntegre()) return 'ios-ouvrir-safari'
    const navigateur = navigateurIOS()
    return navigateur === 'safari' ? 'ios' : `ios-${navigateur}`
  }
  if (estSafariMac()) return 'mac-safari'
  if (estFirefoxOrdinateur()) return 'firefox'
  return null
}

// Installation "à la Samsung" encore possible (second choix, pour qui n'a
// pas Chrome) : le navigateur a annoncé l'appli installable.
export function installationDirectePossible() {
  return invitationDifferee !== null
}

// Rouvre la page d'accueil de l'appli dans Chrome (lien "intent" d'Android ;
// si Chrome manque, Android propose de l'installer depuis le Play Store).
// `?installer=1` : Chrome affiche alors la "Dernière étape" (voir
// components/DerniereEtapeInstallation.jsx).
const PARAM_INSTALLER = 'installer'

export function ouvrirDansChrome() {
  // Efface la session de CE navigateur-ci (Samsung Internet, Firefox...)
  // avant de partir vers Chrome — demande utilisateur du 2026-09-23 :
  // sans ça, elle reste orpheline indéfiniment ici (Chrome et ce
  // navigateur ont chacun leur propre stockage, totalement étanche —
  // aucun moyen de la faire disparaître depuis Chrome après coup). La
  // vraie session repart de zéro dans Chrome ("vous devrez vous y
  // reconnecter", voir InstructionsInstallation).
  sessionApi.effacerCompteSauvegarde()
  const page = `${location.host}${import.meta.env.BASE_URL}?${PARAM_INSTALLER}=1`
  location.href = `intent://${page}#Intent;scheme=https;package=com.android.chrome;end`
}

export function arriveePourInstaller() {
  return new URLSearchParams(location.search).get(PARAM_INSTALLER) === '1'
}

// Retire le marqueur de l'adresse : ni un rechargement ni un favori ne
// rouvrent la "Dernière étape".
export function oublierArriveePourInstaller() {
  const url = new URL(location.href)
  url.searchParams.delete(PARAM_INSTALLER)
  history.replaceState(history.state, '', url)
}

// Renvoie la réponse de l'utilisateur ('accepted' ou 'dismissed').
export async function installer() {
  if (!invitationDifferee) return null
  const invitation = invitationDifferee
  invitation.prompt()
  const { outcome } = await invitation.userChoice
  // Utilisable une seule fois, quelle que soit la réponse.
  invitationDifferee = null
  prevenir()
  return outcome
}

// --- "Ne plus me demander" : sur cet appareil, pour de bon ---
//
// Remplace un ancien mécanisme "Plus tard" qui ne masquait que 7 jours
// (demande utilisateur du 2026-09-22 : l'écran plein écran après connexion,
// voir screens/InstallationScreen.jsx, redemande à CHAQUE connexion tant
// que cette case n'a jamais été cochée).

const CLE_NE_PLUS_DEMANDER = 'contretemps:installationNePlusDemander'

export function neJamaisDemander() {
  try {
    return localStorage.getItem(CLE_NE_PLUS_DEMANDER) === '1'
  } catch {
    return false
  }
}

export function definirNeJamaisDemander() {
  try {
    localStorage.setItem(CLE_NE_PLUS_DEMANDER, '1')
  } catch {
    // Tant pis : l'écran reviendra à la prochaine connexion.
  }
}

// Une désinstallation (voir plus bas) remet aussi ce choix à zéro —
// demande utilisateur du 2026-09-23 : cette case n'a de sens que par
// rapport à l'installation en cours ; si l'appli est désinstallée, la
// question redevient légitime, même si elle avait déjà été cochée avant.
export function oublierNeJamaisDemander() {
  try {
    localStorage.removeItem(CLE_NE_PLUS_DEMANDER)
  } catch {
    // Tant pis.
  }
}

// --- Désinstallation détectée -> effacer la session (demande du 2026-09-22)
//
// Aucune API web ne prévient QUAND une PWA est désinstallée (pas
// d'événement symétrique à `appinstalled`). On le déduit par recoupement,
// au chargement suivant : si CETTE session a un jour tourné en standalone
// (voir marquerSessionLieeInstallation, posé uniquement en observant
// estInstallee() directement — jamais depuis un onglet normal) et que ce
// n'est plus le cas maintenant, l'appli a très probablement été
// désinstallée -> App.jsx efface alors la session au lieu de la
// restaurer. Sans lien avec une install jamais observée (session
// uniquement utilisée au navigateur) : jamais effacée, elle reste
// mémorisée comme avant (demande explicite : "si on n'installe jamais
// l'appli, il faut quand même mémoriser la connexion").

const CLE_SESSION_LIEE_INSTALL = 'contretemps:sessionLieeInstallation'

export function marquerSessionLieeInstallation() {
  try {
    localStorage.setItem(CLE_SESSION_LIEE_INSTALL, '1')
  } catch {
    // Tant pis : au pire, une désinstallation future ne sera pas détectée.
  }
}

export function sessionEtaitLieeInstallation() {
  try {
    return localStorage.getItem(CLE_SESSION_LIEE_INSTALL) === '1'
  } catch {
    return false
  }
}

export function oublierLienInstallation() {
  try {
    localStorage.removeItem(CLE_SESSION_LIEE_INSTALL)
  } catch {
    // Tant pis.
  }
}

// Confirmation, quand le navigateur le permet (Chrome/Edge — voir
// site.webmanifest: related_applications), que l'appli est TOUJOURS
// installée même si CET onglet-ci ne tourne pas en standalone (ex. un
// lien ouvert dans un onglet normal alors que l'appli reste installée à
// côté) — évite de considérer ce cas comme une désinstallation. Renvoie
// `null` si le navigateur ne sait pas répondre (Safari/iOS, Firefox) :
// App.jsx applique alors la règle simple ci-dessus sans ce filet.
export async function estToujoursInstalleeSelonNavigateur() {
  if (!navigator.getInstalledRelatedApps) return null
  try {
    const apps = await navigator.getInstalledRelatedApps()
    return apps.length > 0
  } catch {
    return null
  }
}

// Mode courant, tenu à jour quand le navigateur annonce l'installabilité
// (souvent après le premier affichage) ou que l'installation se termine.
// Re-rendu même si le mode ne change pas : installationDirectePossible()
// peut, elle, avoir changé (Samsung Internet).
export function useModeInstallation() {
  const [mode, setMode] = useState(modeInstallation)
  const [, setVersion] = useState(0)
  useEffect(() => {
    const f = () => {
      setMode(modeInstallation())
      setVersion((v) => v + 1)
    }
    abonnes.add(f)
    return () => abonnes.delete(f)
  }, [])
  return mode
}
