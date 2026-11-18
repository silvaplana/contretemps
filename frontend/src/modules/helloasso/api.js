// Connexion HelloAsso de l'école (spec/modules/helloasso.md §2) — voir
// backend/src/helloasso/. Administrateur principal et Super User seulement,
// vérifié par le serveur.

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

// { connected, org_name, connected_at }
export const etat = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso`)
// → { name, forms } ; tester n'enregistre rien.
export const tester = (ecoleId, cles) => requete(`/ecoles/${ecoleId}/helloasso/tester`, json('POST', cles))
export const retester = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/retester`, { method: 'POST' })
export const enregistrer = (ecoleId, cles) => requete(`/ecoles/${ecoleId}/helloasso`, json('PUT', cles))
export const deconnecter = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso`, { method: 'DELETE' })
export const reprendre = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/reprendre`, { method: 'POST' })

// La campagne de la saison affichée (spec §3) : tout admin la lit ;
// la choisir est réservé à l'Administrateur principal, saison courante.
// → { connected, can_change, form, forms: [{ form_type, form_slug, name, state }], error }
export const campagne = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/campagne`)
export const choisirCampagne = (ecoleId, form) => requete(`/ecoles/${ecoleId}/helloasso/campagne`, json('PUT', form))
export const nosChamps = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/campagne`, { method: 'DELETE' })
// « Synchroniser maintenant » (spec §4) : tout admin, saison en cours.
// → { created, completed, updated, gone }
// Les tarifs de la campagne de la saison affichée, en lecture seule.
// → { campaign, form_name, plans, options, codes, error }
export const tarifs = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/tarifs`)
export const synchroniser = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/synchroniser`, { method: 'POST' })

// Adhérents imposés par HelloAsso (spec §7) : la saison affichée.
// → { imposed, form_name, can_refresh, members: { [fiche]: { amount, discount_code, state, cancelled, photo } } }
export const adherents = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/adherents`)
// → { tier_name, amount, discount_code, state, cancelled, order_date, photo, files, answers, payer_name, payer_email, payments }
export const adherent = (ecoleId, ficheId) => requete(`/ecoles/${ecoleId}/helloasso/adherents/${ficheId}`)

// Photo et documents déposés sur HelloAsso, relayés par le serveur : une
// URL locale (blob), la session passant par fetch (api/identite.js).
async function blob(chemin) {
  const reponse = await fetch(`${BASE_URL}${chemin}`)
  if (!reponse.ok) throw new Error('Fichier introuvable')
  return URL.createObjectURL(await reponse.blob())
}
export const urlPhoto = (ecoleId, ficheId, taille) =>
  blob(`/ecoles/${ecoleId}/helloasso/adherents/${ficheId}/photo?size=${taille}`)
export const urlFichier = (ecoleId, ficheId, index) =>
  blob(`/ecoles/${ecoleId}/helloasso/adherents/${ficheId}/fichiers/${index}`)
