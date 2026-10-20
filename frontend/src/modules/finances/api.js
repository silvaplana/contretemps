// Comptes (module serveur `finances`, voir spec/modules/financier.md et
// backend/src/finances/receiver.py). Session et école choisie ajoutées par
// api/identite.js.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const BASE = `${BASE_URL}/finances`

async function appel(chemin, options = {}) {
  const reponse = await fetch(`${BASE}${chemin}`, options)
  if (!reponse.ok) {
    let message = `Requête échouée (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // réponse sans JSON : message par défaut
    }
    throw new Error(message)
  }
  return reponse.status === 204 ? null : reponse.json()
}

// Historique de tous les comptes (accountId absent) ou d'un seul.
export const historique = (accountId) => appel(accountId ? `/ledger?account=${accountId}` : '/ledger')

// Relevés PDF ou archives : compte rendu { imported, skipped, errors }.
export function importerReleves(fichiers) {
  const body = new FormData()
  for (const fichier of fichiers) body.append('files', fichier)
  return appel('/import', { method: 'POST', body })
}

// Saisons de l'école : { seasons: [{ id, name, startDate, endDate, current }], today }.
export const saisons = () => appel('/seasons')

export function euros(montant) {
  return `${montant.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
}

export function dateFr(isoDate) {
  const [year, month, day] = isoDate.split('-')
  return `${day}/${month}/${year}`
}

// --- Bilan (sous-module, spec §4) ---

const json = (method, corps) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps) })

// Bilans de la saison, modèles et états possibles, nombre de bilans par saison.
export const bilans = (seasonId) => appel(`/reports?seasonId=${seasonId}`)
export const bilan = (id) => appel(`/reports/${id}`)
export const creerBilan = (donnees) => appel('/reports', json('POST', donnees))
export const modifierBilan = (id, donnees) => appel(`/reports/${id}`, json('PUT', donnees))
export const supprimerBilan = (id) => appel(`/reports/${id}`, { method: 'DELETE' })
// Lance le calcul (tableau + analyse) : le bilan revient en « running ».
export const calculerBilan = (id, donnees) => appel(`/reports/${id}/run`, json('POST', donnees))
export const urlTelechargementBilan = (id, format) => `${BASE}/reports/${id}/download?format=${format}`

// --- Assemblée générale (sous-module, spec §5) ---

const fichier = (chemin, f) => {
  const body = new FormData()
  body.append('file', f)
  return appel(chemin, { method: 'POST', body })
}

// AG de la saison, modèles et états, bilan et PowerPoint modèle par défaut,
// nombre d'AG par saison.
export const assemblees = (seasonId) => appel(`/assemblies?seasonId=${seasonId}`)
export const assemblee = (id) => appel(`/assemblies/${id}`)
export const creerAssemblee = (donnees) => appel('/assemblies', json('POST', donnees))
export const modifierAssemblee = (id, donnees) => appel(`/assemblies/${id}`, json('PUT', donnees))
export const supprimerAssemblee = (id) => appel(`/assemblies/${id}`, { method: 'DELETE' })
// Lance la préparation du PowerPoint : l'AG revient en « running ».
export const produireAssemblee = (id, donnees) => appel(`/assemblies/${id}/run`, json('POST', donnees))
// PowerPoint retouché par le trésorier, PowerPoint modèle de l'AG, modèle général de l'école.
export const envoyerPptModifie = (id, f) => fichier(`/assemblies/${id}/upload`, f)
export const envoyerPptModele = (id, f) => fichier(`/assemblies/${id}/model`, f)
export const envoyerModeleGeneral = (f) => fichier('/assemblies/template', f)
export const copierPptModele = (id, sourceId, kind) => appel(`/assemblies/${id}/model`, json('PUT', { sourceId, kind }))
export const sourcesDeModele = (exclude) => appel(`/assemblies/model-sources${exclude == null ? '' : `?exclude=${exclude}`}`)
export const urlTelechargementAssemblee = (id, kind) => `${BASE}/assemblies/${id}/download${kind ? `?kind=${kind}` : ''}`
export const diapos = (id, kind) => appel(`/assemblies/${id}/files/${kind}/slides`)
export const urlDiapo = (id, kind, image) => `${BASE}/assemblies/${id}/files/${kind}/slides/${image}.png`
