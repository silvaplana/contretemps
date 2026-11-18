// Module Essai (spec/modules/essai.md), voir backend/src/trials/.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, options)
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const detail = typeof corps?.detail === 'string' ? corps.detail : null
    throw new Error(detail ?? `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

const json = (method, corps) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps) })
const base = (ecoleId) => `/ecoles/${ecoleId}/trials`

// Admin > Essais (administrateurs).
export const reglages = (ecoleId) => requete(`${base(ecoleId)}/settings`)
export const enregistrerReglages = (ecoleId, r) => requete(`${base(ecoleId)}/settings`, json('PUT', r))
export const inscrits = (ecoleId) => requete(`${base(ecoleId)}/students`)
export const fiche = (ecoleId, id) => requete(`${base(ecoleId)}/students/${id}`)
export const modifier = (ecoleId, id, champs) => requete(`${base(ecoleId)}/students/${id}`, json('PATCH', champs))
export const supprimer = (ecoleId, id) => requete(`${base(ecoleId)}/students/${id}`, { method: 'DELETE' })
export const coursAujourdhui = (ecoleId, id) => requete(`${base(ecoleId)}/students/${id}/courses`, { method: 'POST' })

// Page publique, sans compte.
export const pagePublique = (orgId) => requete(`/trials/public/orgs/${orgId}/page`)
export const inscrire = (orgId, formulaire) =>
  requete(`/trials/public/orgs/${orgId}/registrations`, { method: 'POST', body: formulaire })
