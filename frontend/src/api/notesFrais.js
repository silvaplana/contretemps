// Notes de frais (module serveur `notes_frais`, voir
// spec/modules/notes-de-frais.md et backend/src/notes_frais/receiver.py).
// Les justificatifs ne sont jamais servis par une URL publique : on les lit
// avec la session (en-têtes ajoutés par api/identite.js), puis on les
// affiche par une URL locale (blob).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE = `${BASE_URL}/notes-frais`

export class ErreurNotesFrais extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

// Trésorier qui saisit pour quelqu'un (Financier › ⋯) : tant que c'est réglé,
// chaque appel se fait au nom de cette personne (en-tête lu par le serveur).
let pourPersonne = null
export function agirPour(personId) {
  pourPersonne = personId
}

function avecPersonne(options = {}) {
  if (pourPersonne === null) return options
  const headers = new Headers(options.headers)
  headers.set('X-Pour-Personne', String(pourPersonne))
  return { ...options, headers }
}

async function appel(chemin, options = {}) {
  const reponse = await fetch(`${BASE}${chemin}`, avecPersonne(options))
  if (!reponse.ok) {
    let message = `Requête échouée (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // réponse sans JSON : message par défaut
    }
    throw new ErreurNotesFrais(reponse.status, message)
  }
  return reponse.status === 204 ? null : reponse.json()
}

const json = (method, corps) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corps),
})

function fichier(f) {
  const donnees = new FormData()
  donnees.append('fichier', f, f.name || 'photo.jpg')
  return { method: 'POST', body: donnees }
}

// --- Membre ---

export const espace = () => appel('/moi')
export const compteurs = () => appel('/compteurs')
export const definirRib = (rib) => appel('/rib', json('PUT', rib))
// Lecture du ticket par l'IA : { date, montant_centimes, categorie_id,
// description } (champs absents = null). 422 si la photo n'est pas lisible.
export const lireTicket = (f) => appel('/lecture', fichier(f))
export const creerDepense = (d) => appel('/depenses', json('POST', d))
export const modifierDepense = (id, d) => appel(`/depenses/${id}`, json('PUT', d))
export const supprimerDepense = (id) => appel(`/depenses/${id}`, { method: 'DELETE' })
export const ajouterPiece = (depenseId, f) => appel(`/depenses/${depenseId}/pieces`, fichier(f))
export const supprimerPiece = (id) => appel(`/pieces/${id}`, { method: 'DELETE' })
export const envoyer = ({ depenseIds, titre, don, rib }) =>
  appel('/notes', json('POST', { depense_ids: depenseIds, titre, don, rib: rib ?? null }))
export const reprendre = (noteId) => appel(`/notes/${noteId}/reprendre`, { method: 'POST' })

export async function urlPiece(id) {
  const reponse = await fetch(`${BASE}/pieces/${id}`, avecPersonne())
  if (!reponse.ok) throw new ErreurNotesFrais(reponse.status, 'Justificatif introuvable')
  return URL.createObjectURL(await reponse.blob())
}

// --- Trésoriers ---

export const personnes = () => appel('/personnes')
export const tresorerie = (filtre) => appel(`/tresorerie?filtre=${filtre}`)
export const valider = (noteId) => appel(`/notes/${noteId}/valider`, { method: 'POST' })
export const refuser = (noteId, motif) => appel(`/notes/${noteId}/refuser`, json('POST', { motif }))
export const rembourser = (noteIds) => appel('/remboursements', json('POST', { note_ids: noteIds }))
export const categories = () => appel('/categories')
export const definirCategories = (libelles) => appel('/categories', json('PUT', { libelles }))

export const urlJustificatifs = (noteId) => `${BASE}/notes/${noteId}/justificatifs.zip`

export function urlExport(debut, fin) {
  const params = new URLSearchParams()
  if (debut) params.set('debut', debut)
  if (fin) params.set('fin', fin)
  const requete = params.toString()
  return `${BASE}/export.xlsx${requete ? `?${requete}` : ''}`
}

// --- Affichage ---

const FORMAT_EUROS = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
export const euros = (centimes) => FORMAT_EUROS.format((centimes ?? 0) / 100)

// "12,50" ou "12.5" -> 1250 ; null si illisible.
export function versCentimes(texte) {
  const propre = String(texte ?? '').replace(/\s|€/g, '').replace(',', '.')
  if (!/^\d+(\.\d{0,2})?$/.test(propre)) return null
  return Math.round(Number(propre) * 100)
}

export const versTexteMontant = (centimes) => (centimes == null ? '' : (centimes / 100).toFixed(2).replace('.', ','))

export function dateCourte(iso) {
  if (!iso) return ''
  return new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('fr-FR', {
    day: 'numeric',
    month: 'short',
  })
}

export const aujourdhui = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
