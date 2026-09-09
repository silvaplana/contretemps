// Domaine "chorégraphies" (écran Chorégraphie, voir spec/SPEC.md §6.7) —
// voir api/README.md pour le principe général.

import { choregraphiesParCours } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais l'objet original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) {
    magasin = Object.fromEntries(
      Object.entries(choregraphiesParCours).map(([coursId, liste]) => [
        coursId,
        liste.map((ch) => ({ ...ch, eleveIds: [...ch.eleveIds] })),
      ]),
    )
  }
  return magasin
}
function listeMaquette(coursId) {
  const m = lireMagasin()
  if (!m[coursId]) m[coursId] = []
  return m[coursId]
}
function trouverOuLever(choregraphieId) {
  for (const liste of Object.values(lireMagasin())) {
    const ch = liste.find((c) => c.id === choregraphieId)
    if (ch) return ch
  }
  throw new Error('Chorégraphie introuvable')
}

async function listerMaquette(coursId) {
  return listeMaquette(coursId)
}

async function creerMaquette(coursId, donnees) {
  const nouvelle = { id: crypto.randomUUID(), eleveIds: [], costume: '', horaireRepetition: '', ...donnees }
  listeMaquette(coursId).push(nouvelle)
  return nouvelle
}

async function modifierMaquette(choregraphieId, patch) {
  const ch = trouverOuLever(choregraphieId)
  Object.assign(ch, patch)
  return ch
}

async function supprimerMaquette(coursId, choregraphieId) {
  const liste = listeMaquette(coursId)
  const index = liste.findIndex((c) => c.id === choregraphieId)
  if (index !== -1) liste.splice(index, 1)
}

// --- Réel : voir backend/src/choregraphies/receiver.py. Pas encore
// exercé (mode démo par défaut, voir mode.js) mais tenu à jour avec les
// vraies routes.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

async function avecEleveIds(ch) {
  const eleves = await requete(`/choregraphies/${ch.id}/eleves`)
  return {
    id: ch.id,
    nom: ch.nom,
    costume: ch.costume ?? '',
    horaireRepetition: ch.horaire_repetition ?? '',
    eleveIds: eleves.map((e) => e.id),
  }
}

async function listerReel(coursId) {
  const liste = await requete(`/cours/${coursId}/choregraphies`)
  return Promise.all(liste.map(avecEleveIds))
}

function versChampsBackend({ horaireRepetition, ...reste }) {
  return { ...reste, ...(horaireRepetition !== undefined && { horaire_repetition: horaireRepetition }) }
}

async function creerReel(coursId, { eleveIds = [], ...donnees }) {
  const ch = await requete(`/cours/${coursId}/choregraphies`, {
    method: 'POST',
    body: JSON.stringify(versChampsBackend(donnees)),
  })
  await Promise.all(eleveIds.map((id) => requete(`/choregraphies/${ch.id}/eleves/${id}`, { method: 'POST' })))
  return avecEleveIds(ch)
}

async function modifierReel(choregraphieId, { eleveIds, ...patch }) {
  if (Object.keys(patch).length > 0) {
    await requete(`/choregraphies/${choregraphieId}`, {
      method: 'PUT',
      body: JSON.stringify(versChampsBackend(patch)),
    })
  }
  if (eleveIds !== undefined) {
    const actuels = (await requete(`/choregraphies/${choregraphieId}/eleves`)).map((e) => e.id)
    const aRetirer = actuels.filter((id) => !eleveIds.includes(id))
    const aAjouter = eleveIds.filter((id) => !actuels.includes(id))
    await Promise.all([
      ...aRetirer.map((id) => requete(`/choregraphies/${choregraphieId}/eleves/${id}`, { method: 'DELETE' })),
      ...aAjouter.map((id) => requete(`/choregraphies/${choregraphieId}/eleves/${id}`, { method: 'POST' })),
    ])
  }
  return avecEleveIds(await requete(`/choregraphies/${choregraphieId}`))
}

async function supprimerReel(_coursId, choregraphieId) {
  await requete(`/choregraphies/${choregraphieId}`, { method: 'DELETE' })
}

// --- Point d'entrée unique, appelé par les écrans (voir ChoregraphieScreen.jsx) ---

export async function lister(coursId) {
  return estModeDemo() ? listerMaquette(coursId) : listerReel(coursId)
}

export async function creer(coursId, donnees) {
  return estModeDemo() ? creerMaquette(coursId, donnees) : creerReel(coursId, donnees)
}

export async function modifier(choregraphieId, patch) {
  return estModeDemo() ? modifierMaquette(choregraphieId, patch) : modifierReel(choregraphieId, patch)
}

export async function supprimer(coursId, choregraphieId) {
  return estModeDemo()
    ? supprimerMaquette(coursId, choregraphieId)
    : supprimerReel(coursId, choregraphieId)
}
