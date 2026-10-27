// Tarifs de la saison (spec/core.md §9) — voir backend/src/plans/. Les
// formules : nom, tarif et échéances, montants en centimes côté serveur.
// Réservé aux admins de l'école, vérifié par le serveur.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    ...options,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const detail = typeof corps?.detail === 'string' ? corps.detail : null
    throw new Error(detail ?? `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

const json = (method, corps) => ({ method, body: JSON.stringify(corps) })

// { read_only, plans, previous: { name, plans } | null }
export const lister = (ecoleId) => requete(`/ecoles/${ecoleId}/tarifs`)
export const creer = (ecoleId, formule) => requete(`/ecoles/${ecoleId}/tarifs/formules`, json('POST', formule))
export const reprendre = (ecoleId) => requete(`/ecoles/${ecoleId}/tarifs/reprendre`, { method: 'POST' })
export const modifier = (id, formule) => requete(`/tarifs/formules/${id}`, json('PUT', formule))
export const dupliquer = (id) => requete(`/tarifs/formules/${id}/dupliquer`, { method: 'POST' })
export const retirer = (id) => requete(`/tarifs/formules/${id}`, { method: 'DELETE' })
