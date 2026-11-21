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
    const erreur = new Error(detail ?? `Requête échouée (${reponse.status})`)
    erreur.status = reponse.status
    throw erreur
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
// la choisir est réservé à l'Administrateur principal, toute saison.
// → { connected, can_change, form, forms: [{ form_type, form_slug, name, state }], error }
// `relire` : redemande la liste à HelloAsso (sinon gardée 10 minutes).
export const campagne = (ecoleId, relire = false) =>
  requete(`/ecoles/${ecoleId}/helloasso/campagne${relire ? '?relire=1' : ''}`)
export const choisirCampagne = (ecoleId, form) => requete(`/ecoles/${ecoleId}/helloasso/campagne`, json('PUT', form))
export const nosChamps = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/campagne`, { method: 'DELETE' })
// « Synchroniser maintenant » (spec §4) : tout admin, saison affichée.
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

// Comment la saison affichée utilise HelloAsso (spec §8.1).
// → { connected, mode: 'master' | 'payment' | 'none', season_name, can_change, form }
export const saison = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/saison`)
// « L'appli fait tout, HelloAsso encaisse » ('payment') ou « Sans HelloAsso » ('none') ;
// « HelloAsso fait tout » se choisit avec sa campagne (choisirCampagne).
export const choisirSaison = (ecoleId, mode) => requete(`/ecoles/${ecoleId}/helloasso/saison`, json('PUT', { mode }))

// Admin > Impayés HelloAsso (spec §7.4) → { campaign, members: [{ member_id,
// first_name, last_name, email, total, unpaid, refused: [{ date, amount }] }] }.
export const impayes = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/impayes`)

// Contact et résiliation (spec §7.6, §7.7).
const adherentUrl = (ecoleId, ficheId) => `/ecoles/${ecoleId}/helloasso/adherents/${ficheId}`
export const envoyerMail = (ecoleId, ficheId, subject, message) =>
  requete(`${adherentUrl(ecoleId, ficheId)}/mail`, json('POST', { subject, message }))
// → { phone } : l'écran ouvre l'appli SMS du téléphone.
export const preparerSms = (ecoleId, ficheId, message) =>
  requete(`${adherentUrl(ecoleId, ficheId)}/sms`, json('POST', { message }))
export const resiliation = (ecoleId, ficheId) => requete(`${adherentUrl(ecoleId, ficheId)}/resiliation`)
export const resilier = (ecoleId, ficheId) => requete(`${adherentUrl(ecoleId, ficheId)}/resilier`, { method: 'POST' })
// Messages préenregistrés, `kind` 'mail' ou 'sms' → [{ id, subject, body }].
export const messages = (ecoleId, kind) => requete(`/ecoles/${ecoleId}/helloasso/messages?kind=${kind}`)
export const garderMessage = (ecoleId, kind, subject, body) =>
  requete(`/ecoles/${ecoleId}/helloasso/messages`, json('POST', { kind, subject, body }))
export const retirerMessage = (ecoleId, kind, id) =>
  requete(`/ecoles/${ecoleId}/helloasso/messages/${id}?kind=${kind}`, { method: 'DELETE' })

// Vérification des dossiers et « Nouvel adhérent » (spec §7.5).
export const reglages = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/reglages`)
export const regler = (ecoleId, checkFiles, notifyNew) =>
  requete(`/ecoles/${ecoleId}/helloasso/reglages`, json('PUT', { check_files: checkFiles, notify_new: notifyNew }))
// → { on, running, to_check, cost (dollars), can_run }.
export const verification = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/verification`)
// Statistiques de la saison affichée (spec §7.8) ; soldes et projection à null
// sans l'Accès au Financier.
export const statistiques = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/statistiques`)
export const verifier = (ecoleId) => requete(`/ecoles/${ecoleId}/helloasso/verification`, { method: 'POST' })
export const validerDossier = (ecoleId, ficheId) =>
  requete(`/ecoles/${ecoleId}/helloasso/adherents/${ficheId}/valider`, { method: 'POST' })
export const devaliderDossier = (ecoleId, ficheId) =>
  requete(`/ecoles/${ecoleId}/helloasso/adherents/${ficheId}/valider`, { method: 'DELETE' })
