// Publications (voir spec/modules/actualites.md §8 et §12, et
// backend/src/publications/receiver.py). Session et école choisie ajoutées
// par api/identite.js. `lieu` : { ecoleId, blogId }, le blog ouvert.
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
    // empreinte), une vidéo ou un lien (avec son titre et l'image du site
    // en photo).
    media: n.media.map((m) => ({
      photo: m.photo,
      video: m.video ? videoVersEcran(m.video) : null,
      lien: m.link,
      titre: m.title,
    })),
    document: n.document, // { id, name } ou null
    // Blog avec catégories (§12.6) : son nom, sa catégorie puis sa
    // sous-catégorie ({ id, nom }).
    titre: n.title ?? '',
    categories: n.categories.map((c) => ({ id: c.id, nom: c.name })),
  }
}

const versServeur = (a) => ({
  level: a.niveau,
  body: a.texte,
  on_top_until: a.niveau === 'important' ? a.enHautJusquau : null,
  notify: a.notifier,
  publish: a.publier,
  media: a.media.map((m) => {
    if (m.lien) return { link: m.lien, title: m.titre, photo: m.photo ?? null }
    return m.photo ? { photo: m.photo } : { video_id: m.video.id }
  }),
  document_id: a.document?.id ?? null,
  title: a.titre || null,
  category: a.categorie || null,
  subcategory: a.sousCategorie || null,
})

const blogs = (ecoleId) => `/ecoles/${ecoleId}/publications/blogs`
const blog = (lieu) => `${blogs(lieu.ecoleId)}/${lieu.blogId}`

// --- Les blogs de l'école (§12.2, §12.3) ---

const versBlog = (b) => ({
  id: b.id,
  nom: b.name,
  icone: b.icon,
  avecNiveaux: b.with_levels,
  avecCategories: b.with_categories,
  peutLire: b.can_read,
  peutPublier: b.can_publish,
  // L'appli s'ouvre dessus (un blog au plus), s'il a une publication.
  ouvrirAppli: b.open_app_on && b.has_posts,
  dernierePublication: b.latest_post,
})

// Module éteint ou erreur : aucun blog.
export async function lireBlogs(ecoleId) {
  try {
    return (await appel(blogs(ecoleId))).map(versBlog)
  } catch {
    return []
  }
}

// Admin › École › Fonctionnalités : nom, logo, catégories, niveaux.
export const ajouterBlog = async (ecoleId, nom) => versBlog(await appel(blogs(ecoleId), json('POST', { name: nom })))
export const changerBlog = async (ecoleId, blogId, changement) =>
  versBlog(await appel(`${blogs(ecoleId)}/${blogId}`, json('PUT', changement)))
export const supprimerBlog = (ecoleId, blogId) => appel(`${blogs(ecoleId)}/${blogId}`, { method: 'DELETE' })

// Le blog sur lequel l'appli s'ouvre (§6), parmi ceux qu'on lit. Ouverte
// deux fois dessus avec la même dernière publication, elle a été vue : on
// ne s'y rouvre plus avant la suivante (Seb, 12 novembre). Compté sur
// l'appareil.
// Une seule décision par lancement (l'effet peut être rejoué).
const OUVERTURES = 2
const decisions = new Map()
export function blogAOuvrir(ecoleId) {
  if (!decisions.has(ecoleId)) decisions.set(ecoleId, decider(ecoleId))
  return decisions.get(ecoleId)
}
async function decider(ecoleId) {
  const b = (await lireBlogs(ecoleId)).find((x) => x.peutLire && x.ouvrirAppli)
  if (!b) return null
  const cle = `publications.ouvertures.${ecoleId}.${b.id}`
  let deja = null
  try {
    deja = JSON.parse(localStorage.getItem(cle))
  } catch {
    deja = null
  }
  const fois = deja?.publication === b.dernierePublication ? deja.fois : 0
  if (fois >= OUVERTURES) return null
  try {
    localStorage.setItem(cle, JSON.stringify({ publication: b.dernierePublication, fois: fois + 1 }))
  } catch {
    // Stockage refusé : on s'ouvre sur le blog à chaque fois, comme avant.
  }
  return b
}

// --- Les publications d'un blog ---

export async function lireActus(lieu) {
  const r = await appel(blog(lieu))
  return {
    peutPublier: r.can_publish,
    mediaEnHaut: r.media_first,
    actus: r.items.map(versEcran),
    brouillons: r.drafts.map(versEcran),
  }
}

export async function enregistrer(lieu, actu) {
  const r = actu.id
    ? await appel(`${blog(lieu)}/posts/${actu.id}`, json('PUT', versServeur(actu)))
    : await appel(`${blog(lieu)}/posts`, json('POST', versServeur(actu)))
  return versEcran(r)
}

