// Domaine "professeurs" (Admin > Professeurs, voir spec/SPEC.md §6.3) —
// voir api/README.md pour le principe général. Plus simple qu'eleves.js :
// aucun champ propre côté backend (juste Compte + cours enseignés).

import { professeurs as professeursInitiaux } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais le tableau original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function copieProfonde(prof) {
  return { ...prof, coursIds: [...prof.coursIds] }
}
function lireMagasin() {
  if (magasin === null) magasin = professeursInitiaux.map(copieProfonde)
  return magasin
}

async function listerMaquette() {
  return lireMagasin()
}

async function creerMaquette({ nom, prenom, email }) {
  const nouveau = { id: crypto.randomUUID(), nom, prenom, email: email ?? '', coursIds: [] }
  lireMagasin().push(nouveau)
  return nouveau
}

async function modifierMaquette(profId, patch) {
  const liste = lireMagasin()
  const index = liste.findIndex((p) => p.id === profId)
  if (index === -1) throw new Error('Professeur introuvable')
  liste[index] = { ...liste[index], ...patch }
  return liste[index]
}

async function supprimerMaquette(profId) {
  magasin = lireMagasin().filter((p) => p.id !== profId)
}

async function basculerCoursMaquette(profId, coursId) {
  const prof = lireMagasin().find((p) => p.id === profId)
  if (!prof) throw new Error('Professeur introuvable')
  const inscrit = prof.coursIds.includes(coursId)
  prof.coursIds = inscrit ? prof.coursIds.filter((id) => id !== coursId) : [...prof.coursIds, coursId]
  return prof
}

// --- Réel : voir backend/src/profs/receiver.py. Pas encore exercé (mode
// démo par défaut, voir mode.js) mais tenu à jour avec les vraies routes.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// ProfSortie du backend renvoie déjà cours_ids (pas besoin d'une 2e
// requête comme pour les élèves) — juste traduire vers camelCase.
function versEcran(prof) {
  return { id: prof.id, nom: prof.nom, prenom: prof.prenom, email: prof.email ?? '', coursIds: prof.cours_ids }
}

async function listerReel(ecoleId) {
  const profs = await requete(`/profs?ecole_id=${ecoleId}`)
  return profs.map(versEcran)
}

async function creerReel(ecoleId, donnees) {
  return versEcran(await requete(`/profs?ecole_id=${ecoleId}`, { method: 'POST', body: JSON.stringify(donnees) }))
}

async function modifierReel(profId, patch) {
  return versEcran(await requete(`/profs/${profId}`, { method: 'PUT', body: JSON.stringify(patch) }))
}

async function supprimerReel(profId) {
  await requete(`/profs/${profId}`, { method: 'DELETE' })
}

async function basculerCoursReel(profId, coursId) {
  const prof = await requete(`/profs/${profId}`)
  const inscrit = prof.cours_ids.includes(coursId)
  await requete(`/cours/${coursId}/professeurs/${profId}`, { method: inscrit ? 'DELETE' : 'POST' })
  return versEcran(await requete(`/profs/${profId}`))
}

// --- Point d'entrée unique, appelé par les écrans (voir AdminProfesseurs.jsx) ---

export async function lister(ecoleId) {
  return estModeDemo() ? listerMaquette() : listerReel(ecoleId)
}

export async function creer(ecoleId, donnees) {
  return estModeDemo() ? creerMaquette(donnees) : creerReel(ecoleId, donnees)
}

export async function modifier(profId, patch) {
  return estModeDemo() ? modifierMaquette(profId, patch) : modifierReel(profId, patch)
}

export async function supprimer(profId) {
  return estModeDemo() ? supprimerMaquette(profId) : supprimerReel(profId)
}

export async function basculerCours(profId, coursId) {
  return estModeDemo() ? basculerCoursMaquette(profId, coursId) : basculerCoursReel(profId, coursId)
}
