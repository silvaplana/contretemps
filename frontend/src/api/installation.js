// Installer Contretemps comme une appli (PWA) — demande du 2026-09-21 :
// inviter à l'installation tant que l'appli n'est pas installée.
//
// Selon le navigateur :
// - Android (Chrome, Samsung Internet), Chrome et Edge sur PC/Mac : le
//   navigateur prévient quand l'appli est installable (événement
//   `beforeinstallprompt`) ; on garde cet événement et NOTRE bouton ouvre la
//   vraie fenêtre d'installation du système en un appui.
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

let invitationDifferee = null
const abonnes = new Set()

function prevenir() {
  abonnes.forEach((f) => f())
}

// À appeler UNE fois, le plus tôt possible (main.jsx) : l'événement peut
// arriver avant même que React ait affiché quoi que ce soit.
export function ecouterInstallation() {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault() // pas la mini-barre du navigateur : notre invitation à la place
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

function estSafariMac() {
  const ua = navigator.userAgent
  return /macintosh/i.test(ua) && /safari/i.test(ua) && !/chrome|chromium|crios|edg|firefox|fxios/i.test(ua)
}

function estFirefoxOrdinateur() {
  return /firefox/i.test(navigator.userAgent) && !/android|mobile/i.test(navigator.userAgent)
}

// 'bouton' : installation en un appui (Android/Chrome) ;
// 'ios' : instructions Partager -> Sur l'écran d'accueil ;
// 'ios-ouvrir-safari' : il faut d'abord ouvrir la page dans Safari ;
// 'mac-safari' : menu Fichier > Ajouter au Dock ;
// 'firefox' : ouvrir la page dans Chrome ou Edge ;
// null : déjà installée, ou rien à proposer sur ce navigateur (ex. Chrome
// qui n'a pas — ou pas encore — annoncé l'appli installable).
export function modeInstallation() {
  if (estInstallee()) return null
  if (invitationDifferee) return 'bouton'
  if (estIOS()) return estNavigateurIntegre() ? 'ios-ouvrir-safari' : 'ios'
  if (estSafariMac()) return 'mac-safari'
  if (estFirefoxOrdinateur()) return 'firefox'
  return null
}

export async function installer() {
  if (!invitationDifferee) return
  const invitation = invitationDifferee
  invitation.prompt()
  await invitation.userChoice
  // Utilisable une seule fois, quelle que soit la réponse.
  invitationDifferee = null
  prevenir()
}

// --- "Plus tard" : encart masqué 7 jours sur cet appareil ---

const CLE_PLUS_TARD = 'contretemps:installationPlusTard'
const SEPT_JOURS = 7 * 24 * 3600 * 1000

export function reporteRecemment() {
  try {
    return Date.now() - Number(localStorage.getItem(CLE_PLUS_TARD) || 0) < SEPT_JOURS
  } catch {
    return false
  }
}

export function reporter() {
  try {
    localStorage.setItem(CLE_PLUS_TARD, String(Date.now()))
  } catch {
    // Tant pis : l'encart reviendra au prochain lancement.
  }
}

// Mode courant, tenu à jour quand le navigateur annonce l'installabilité
// (souvent après le premier affichage) ou que l'installation se termine.
export function useModeInstallation() {
  const [mode, setMode] = useState(modeInstallation)
  useEffect(() => {
    const f = () => setMode(modeInstallation())
    abonnes.add(f)
    return () => abonnes.delete(f)
  }, [])
  return mode
}
