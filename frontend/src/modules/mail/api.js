// Sous-module Mail (spec/modules/mail.md) — voir backend/src/mail/. L'état
// de la boîte : droit « Boîte mail du club », ou Administrateur principal ;
// connecter et déconnecter (Fonctionnalités) : l'Administrateur principal.
// Vérifié par le serveur.

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

// → { connected, address, provider, connected_at, cut, can_connect, can_read }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/mail`)
// → l'état, une fois que Google a accepté le code.
export const connecter = (ecoleId, address, code, provider) =>
  requete(`/ecoles/${ecoleId}/mail`, { method: 'PUT', body: JSON.stringify({ address, code, provider }) })
export const deconnecter = (ecoleId) => requete(`/ecoles/${ecoleId}/mail`, { method: 'DELETE' })

// L'état, ou null quand la personne ne voit pas la puce Mail (sous-module
// éteint : 404 ; pas le droit : 403).
export async function etatOuRien(ecoleId) {
  try {
    const lu = await etat(ecoleId)
    // L'Administrateur principal lit l'état sans le droit (Fonctionnalités).
    return lu.can_read ? lu : null
  } catch (e) {
    if (e.status === 403 || e.status === 404) return null
    throw e
  }
}

// --- Lire et ranger (spec §5, §6) ------------------------------------------

const base = (ecoleId) => `/ecoles/${ecoleId}/mail`
const json = (method, corps) => ({ method, body: JSON.stringify(corps) })

// → { address, folders: [{ key, label }], unread }
export const dossiers = (ecoleId) => requete(`${base(ecoleId)}/folders`)
// → { unread } (0 si la boîte n'est pas lisible)
export const nonLus = (ecoleId) => requete(`${base(ecoleId)}/unread`)
// → { folder, messages: [{ uid, subject, from, to, date, seen, starred, hasAttachments, snippet }], hasMore }
export function lister(ecoleId, dossier, { avant = null, recherche = '' } = {}) {
  const p = new URLSearchParams({ folder: dossier })
  if (avant != null) p.set('before', avant)
  if (recherche) p.set('q', recherche)
  return requete(`${base(ecoleId)}/messages?${p}`)
}
// → { subject, from, to, cc, date, html, text, attachments: [{ index, filename, size }], starred } ; le marque lu.
export const lire = (ecoleId, dossier, uid) => requete(`${base(ecoleId)}/messages/${dossier}/${uid}`)
export const drapeaux = (ecoleId, dossier, uid, changes) =>
  requete(`${base(ecoleId)}/messages/${dossier}/${uid}/flags`, json('PUT', changes))
// action : trash, archive, spam, inbox, delete, read, unread.
export const cocher = (ecoleId, dossier, uids, action) =>
  requete(`${base(ecoleId)}/bulk`, json('POST', { folder: dossier, uids, action }))

// Pièce jointe : téléchargée (jamais ouverte sur le domaine de l'appli).
export async function telecharger(ecoleId, dossier, uid, piece) {
  const reponse = await fetch(`${BASE_URL}${base(ecoleId)}/messages/${dossier}/${uid}/attachments/${piece.index}`)
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    throw new Error(typeof corps?.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
  }
  const url = URL.createObjectURL(await reponse.blob())
  const lien = document.createElement('a')
  lien.href = url
  lien.download = piece.filename
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

// Pastille des non lus à relire tout de suite (un mail lu ou remis non lu).
export const signalerNonLus = () => window.dispatchEvent(new Event('mail:non-lus'))
