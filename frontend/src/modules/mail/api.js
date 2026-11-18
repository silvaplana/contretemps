// Sous-module Mail (spec/modules/mail.md) — voir backend/src/mail/. L'état
// de la boîte : droit « Boîte mail du club » ; connecter et déconnecter :
// l'Administrateur principal qui a ce droit. Vérifié par le serveur.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    ...options,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const detail = typeof corps?.detail === 'string' ? corps.detail : null
    const erreur = new Error(detail ?? `Requête échouée (${reponse.status})`)
    erreur.status = reponse.status
    throw erreur
  }
  return reponse.status === 204 ? null : reponse.json()
}

// → { connected, address, connected_at, cut, can_connect }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/mail`)
// → l'état, une fois que Google a accepté le code.
export const connecter = (ecoleId, address, code) =>
  requete(`/ecoles/${ecoleId}/mail`, { method: 'PUT', body: JSON.stringify({ address, code }) })
export const deconnecter = (ecoleId) => requete(`/ecoles/${ecoleId}/mail`, { method: 'DELETE' })

// L'état, ou null quand la personne ne voit pas la puce Mail (sous-module
// éteint : 404 ; pas le droit : 403).
export async function etatOuRien(ecoleId) {
  try {
    return await etat(ecoleId)
  } catch (e) {
    if (e.status === 403 || e.status === 404) return null
    throw e
  }
}
