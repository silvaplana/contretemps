// Domaine "école" (Admin > École, voir spec/SPEC.md §5.1.1 et §6.1) — voir
// api/README.md pour le principe général.
//
// L'appli reste mono-école côté écran (voir auth.js : resoudreEcoleReelle),
// donc pas de lister()/creer() ici — juste modifier(), le seul besoin de
// AdminParametres.jsx.

import { ecoleActuelle } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais l'objet original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) magasin = { ...ecoleActuelle }
  return magasin
}

async function modifierMaquette(patch) {
  Object.assign(lireMagasin(), patch)
  return { ...magasin }
}

// --- Réel : voir backend/src/ecoles/receiver.py. ---

function versEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
    codeAccesAdmin: e.code_acces_admin,
    codeAccesProf: e.code_acces_prof,
    codeAccesEleve: e.code_acces_eleve,
  }
}

async function modifierReel(ecoleId, patch) {
  const corps = {
    ...(patch.nom !== undefined && { nom: patch.nom }),
    ...(patch.codePostal !== undefined && { code_postal: patch.codePostal }),
    ...(patch.codeAccesAdmin !== undefined && { code_acces_admin: patch.codeAccesAdmin }),
    ...(patch.codeAccesProf !== undefined && { code_acces_prof: patch.codeAccesProf }),
    ...(patch.codeAccesEleve !== undefined && { code_acces_eleve: patch.codeAccesEleve }),
  }
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps),
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return versEcran(await reponse.json())
}

// --- Point d'entrée unique, appelé par AdminParametres.jsx. ---

export async function modifier(ecoleId, patch) {
  return estModeDemo() ? modifierMaquette(patch) : modifierReel(ecoleId, patch)
}
