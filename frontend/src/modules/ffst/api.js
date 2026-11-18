// Module FFST (spec/modules/ffst.md) — voir backend/src/ffst/. Les
// identifiants du club : Administrateur principal et Super User ; les
// listes et les statuts : tout admin. Vérifié par le serveur.

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
  return reponse.json()
}

const json = (method, corps) => ({ method, body: JSON.stringify(corps) })

// → { connected, login: '21 / 13 / 1230', connected_at }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/ffst`)
// identifiants : { part1, part2, part3, password } → { licensees } ; tester n'enregistre rien.
export const tester = (ecoleId, identifiants) => requete(`/ecoles/${ecoleId}/ffst/tester`, json('POST', identifiants))
export const retester = (ecoleId) => requete(`/ecoles/${ecoleId}/ffst/retester`, { method: 'POST' })
export const enregistrer = (ecoleId, identifiants) => requete(`/ecoles/${ecoleId}/ffst`, json('PUT', identifiants))

// La copie de la dernière lecture du site (spec §3).
// → { connected, read_at, lists: { licensees, validated, drafts }, error }
export const listes = (ecoleId) => requete(`/ecoles/${ecoleId}/ffst/listes`)
// « Rafraîchir » : relit le site ; s'il ne répond pas, la copie revient avec `error`.
export const lire = (ecoleId) => requete(`/ecoles/${ecoleId}/ffst/lire`, { method: 'POST' })
// Le statut FFST de chaque fiche (spec §4) → { connected, read_at, members: { [fiche]: { status } } }
export const adherents = (ecoleId) => requete(`/ecoles/${ecoleId}/ffst/adherents`)
