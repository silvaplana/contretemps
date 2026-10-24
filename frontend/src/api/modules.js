// Modules allumés ou éteints pour une école (spec/core.md §9 bis.3) — voir
// api/README.md pour le principe général. Lus par tous les membres (onglets
// à montrer) ; seul le Super User les change (Supervision).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    throw new Error(typeof corps?.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
  }
  return reponse.json()
}

// [{ key, label, requires, enabled }], dans l'ordre de la liste de l'appli.
export function lister(ecoleId) {
  return requete(`/ecoles/${ecoleId}/modules`)
}

// Renvoie la liste à jour (allumer un module allume aussi ceux dont il a besoin).
export function changer(ecoleId, key, enabled) {
  return requete(`/ecoles/${ecoleId}/modules/${key}`, { method: 'PUT', body: JSON.stringify({ enabled }) })
}
