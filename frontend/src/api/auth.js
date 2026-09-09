// Connexion — un seul point d'entrée (`login`) appelé par LoginScreen.
// Le mode n'est plus un interrupteur séparé : c'est le bouton cliqué qui
// décide, une fois pour toute la session — "Se connecter" (login) est
// TOUJOURS réel, "Voir une maquette" (voirMaquette) est TOUJOURS la
// maquette. Chacun fixe mode.js lui-même (voir activerModeReel/
// activerModeDemo) avant que les autres domaines (api/eleves.js etc.)
// ne consultent estModeDemo().

import { currentUser } from '../data/mockData.js'
import { activerModeDemo, activerModeReel } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : ne contacte jamais le réseau, toujours disponible. ---
async function loginMaquette() {
  return { compte: currentUser, ecole: null, modeDemo: true }
}

// --- Réel : POST /auth/login (voir backend/src/auth/receiver.py). ---

// Traduit une EcoleSortie (backend) vers la forme attendue par App.jsx
// (voir data/mockData.js : ecoleActuelle).
function versEcoleEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
    codeAccesAdmin: e.code_acces_admin,
    codeAccesProf: e.code_acces_prof,
    codeAccesEleve: e.code_acces_eleve,
  }
}

// L'appli reste mono-école côté écran (voir spec §2.1, multi-écoles
// prévu mais pas encore dans l'IHM) : en mode réel, on prend la
// première école du backend plutôt que de demander à l'utilisateur de
// la choisir — cohérent avec "Nouvelle école ?" qui n'en crée qu'une à
// la fois en pratique aujourd'hui.
async function resoudreEcoleReelle() {
  const reponse = await fetch(`${BASE_URL}/ecoles`)
  if (!reponse.ok) throw new Error('Impossible de contacter le backend')
  const ecoles = await reponse.json()
  if (ecoles.length === 0) {
    throw new Error('Aucune école côté backend (voir backend/README.md : python -m app.seed)')
  }
  return ecoles[0]
}

async function loginReel({ identifiant, code }) {
  const ecole = await resoudreEcoleReelle()
  const reponse = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ecole_id: ecole.id, identifiant, code }),
  })
  if (!reponse.ok) {
    throw new Error("Identifiant ou code d'accès incorrect")
  }
  const compte = await reponse.json()
  return { compte, ecole: versEcoleEcran(ecole), modeDemo: false }
}

export async function login(identifiants) {
  const resultat = await loginReel(identifiants)
  activerModeReel()
  return resultat
}

export async function voirMaquette() {
  activerModeDemo()
  return loginMaquette()
}