export const depublier = (lieu, id) => appel(`${blog(lieu)}/posts/${id}/unpublish`, { method: 'POST' })
export const supprimer = (lieu, id) => appel(`${blog(lieu)}/posts/${id}`, { method: 'DELETE' })

// --- Catégories (§12.6) : [{ id, nom, nombre, sous: [...] }] ---

const versCategorie = (c) => ({ id: c.id, nom: c.name, nombre: c.count, sous: c.children.map(versCategorie) })
export const lireCategories = async (lieu) => (await appel(`${blog(lieu)}/categories`)).map(versCategorie)
// Le nom d'une autre catégorie du même niveau réunit les deux.
export const renommerCategorie = async (lieu, id, nom) =>
  (await appel(`${blog(lieu)}/categories/${id}`, json('PUT', { name: nom }))).map(versCategorie)

// --- Paramètres du blog (§12.5) ---

const versReglages = (r) => ({
  ouvrir: r.open_app_on,
  mediaEnHaut: r.media_first,
  pourTous: r.visible_to_all,
  hashtag: r.instagram_hashtag,
  publier: r.instagram_publish,
})
export const lireReglages = async (lieu) => versReglages(await appel(`${blog(lieu)}/settings`))
const changerReglage = (lieu, changement) => appel(`${blog(lieu)}/settings`, json('PUT', changement))
// « L'appli affiche toujours <blog> à son ouverture » : éteint dans les autres.
export const changerOuverture = (lieu, valeur) => changerReglage(lieu, { open_app_on: valeur })
// « … visibles par tout le monde » (§2 bis).
export const changerPourTous = (lieu, valeur) => changerReglage(lieu, { visible_to_all: valeur })
// « En haut de chaque billet : Texte | Photo, vidéo » (§4.1).
export const changerMediaEnHaut = (lieu, valeur) => changerReglage(lieu, { media_first: valeur })

// --- Médias ---

export async function envoyerPhoto(lieu, fichier) {
  const corps = new FormData()
  corps.append('fichier', fichier)
  return (await appel(`${blog(lieu)}/photos`, { method: 'POST', body: corps })).photo
}

// Un lien (YouTube ou autre site) : le serveur lit son titre et son image.
export async function ajouterLien(lieu, url) {
  const r = await appel(`${blog(lieu)}/links`, json('POST', { url }))
  return { lien: r.link, titre: r.title, photo: r.photo, photoLocale: r.preview }
}

// « Publier » avec une vidéo : l'envoi par blocs (utils/videoUploads.js)
// devient une vidéo (voir finaliserTeleversement).
export async function attacherVideo(lieu, uploadId) {
  return videoVersEcran(await appel(`${blog(lieu)}/videos`, json('POST', { upload_id: uploadId })))
}

// La photo d'une publication, lue avec la session (comme les pièces jointes
// de la messagerie) ; gardée tant que l'appli est ouverte.
const photos = new Map()
export function lirePhoto(lieu, actuId, photo) {
  const chemin = `${blog(lieu)}/posts/${actuId}/photos/${photo}`
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

// Compte Instagram relayé (§6 bis) : celui de l'école, dans le blog où on
// l'a relié (`ailleurs` : le nom de cet autre blog).
const versInstagram = (r) => ({
  relie: r.linked,
  compte: r.username,
  erreur: r.last_error,
  peutSeConnecter: r.can_sign_in,
  ailleurs: r.elsewhere,
  signataire: r.signer_id,
})
export const lireInstagram = async (lieu) => versInstagram(await appel(`${blog(lieu)}/instagram`))
export const relierInstagram = async (lieu, cle) => versInstagram(await appel(`${blog(lieu)}/instagram`, json('PUT', { token: cle })))
// « Se connecter avec Instagram » : l'adresse de la page d'Instagram.
export const connexionInstagram = async (lieu) => (await appel(`${blog(lieu)}/instagram/login`, { method: 'POST' })).url
// « Seulement les posts avec # » (§6 bis) : vide, tous les nouveaux posts.
// « Les publier tout de suite » : sinon, ils arrivent en brouillon.
export const lireTriInstagram = async (lieu) => versReglages(await appel(`${blog(lieu)}/settings`))
export const changerTriInstagram = async (lieu, changement) => versReglages(await changerReglage(lieu, changement))
// « Signé par » (Seb, 13 novembre) : un membre de l'école, dont le prénom
// signe les posts reçus.
export const lireSignatairesInstagram = (lieu) => appel(`${blog(lieu)}/instagram/signers`)
export const changerSignataireInstagram = async (lieu, membreId) =>
  versInstagram(await appel(`${blog(lieu)}/instagram/signer`, json('PUT', { member_id: membreId })))
export const delierInstagram = async (lieu) => versInstagram(await appel(`${blog(lieu)}/instagram`, { method: 'DELETE' }))
