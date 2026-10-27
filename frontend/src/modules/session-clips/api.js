// Sparring (module serveur `session_clips`, voir
// spec/modules/video-combats.md §6 et backend/src/session_clips/receiver.py).
// Session et école choisie ajoutées par api/identite.js. Les vidéos sont
// celles du module Vidéos : même format d'écran (api/videos.js : versEcran).
import { versEcran } from '../../api/videos.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE = `${BASE_URL}/session-clips`

async function appel(chemin, options = {}) {
  const reponse = await fetch(`${BASE}${chemin}`, options)
  if (!reponse.ok) {
    let message = `Requête échouée (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // réponse sans JSON : message par défaut
    }
    throw new Error(message)
  }
  return reponse.status === 204 ? null : reponse.json()
}

const json = (method, corps) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps) })

function video(v) {
  return v ? { ...versEcran(v), dureeSecondes: v.duree_secondes } : null
}

function clip(c) {
  return { ...c, video: video(c.video) }
}

function seance(s) {
  return {
    ...s,
    previews: s.previews.map(video),
    raw_video: video(s.raw_video),
    ...(s.clips ? { clips: s.clips.map(clip) } : {}),
  }
}

export const moi = () => appel('/me')
export const seances = async () => (await appel('/sessions')).map(seance)
export const detailSeance = async (id) => seance(await appel(`/sessions/${id}`))
export const creerSeance = async (corps) => seance(await appel('/sessions', json('POST', corps)))
export const mesCombats = async () => (await appel('/mine')).map(clip)
export const aVerifier = async () => (await appel('/to-check')).map(clip)
export const obtenirClip = async (id) => clip(await appel(`/clips/${id}`))
export const nommer = async (id, people) => clip(await appel(`/clips/${id}/participants`, json('PUT', { people })))
export const valider = async (id) => clip(await appel(`/clips/${id}/validate`, { method: 'POST' }))
export const supprimer = (id) => appel(`/clips/${id}`, { method: 'DELETE' })
export const membres = () => appel('/people')

// « Jeu. 23 oct. »
export function jour(iso) {
  const texte = new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

// Le fichier du clip, pour le garder ou le partager (§6.5).
async function fichierDuClip(c) {
  const reponse = await fetch(c.video.url)
  if (!reponse.ok) throw new Error('Vidéo indisponible')
  const blob = await reponse.blob()
  return new File([blob], `${c.title}.mp4`, { type: blob.type || 'video/mp4' })
}

export async function telecharger(c) {
  const fichier = await fichierDuClip(c)
  const url = URL.createObjectURL(fichier)
  const lien = document.createElement('a')
  lien.href = url
  lien.download = fichier.name
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  setTimeout(() => URL.revokeObjectURL(url), 60000)
}

// Le menu Partager du téléphone (WhatsApp, mail…). Faux si le navigateur ne
// sait pas partager un fichier : on télécharge alors à la place.
export async function partager(c) {
  const fichier = await fichierDuClip(c)
  if (navigator.canShare?.({ files: [fichier] })) {
    try {
      await navigator.share({ files: [fichier], title: c.title })
    } catch (err) {
      if (err.name !== 'AbortError') throw err
    }
    return true
  }
  return false
}
