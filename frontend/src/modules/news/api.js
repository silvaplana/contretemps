// Actualités (module serveur `news`, voir spec/modules/actualites.md §8 et
// backend/src/news/receiver.py). Session et école choisie ajoutées par
// api/identite.js.
import { versEcran as videoVersEcran } from '../../api/videos.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function appel(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, options)
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

export function versEcran(n) {
  return {
    id: n.id,
    niveau: n.level, // important | normal | brief
    texte: n.body,
    enHautJusquau: n.on_top_until, // 'AAAA-MM-JJ' ou null
    enHaut: n.on_top,
    notifier: n.notify,
    auteur: n.author_name,
    publieeLe: n.published_at ? new Date(`${n.published_at}Z`) : null,
    modifieeLe: new Date(`${n.updated_at}Z`),
    nouveau: n.is_new,
    // Le carrousel, dans l'ordre : chaque élément est une photo (son
    // empreinte) ou une vidéo.
    media: n.media.map((m) => ({ photo: m.photo, video: m.video ? videoVersEcran(m.video) : null })),
    document: n.document, // { id, name } ou null
  }
}

const versServeur = (a) => ({
  level: a.niveau,
  body: a.texte,
  on_top_until: a.niveau === 'important' ? a.enHautJusquau : null,
  notify: a.notifier,
  publish: a.publier,
  media: a.media.map((m) => (m.photo ? { photo: m.photo } : { video_id: m.video.id })),
  document_id: a.document?.id ?? null,
})

export async function lireActus(ecoleId) {
  const r = await appel(`/ecoles/${ecoleId}/news`)
  return { peutPublier: r.can_publish, actus: r.items.map(versEcran) }
}

export async function lireAtelier(ecoleId) {
  return (await appel(`/ecoles/${ecoleId}/news/atelier`)).map(versEcran)
}

export async function enregistrer(ecoleId, actu) {
  const r = actu.id
    ? await appel(`/ecoles/${ecoleId}/news/${actu.id}`, json('PUT', versServeur(actu)))
    : await appel(`/ecoles/${ecoleId}/news`, json('POST', versServeur(actu)))
  return versEcran(r)
}

export const depublier = (ecoleId, id) => appel(`/ecoles/${ecoleId}/news/${id}/unpublish`, { method: 'POST' })
export const supprimer = (ecoleId, id) => appel(`/ecoles/${ecoleId}/news/${id}`, { method: 'DELETE' })

// Option « Ouvrir l'appli sur les actus » (§6). Module éteint ou erreur :
// on garde l'ouverture habituelle.
export async function ouvrirSurLesActus(ecoleId) {
  try {
    return (await appel(`/ecoles/${ecoleId}/news/settings`)).open_on_news
  } catch {
    return false
  }
}

// Pendant le test (§2 bis) : voit-on les actus, et peut-on choisir qui les
// voit (administrateur principal, Super User). Module éteint ou erreur : non.
export async function lireReglages(ecoleId) {
  try {
    const r = await appel(`/ecoles/${ecoleId}/news/settings`)
    return { ouvrir: r.open_on_news, voir: r.can_read, choisir: r.can_choose_readers }
  } catch {
    return { ouvrir: false, voir: false, choisir: false }
  }
}

const versLecteur = (r) => ({ id: r.id, nom: r.name, voit: r.reads, publie: r.publishes })
export const lireLecteurs = async (ecoleId) => (await appel(`/ecoles/${ecoleId}/news/readers`)).map(versLecteur)
export const changerLecteur = async (ecoleId, id, voit) =>
  versLecteur(await appel(`/ecoles/${ecoleId}/news/readers/${id}`, json('PUT', { reads: voit })))

export const changerOuverture = (ecoleId, valeur) =>
  appel(`/ecoles/${ecoleId}/news/settings`, json('PUT', { open_on_news: valeur }))

// --- Médias (étape 2) ---

export async function envoyerPhoto(ecoleId, fichier) {
  const corps = new FormData()
  corps.append('fichier', fichier)
  return (await appel(`/ecoles/${ecoleId}/news/photos`, { method: 'POST', body: corps })).photo
}

// « Publier » avec une vidéo : l'envoi par blocs (utils/videoUploads.js)
// devient une vidéo (voir finaliserTeleversement).
export async function attacherVideo(ecoleId, uploadId) {
  return videoVersEcran(await appel(`/ecoles/${ecoleId}/news/videos`, json('POST', { upload_id: uploadId })))
}

// La photo d'une actu, lue avec la session (comme les pièces jointes de la
// messagerie) ; gardée tant que l'appli est ouverte.
const photos = new Map()
export function lirePhoto(ecoleId, actuId, photo) {
  const chemin = `/ecoles/${ecoleId}/news/${actuId}/photos/${photo}`
  if (!photos.has(chemin)) {
    const promesse = fetch(`${BASE_URL}${chemin}`).then(async (reponse) => {
      if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
      return URL.createObjectURL(await reponse.blob())
    })
    promesse.catch(() => photos.delete(chemin))
    photos.set(chemin, promesse)
  }
  return photos.get(chemin)
}

// Compte Instagram relayé dans les actus (§6 bis).
const versInstagram = (r) => ({ relie: r.linked, compte: r.username, erreur: r.last_error, peutSeConnecter: r.can_sign_in })
export const lireInstagram = async (ecoleId) => versInstagram(await appel(`/ecoles/${ecoleId}/news/instagram`))
export const relierInstagram = async (ecoleId, cle) =>
  versInstagram(await appel(`/ecoles/${ecoleId}/news/instagram`, json('PUT', { token: cle })))
// « Se connecter avec Instagram » : l'adresse de la page d'Instagram.
export const connexionInstagram = async (ecoleId) =>
  (await appel(`/ecoles/${ecoleId}/news/instagram/login`, { method: 'POST' })).url
export const delierInstagram = async (ecoleId) =>
  versInstagram(await appel(`/ecoles/${ecoleId}/news/instagram`, { method: 'DELETE' }))
