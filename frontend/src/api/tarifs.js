// Tarifs de la saison (spec/core.md §9) — voir backend/src/plans/. Les
// formules : nom, tarif et échéances ; les options et codes promo. Montants
// en centimes côté serveur (centièmes de % pour un pourcentage).
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

// { read_only, plans, adjustments, previous: { name, plans, adjustments } | null }
export const lister = (ecoleId) => requete(`/ecoles/${ecoleId}/tarifs`)
export const creer = (ecoleId, formule) => requete(`/ecoles/${ecoleId}/tarifs/formules`, json('POST', formule))
// → { plans, adjustments } recopiés
export const reprendre = (ecoleId) => requete(`/ecoles/${ecoleId}/tarifs/reprendre`, { method: 'POST' })
export const modifier = (id, formule) => requete(`/tarifs/formules/${id}`, json('PUT', formule))
export const dupliquer = (id) => requete(`/tarifs/formules/${id}/dupliquer`, { method: 'POST' })
export const retirer = (id) => requete(`/tarifs/formules/${id}`, { method: 'DELETE' })
export const creerOption = (ecoleId, option) => requete(`/ecoles/${ecoleId}/tarifs/options`, json('POST', option))
export const modifierOption = (id, option) => requete(`/tarifs/options/${id}`, json('PUT', option))
// « Faire comprendre la règle » → { understood, calculation, example }
export const comprendre = (ecoleId, regle) => requete(`/ecoles/${ecoleId}/tarifs/regle`, json('POST', regle))
export const retirerOption = (id) => requete(`/tarifs/options/${id}`, { method: 'DELETE' })
