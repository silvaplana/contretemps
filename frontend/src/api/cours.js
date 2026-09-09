// Domaine "cours" (Admin > Cours, voir spec/SPEC.md §6.5) — voir
// api/README.md pour le principe général.
//
// ⚠️ Simplification volontaire : la maquette (et tous les écrans actuels
// — AdminCours, Présence, PlanningHebdoView, HeuresScreen) suppose UN
// SEUL `professeurId` par cours. Le backend modélise en réalité
// plusieurs profs par cours (table de jointure cours_professeurs, voir
// backend/src/cours/models.py) — la couche réelle ci-dessous s'adapte
// (ne prend que le premier professeur assigné) plutôt que de forcer une
// refonte des écrans aujourd'hui. À revoir si un jour l'IHM a besoin de
// plusieurs profs par cours.

import { cours as coursInitiaux } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire (voir eleves.js/profs.js). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) magasin = coursInitiaux.map((c) => ({ ...c }))
  return magasin
}

async function listerMaquette() {
  return lireMagasin()
}

async function creerMaquette(donnees) {
  const nouveau = { id: crypto.randomUUID(), ...donnees }
  lireMagasin().push(nouveau)
  return nouveau
}

async function modifierMaquette(coursId, patch) {
  const liste = lireMagasin()
  const index = liste.findIndex((c) => c.id === coursId)
  if (index === -1) throw new Error('Cours introuvable')
  liste[index] = { ...liste[index], ...patch }
  return liste[index]
}

async function supprimerMaquette(coursId) {
  magasin = lireMagasin().filter((c) => c.id !== coursId)
}

// --- Réel : voir backend/src/cours/receiver.py. Pas encore exercé (mode
// démo par défaut, voir mode.js) mais tenu à jour avec les vraies routes.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

async function avecProfesseurId(cours) {
  const professeurs = await requete(`/cours/${cours.id}/professeurs`)
  return {
    id: cours.id,
    nom: cours.nom,
    jour: cours.jour ?? '',
    heureDebut: cours.heure_debut ?? '',
    heureFin: cours.heure_fin ?? '',
    salle: cours.salle ?? '',
    professeurId: professeurs[0]?.id ?? '',
  }
}

async function listerReel(ecoleId) {
  const liste = await requete(`/cours?ecole_id=${ecoleId}`)
  return Promise.all(liste.map(avecProfesseurId))
}

function versChampsBackend({ heureDebut, heureFin, ...reste }) {
  return {
    ...reste,
    ...(heureDebut !== undefined && { heure_debut: heureDebut }),
    ...(heureFin !== undefined && { heure_fin: heureFin }),
  }
}

async function creerReel(ecoleId, { professeurId, ...donnees }) {
  const cours = await requete(`/cours?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify(versChampsBackend(donnees)),
  })
  if (professeurId) {
    await requete(`/cours/${cours.id}/professeurs/${professeurId}`, { method: 'POST' })
  }
  return avecProfesseurId(cours)
}

async function modifierReel(coursId, { professeurId, ...patch }) {
  if (Object.keys(patch).length > 0) {
    await requete(`/cours/${coursId}`, { method: 'PUT', body: JSON.stringify(versChampsBackend(patch)) })
  }
  if (professeurId !== undefined) {
    const actuels = await requete(`/cours/${coursId}/professeurs`)
    await Promise.all(actuels.map((p) => requete(`/cours/${coursId}/professeurs/${p.id}`, { method: 'DELETE' })))
    if (professeurId) {
      await requete(`/cours/${coursId}/professeurs/${professeurId}`, { method: 'POST' })
    }
  }
  return avecProfesseurId(await requete(`/cours/${coursId}`))
}

async function supprimerReel(coursId) {
  await requete(`/cours/${coursId}`, { method: 'DELETE' })
}

// --- Point d'entrée unique, appelé par les écrans (voir AdminCours.jsx) ---

export async function lister(ecoleId) {
  return estModeDemo() ? listerMaquette() : listerReel(ecoleId)
}

export async function creer(ecoleId, donnees) {
  return estModeDemo() ? creerMaquette(donnees) : creerReel(ecoleId, donnees)
}

export async function modifier(coursId, patch) {
  return estModeDemo() ? modifierMaquette(coursId, patch) : modifierReel(coursId, patch)
}

export async function supprimer(coursId) {
  return estModeDemo() ? supprimerMaquette(coursId) : supprimerReel(coursId)
}
