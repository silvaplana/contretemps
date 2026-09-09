// Domaine "vidéos" (écran Vidéo + onglet vidéos d'une chorégraphie, voir
// spec/SPEC.md §6.8) — voir api/README.md pour le principe général.
//
// ⚠️ Limite connue, pas résolue ici : "ajouter une vidéo" ne fait
// aujourd'hui QUE choisir un fichier local (URL.createObjectURL, voir
// AddVideoModal.jsx — valable seulement dans cette session de
// navigateur). Le vrai upload de fichier n'existe pas encore côté
// backend (chantier à part, différé). En mode réel, ce fichier envoie
// donc la forme REST correcte (POST/PUT/DELETE avec les bons champs),
// mais une URL locale choisie par l'utilisateur resterait inutilisable
// ailleurs qu'ici — décision explicite (voir l'utilisateur), à corriger
// seulement quand le vrai upload existera.
//
// `duree` (affichée seulement si `url` est vide, voir VideoThumb.jsx)
// n'existe pas côté backend — jamais envoyée/lue en mode réel.

import { videosParCours } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function dateAffichee() {
  return new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
}

// --- Maquette : copie mutable en mémoire, jamais l'objet original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) {
    magasin = Object.fromEntries(
      Object.entries(videosParCours).map(([coursId, liste]) => [coursId, liste.map((v) => ({ ...v }))]),
    )
  }
  return magasin
}
function listeMaquette(coursId) {
  const m = lireMagasin()
  if (!m[coursId]) m[coursId] = []
  return m[coursId]
}
function trouverOuLever(videoId) {
  for (const liste of Object.values(lireMagasin())) {
    const v = liste.find((x) => x.id === videoId)
    if (v) return v
  }
  throw new Error('Vidéo introuvable')
}

async function listerMaquette(coursId) {
  return listeMaquette(coursId)
}

async function creerMaquette(coursId, donnees) {
  const nouvelle = {
    id: crypto.randomUUID(),
    titre: donnees.titre,
    description: donnees.description ?? '',
    duree: donnees.duree || '00:00',
    url: donnees.url || null,
    choregraphieId: donnees.choregraphieId ?? null,
    datePublication: dateAffichee(),
  }
  listeMaquette(coursId).push(nouvelle)
  return nouvelle
}

async function modifierMaquette(videoId, patch) {
  const v = trouverOuLever(videoId)
  Object.assign(v, patch)
  return v
}

async function supprimerMaquette(coursId, videoId) {
  const liste = listeMaquette(coursId)
  const index = liste.findIndex((v) => v.id === videoId)
  if (index !== -1) liste.splice(index, 1)
}

// --- Réel : voir backend/src/videos/receiver.py. Pas encore exercé
// (mode démo par défaut, voir mode.js) mais tenu à jour avec les vraies
// routes.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

function versEcran(v) {
  return {
    id: v.id,
    titre: v.nom,
    description: v.description ?? '',
    duree: '', // voir note en tête de fichier : pas de champ backend
    url: v.lien_fichier,
    choregraphieId: v.choregraphie_id,
    datePublication: v.date_publication.slice(8, 10) + '/' + v.date_publication.slice(5, 7),
  }
}

async function listerReel(coursId) {
  const liste = await requete(`/cours/${coursId}/videos`)
  return liste.map(versEcran)
}

async function creerReel(coursId, { titre, description, url, choregraphieId }, uploaderId) {
  const v = await requete(`/cours/${coursId}/videos`, {
    method: 'POST',
    body: JSON.stringify({
      nom: titre,
      description: description ?? '',
      lien_fichier: url ?? '',
      choregraphie_id: choregraphieId ?? null,
      uploaded_by: uploaderId,
    }),
  })
  return versEcran(v)
}

async function modifierReel(videoId, { titre, choregraphieId, ...reste }) {
  const patch = {
    ...reste,
    ...(titre !== undefined && { nom: titre }),
    ...(choregraphieId !== undefined && { choregraphie_id: choregraphieId }),
  }
  const v = await requete(`/videos/${videoId}`, { method: 'PUT', body: JSON.stringify(patch) })
  return versEcran(v)
}

async function supprimerReel(_coursId, videoId) {
  await requete(`/videos/${videoId}`, { method: 'DELETE' })
}

// --- Point d'entrée unique, appelé par les écrans (voir VideoScreen.jsx
// et ChoregraphieScreen.jsx). `uploaderId` = compte connecté (voir
// activeUser dans App.jsx) — requis par le backend, ignoré en maquette.

export async function lister(coursId) {
  return estModeDemo() ? listerMaquette(coursId) : listerReel(coursId)
}

export async function creer(coursId, donnees, uploaderId) {
  return estModeDemo() ? creerMaquette(coursId, donnees) : creerReel(coursId, donnees, uploaderId)
}

export async function modifier(videoId, patch) {
  return estModeDemo() ? modifierMaquette(videoId, patch) : modifierReel(videoId, patch)
}

export async function supprimer(coursId, videoId) {
  return estModeDemo() ? supprimerMaquette(coursId, videoId) : supprimerReel(coursId, videoId)
}
