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

// Plusieurs boîtes par école (spec §4 bis) : `boite` est le numéro d'une
// boîte (`boxes[].id`) ; toutes les routes de lecture la prennent.
const avecBoite = (boite) => (boite != null ? `box=${boite}` : '')

// → { connected, can_connect, can_read, boxes: [{ id, name, address, provider, connected_at, cut }] }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/mail`)
// → l'état, une fois que le fournisseur a accepté le code. Sans `boite` :
// ajoute une boîte (nommée `name`) ; avec : la reconnecte ou la remplace.
export const connecter = (ecoleId, { boite, name, address, code, provider }) =>
  requete(`/ecoles/${ecoleId}/mail?${avecBoite(boite)}`, {
    method: 'PUT',
    body: JSON.stringify({ address, code, provider, name: name ?? '' }),
  })
export const renommer = (ecoleId, boite, name) =>
  requete(`/ecoles/${ecoleId}/mail?${avecBoite(boite)}`, { method: 'PATCH', body: JSON.stringify({ name }) })
export const deconnecter = (ecoleId, boite) =>
  requete(`/ecoles/${ecoleId}/mail?${avecBoite(boite)}`, { method: 'DELETE' })

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
export const dossiers = (ecoleId, boite) => requete(`${base(ecoleId)}/folders?${avecBoite(boite)}`)
// → { unread, boxes: [{ id, unread }] } : le total et chaque boîte (0 si pas lisible)
export const nonLus = (ecoleId) => requete(`${base(ecoleId)}/unread`)
// → { folder, messages: [{ uid, subject, from, to, date, seen, starred, hasAttachments, snippet }], hasMore }
export function lister(ecoleId, boite, dossier, { avant = null, recherche = '' } = {}) {
  const p = new URLSearchParams({ folder: dossier, box: boite })
  if (avant != null) p.set('before', avant)
  if (recherche) p.set('q', recherche)
  return requete(`${base(ecoleId)}/messages?${p}`)
}
// → { subject, from, to, cc, date, html, text, attachments: [{ index, filename, size }], starred } ; le marque lu.
export const lire = (ecoleId, boite, dossier, uid) =>
  requete(`${base(ecoleId)}/messages/${dossier}/${uid}?${avecBoite(boite)}`)
export const drapeaux = (ecoleId, boite, dossier, uid, changes) =>
  requete(`${base(ecoleId)}/messages/${dossier}/${uid}/flags?${avecBoite(boite)}`, json('PUT', changes))
// action : trash, archive, spam, inbox, delete, read, unread.
export const cocher = (ecoleId, boite, dossier, uids, action) =>
  requete(`${base(ecoleId)}/bulk?${avecBoite(boite)}`, json('POST', { folder: dossier, uids, action }))

// Pièce jointe : téléchargée (jamais ouverte sur le domaine de l'appli).
export async function telecharger(ecoleId, boite, dossier, uid, piece) {
  const reponse = await fetch(
    `${BASE_URL}${base(ecoleId)}/messages/${dossier}/${uid}/attachments/${piece.index}?${avecBoite(boite)}`,
  )
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

// Écrire (spec §7) : formulaire multipart (pièces jointes), comme Sambo Admin.
export async function envoyer(ecoleId, boite, b, fichiers) {
  const form = new FormData()
  for (const cle of ['to', 'cc', 'bcc', 'subject', 'body']) form.set(cle, b[cle] ?? '')
  if (b.inReplyTo) form.set('inReplyTo', b.inReplyTo)
  if (b.references) form.set('references', b.references)
  if (b.answered) {
    form.set('answeredFolder', b.answered.folder)
    form.set('answeredUid', b.answered.uid)
  }
  if (b.forward) {
    form.set('forwardFolder', b.forward.folder)
    form.set('forwardUid', b.forward.uid)
  }
  fichiers.forEach((f) => form.append('files', f))
  const reponse = await fetch(`${BASE_URL}${base(ecoleId)}/send?${avecBoite(boite)}`, { method: 'POST', body: form })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const erreur = new Error(typeof corps?.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
    erreur.status = reponse.status
    throw erreur
  }
  return reponse.json()
}

// Suggestions pour À, Cc, Cci : gens de l'école et adresses déjà échangées.
export const contacts = (ecoleId, boite) => requete(`${base(ecoleId)}/contacts?${avecBoite(boite)}`)

// Écrire aux adhérents (spec §7 bis) : → { season, people, without, courses: [{ id, name, people }] }
export const adherents = (ecoleId) => requete(`${base(ecoleId)}/members`)
// Un mail à chacun par Brevo ; `courses` vide : tous. → { people, sent }
export const ecrireAuxAdherents = (ecoleId, boite, { courses, subject, body }) =>
  requete(`${base(ecoleId)}/members/send?${avecBoite(boite)}`, json('POST', { courses, subject, body }))
