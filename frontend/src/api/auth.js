// Connexion — un seul point d'entrée (`login`) appelé par LoginScreen,
// qui ne sait jamais lui-même dans quel mode il tourne (voir mode.js).
// `voirMaquette` est un filet de sécurité séparé : TOUJOURS la maquette,
// quel que soit le mode courant (voir mode.js et backend-architecture,
// mémoire projet — décision explicite de garder cet accès tant que le
// vrai backend n'est pas branché de façon fiable).

import { currentUser } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : ne contacte jamais le réseau, toujours disponible. ---
async function loginMaquette() {
  return { compte: currentUser, modeDemo: true }
}

// --- Réel : POST /auth/login (voir backend/src/auth/receiver.py). Pas
// encore appelée en pratique (mode démo par défaut, voir mode.js) — prête
// pour le jour où on branchera vraiment le frontend sur l'API.
async function loginReel({ ecoleId, identifiant, code }) {
  const reponse = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ecole_id: ecoleId, identifiant, code }),
  })
  if (!reponse.ok) {
    throw new Error("Identifiant ou code d'accès incorrect")
  }
  const compte = await reponse.json()
  return { compte, modeDemo: false }
}

export async function login(identifiants) {
  if (estModeDemo()) return loginMaquette()
  return loginReel(identifiants)
}

export async function voirMaquette() {
  return loginMaquette()
}
