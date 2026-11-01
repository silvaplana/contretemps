// Domaine "chorégraphies" (écran Chorégraphie, voir spec/SPEC.md §5.3 et
// §6.7) — voir api/README.md pour le principe général. Une chorégraphie
// arrive complète : ses élèves et ses vidéos (dans l'ordre). Les vidéos
// viennent du module générique (api/videos.js), que les chorégraphies
// utilisent sans qu'il les connaisse.

import { versEcran as videoVersEcran } from './videos.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) {
    const detail = (await reponse.json().catch(() => null))?.detail
    throw new Error(typeof detail === 'string' ? detail : `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

function versEcran(ch) {
  return {
    id: ch.id,
    // Tous ses cours, le premier en tête (une chorégraphie peut être
    // dansée par plusieurs cours, Seb 1er novembre).
    coursIds: ch.cours_ids,
    nom: ch.nom,
    costume: ch.costume ?? '',
    horaireRepetition: ch.horaire_repetition ?? '',
    eleveIds: ch.eleve_ids,
    videos: ch.videos.map(videoVersEcran),
  }
}

function versChampsBackend({ horaireRepetition, eleveIds, coursIds, autresCoursIds, ...reste }) {
  return {
    ...reste,
    ...(horaireRepetition !== undefined && { horaire_repetition: horaireRepetition }),
    ...(eleveIds !== undefined && { eleve_ids: eleveIds }),
    ...(coursIds !== undefined && { cours_ids: coursIds }),
    ...(autresCoursIds !== undefined && { autres_cours_ids: autresCoursIds }),
  }
}

// Toutes les chorégraphies de l'école (saison affichée), en une requête.
export async function lister(ecoleId) {
  return (await requete(`/ecoles/${ecoleId}/choregraphies`)).map(versEcran)
}

// Une chorégraphie est associée à son premier cours dès la création ;
// `donnees.autresCoursIds` : les autres cours qui la dansent.
export async function creer(coursId, donnees) {
  return versEcran(
    await requete(`/cours/${coursId}/choregraphies`, {
      method: 'POST',
      body: JSON.stringify(versChampsBackend(donnees)),
    }),
  )
}

export async function modifier(choregraphieId, patch) {
  return versEcran(
    await requete(`/choregraphies/${choregraphieId}`, {
      method: 'PUT',
      body: JSON.stringify(versChampsBackend(patch)),
    }),
  )
}

// Supprime aussi ses vidéos (fichiers compris).
export async function supprimer(choregraphieId) {
  await requete(`/choregraphies/${choregraphieId}`, { method: 'DELETE' })
}

// --- Vidéos d'une chorégraphie ---

// Clic "Ajouter" : l'envoi (voir utils/videoUploads.js) devient une vidéo
// de la chorégraphie. Ouvert à tous ; l'auteur est l'appelant.
// `dejaCompresse` : le téléphone a compressé la vidéo avant l'envoi — le
// serveur ne la recompresse pas (une seule compression).
export async function ajouterVideo(choregraphieId, uploadId, { nom, description, dejaCompresse = false }) {
  return videoVersEcran(
    await requete(`/choregraphies/${choregraphieId}/videos`, {
      method: 'POST',
      body: JSON.stringify({
        upload_id: uploadId,
        nom,
        description: description || '',
        deja_compresse: dejaCompresse,
      }),
    }),
  )
}

export async function modifierVideo(choregraphieId, videoId, { titre, description }) {
  return videoVersEcran(
    await requete(`/choregraphies/${choregraphieId}/videos/${videoId}`, {
      method: 'PUT',
      body: JSON.stringify({ ...(titre !== undefined && { nom: titre }), ...(description !== undefined && { description }) }),
    }),
  )
}

export async function supprimerVideo(choregraphieId, videoId) {
  await requete(`/choregraphies/${choregraphieId}/videos/${videoId}`, { method: 'DELETE' })
}

export async function reordonnerVideos(choregraphieId, videoIds) {
  await requete(`/choregraphies/${choregraphieId}/videos/ordre`, {
    method: 'PUT',
    body: JSON.stringify({ ordre_video_ids: videoIds }),
  })
}
