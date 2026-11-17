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
    cover: video(s.cover),
    ...(s.clips ? { clips: s.clips.map(clip) } : {}),
    ...(s.film ? { film: s.film.map((x) => ({ ...x, video: video(x.video) })) } : {}),
  }
}

export const moi = () => appel('/me')
export const seances = async () => (await appel('/sessions')).map(seance)
export const renommerSeance = async (id, title) => seance(await appel(`/sessions/${id}`, json('PATCH', { title })))
export const relancerDecoupe = (id) => appel(`/sessions/${id}/recut`, { method: 'POST' })
export const supprimerSeance = (id) => appel(`/sessions/${id}`, { method: 'DELETE' })
export const detailSeance = async (id) => seance(await appel(`/sessions/${id}`))
export const creerSeance = async (corps) => seance(await appel('/sessions', json('POST', corps)))
export const filmerCombat = async (corps) => clip(await appel('/fights', json('POST', corps)))
export const mesCombats = async () => (await appel('/mine')).map(clip)
// La pastille de Fights : combats validés pas encore ouverts (Seb, 17/11).
export const nouveaux = () => appel('/new')
export const obtenirClip = async (id) => clip(await appel(`/clips/${id}`))
export const nommer = async (id, people) => clip(await appel(`/clips/${id}/participants`, json('PUT', { people })))
export const valider = async (id) => clip(await appel(`/clips/${id}/validate`, { method: 'POST' }))
export const supprimer = (id) => appel(`/clips/${id}`, { method: 'DELETE' })
export const membres = () => appel('/people')
// La caméra de la salle (étape 3).
export const camera = () => appel('/camera')
// Fights › Tournage sur « Caméra » : ce téléphone devient la caméra de l'école.
export const ceTelephoneFilme = () => appel('/camera/this-phone', { method: 'POST' })
// L'adresse complète de l'API, pour le film en tâche de fond de l'appli Tournage.
export const adresseApi = () => new URL(BASE_URL, window.location.href).href.replace(/\/$/, '')
export const demarrerCamera = (title) => appel('/camera/start', json('POST', { title }))
export const arreterCamera = () => appel('/camera/stop', { method: 'POST' })
export const favoris = async () => (await appel('/favorites')).map(clip)
export const favori = async (id, oui) => clip(await appel(`/clips/${id}/favorite`, json('PUT', { favorite: oui })))

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

// Un clip ou plusieurs (sélection par appui long).
export async function telecharger(clips) {
  for (const c of [].concat(clips)) {
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
}

// Le menu Partager du téléphone (WhatsApp, mail…). Faux si le navigateur ne
// sait pas partager ces fichiers : on télécharge alors à la place.
export async function partager(clips) {
  const liste = [].concat(clips)
  const fichiers = await Promise.all(liste.map(fichierDuClip))
  if (navigator.canShare?.({ files: fichiers })) {
    try {
      await navigator.share({ files: fichiers, title: liste.length === 1 ? liste[0].title : 'Combats' })
    } catch (err) {
      if (err.name !== 'AbortError') throw err
    }
    return true
  }
  return false
}
// Le Labo (§6.5 bis) : essais sur des vidéos déjà filmées, et les signes du club.
function essai(e) {
  return { ...e, video: video(e.video) }
}
export const essais = async () => (await appel('/lab')).map(essai)
export const essaiLabo = async (id) => essai(await appel(`/lab/${id}`))
export const creerEssai = async (corps) => essai(await appel('/lab', json('POST', corps)))
export const renommerEssai = async (id, title) => essai(await appel(`/lab/${id}`, json('PATCH', { title })))
export const supprimerEssai = (id) => appel(`/lab/${id}`, { method: 'DELETE' })
export const relireEssai = (id) => appel(`/lab/${id}/reread`, { method: 'POST' })
// Réglages de la découpe du club : { signs, framing, start_skip, end_skip }.
export const reglagesDuClub = () => appel('/signs')
export const reglerClub = (reglages) => appel('/signs', json('PUT', reglages))
// Ceux du Labo, à part : on y expérimente sans changer le tournage (Seb, 12/11).
export const reglagesDuLabo = () => appel('/lab/signs')
export const reglerLabo = (reglages) => appel('/lab/signs', json('PUT', reglages))

// Fights › ⋮ › Entraîner l'écoute (Seb, 14/11) : les cris enregistrés au téléphone.
export const enregistrements = () => appel('/voice')
export const envoyerEnregistrement = (mot, son) =>
  appel(`/voice/${mot}`, { method: 'POST', headers: { 'Content-Type': son.type || 'audio/webm' }, body: son })
export const supprimerEnregistrement = (mot, nom) => appel(`/voice/${mot}/${nom}`, { method: 'DELETE' })
export async function lireEnregistrement(mot, nom) {
  const reponse = await fetch(`${BASE}/voice/${mot}/${nom}`)
  if (!reponse.ok) throw new Error('Enregistrement introuvable')
  return URL.createObjectURL(await reponse.blob())
}
export const notesSeance = (id) => appel(`/sessions/${id}/voice-notes`)
export const retirerNote = (id, t) => appel(`/sessions/${id}/voice-notes?t=${t}`, { method: 'DELETE' })
export const noterCri = (id, corps) => appel(`/sessions/${id}/voice-notes`, json('POST', corps))
// Noter les gestes dans la frise (Seb, 15/11) et « Proposer un réglage ».
// Qui est qui ? (Seb, 17/11) : les personnes repérées dans les combats d'une séance.
export const personnes = (id) => appel(`/sessions/${id}/people`)
export const nommerPersonne = (id, n, who) => appel(`/sessions/${id}/people/${n}`, json('PUT', { who }))
export const notesGestes = (id) => appel(`/sessions/${id}/gesture-notes`)
export const noterGeste = (id, corps) => appel(`/sessions/${id}/gesture-notes`, json('POST', corps))
export const retirerGeste = (id, t) => appel(`/sessions/${id}/gesture-notes?t=${t}`, { method: 'DELETE' })
export const proposerReglage = () => appel('/signs/proposal')
export const effacerEnregistrements = () => appel('/voice', { method: 'DELETE' })
export const effacerTests = () => appel('/voice-tests', { method: 'DELETE' })
export const envoyerTest = (son) =>
  appel('/voice-tests', { method: 'POST', headers: { 'Content-Type': son.type || 'audio/webm' }, body: son })
export const resultatTest = (nom) => appel(`/voice-tests/${nom}`)
export const repondreTest = (nom, corps) => appel(`/voice-tests/${nom}/answer`, json('POST', corps))
export const motManque = (nom, word) => appel(`/voice-tests/${nom}/missing`, json('POST', { word }))
export const rejouerEssais = () => appel('/voice-replays', { method: 'POST' })
export const rejeux = () => appel('/voice-replays')
