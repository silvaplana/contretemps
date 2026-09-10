// Domaine "comptes" (voir spec/SPEC.md §6.2/§6.3) — pour l'instant, couvre
// la vraie liste des comptes admin de l'école (Admin > Conversations,
// "Ajouter un membre" > Admin, à la place du "Direction" fictif d'avant)
// et la modification email/code_recuperation depuis Profil (crayon, voir
// ProfilScreen.jsx). Pas encore de module complet (pas d'écran de gestion
// multi-admin, voir spec §8).

import { currentUser } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function listerAdminsMaquette() {
  // Un seul admin en maquette (voir mockData.js: currentUser) — même
  // convention d'id que le reste du mock (chaîne, pas un entier).
  return [{ id: currentUser.id, nom: currentUser.nom, prenom: currentUser.prenom }]
}

async function listerAdminsReel(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/comptes?ecole_id=${ecoleId}&role=admin`)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.json()
}

export async function listerAdmins(ecoleId) {
  return estModeDemo() ? listerAdminsMaquette() : listerAdminsReel(ecoleId)
}

function versChampsBackend({ codeRecuperation, ...reste }) {
  return { ...reste, ...(codeRecuperation !== undefined && { code_recuperation: codeRecuperation }) }
}

// Réel uniquement (comme auth.js: verifierRecuperation/repondreRecuperation)
// — "Voir une maquette" est retiré du login, la maquette n'a plus de
// vraie session admin à modifier.
export async function modifier(compteId, patch) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(versChampsBackend(patch)),
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.json()
}
