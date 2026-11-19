// Drives du club (spec/core.md §3) — voir backend/src/drives/. Connecter,
// renommer, déconnecter : l'Administrateur principal ; parcourir : lui et
// l'Accès au Financier. Vérifié par le serveur.

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

const avecDrive = (drive) => (drive != null ? `drive=${drive}` : '')

// → { connected, can_connect, google_address, drives: [{ id, name, provider, address, connected_at, cut }] }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/drives`)
// Sans `drive` : ajoute un drive ; avec : le reconnecte ou le remplace.
export const connecter = (ecoleId, { drive, name, provider, address, code, driveRef }) =>
  requete(`/ecoles/${ecoleId}/drives?${avecDrive(drive)}`, {
    method: 'PUT',
    body: JSON.stringify({ provider, address, code: code ?? '', drive_ref: driveRef ?? '', name: name ?? '' }),
  })
export const renommer = (ecoleId, drive, name) =>
  requete(`/ecoles/${ecoleId}/drives?${avecDrive(drive)}`, { method: 'PATCH', body: JSON.stringify({ name }) })
export const deconnecter = (ecoleId, drive) =>
  requete(`/ecoles/${ecoleId}/drives?${avecDrive(drive)}`, { method: 'DELETE' })
// → [{ name, path, is_dir, size, modified }]
export const lister = (ecoleId, drive, path = '') =>
  requete(`/ecoles/${ecoleId}/drives/${drive}/list?path=${encodeURIComponent(path)}`)
