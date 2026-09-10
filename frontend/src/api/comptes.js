// Domaine "comptes" (voir spec/SPEC.md §6.2/§6.3) — pour l'instant, ne
// couvre que ce dont Admin > Conversations a besoin : la vraie liste des
// comptes admin de l'école (voir AdminGroupes.jsx, "Ajouter un membre" >
// Admin), à la place du "Direction" fictif d'avant. Pas encore de module
// complet (pas d'écran de gestion multi-admin, voir spec §8).

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
