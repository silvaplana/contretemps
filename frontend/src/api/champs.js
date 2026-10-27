// Champs des membres (spec/core.md §4.3) — voir backend/src/members/. La
// fiche que l'école règle (Admin > Élèves > ⋮ > Champs) et les réponses
// d'une fiche. Réservé aux admins de l'école, vérifié par le serveur.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    ...options,
    headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json' },
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const detail = typeof corps?.detail === 'string' ? corps.detail : null
    throw new Error(detail ?? `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

const json = (method, corps) => ({ method, body: JSON.stringify(corps) })

// Les formats de la réponse, dans l'ordre de la liste (jamais « type » à l'écran).
export const FORMATS = [
  ['short_text', 'Texte court'],
  ['long_text', 'Texte long'],
  ['number', 'Nombre'],
  ['date', 'Date'],
  ['yes_no', 'Oui / non'],
  ['phone', 'Téléphone'],
  ['postal_code', 'Code postal'],
  ['file', 'Fichier à télécharger'],
  ['list', 'Liste déroulante'],
  ['group', 'Groupe'],
]
export const nomFormat = (cle) => FORMATS.find(([c]) => c === cle)?.[1] ?? cle

export const lister = (ecoleId) => requete(`/ecoles/${ecoleId}/champs`)
export const groupes = (ecoleId) => requete(`/ecoles/${ecoleId}/champs/groupes`)
export const creer = (ecoleId, champ) => requete(`/ecoles/${ecoleId}/champs`, json('POST', champ))
export const modifier = (id, champ) => requete(`/champs/${id}`, json('PATCH', champ))
export const retirer = (id) => requete(`/champs/${id}`, { method: 'DELETE' })
export const remettre = (id) => requete(`/champs/${id}/remettre`, { method: 'POST' })

export const toutesReponses = (ecoleId) => requete(`/ecoles/${ecoleId}/champs/reponses`)
export const colonnes = (ecoleId) => requete(`/ecoles/${ecoleId}/colonnes`)
export const changerColonnes = (ecoleId, liste) =>
  requete(`/ecoles/${ecoleId}/colonnes`, json('PUT', liste.map(({ key, shown }) => ({ key, shown }))))

export const reponses = (compteId) => requete(`/membres/${compteId}/champs`)
export const repondre = (compteId, champId, valeur) =>
  requete(`/membres/${compteId}/champs/${champId}`, json('PUT', { value: valeur }))

export function envoyerFichier(compteId, champId, fichier) {
  const donnees = new FormData()
  donnees.append('fichier', fichier, fichier.name)
  return requete(`/membres/${compteId}/champs/${champId}/fichier`, { method: 'POST', body: donnees })
}

export async function urlFichier(compteId, champId) {
  const reponse = await fetch(`${BASE_URL}/membres/${compteId}/champs/${champId}/fichier`)
  if (!reponse.ok) throw new Error('Fichier introuvable')
  return URL.createObjectURL(await reponse.blob())
}
