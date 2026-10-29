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

// Connexion bancaire (backend/src/finances/bank.py) : { configured,
// connected, bank, psuType, validUntil, lastSyncAt, lastError, accounts }.
export const banque = () => appel('/bank')
export const banques = (q) => appel(`/bank/banks?q=${encodeURIComponent(q)}`)
// L'adresse de la banque où aller s'identifier : { url }.
export const connecterBanque = (bank, psuType) => appel('/bank/connect', json('POST', { bank, psuType }))
export const suivreComptes = (uids) => appel('/bank/accounts', json('PUT', { uids }))
export const actualiserBanque = () => appel('/bank/sync', { method: 'POST' })
export const renommerCompte = (id, name) => appel(`/accounts/${id}`, json('PUT', { name }))

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

// --- Prévisionnel (sous-module, spec §6) ---

// Prévisionnels de la saison, modèles et états possibles, nombre par saison.
export const previsionnels = (seasonId) => appel(`/forecasts?seasonId=${seasonId}`)
export const previsionnel = (id) => appel(`/forecasts/${id}`)
export const creerPrevisionnel = (donnees) => appel('/forecasts', json('POST', donnees))
export const modifierPrevisionnel = (id, donnees) => appel(`/forecasts/${id}`, json('PUT', donnees))
export const supprimerPrevisionnel = (id) => appel(`/forecasts/${id}`, { method: 'DELETE' })
// Lance le calcul (formule + courbe) : le prévisionnel revient en « running ».
export const calculerPrevisionnel = (id, donnees) => appel(`/forecasts/${id}/run`, json('POST', donnees))
// Rejoue la formule avec la position des curseurs (sans rappeler le modèle).
export const reglerPrevisionnel = (id, params) => appel(`/forecasts/${id}/params`, json('PUT', { params }))
// Image (png) ou PDF, avec les saisons comparées à l'écran.
export const urlTelechargementPrevisionnel = (id, format, seasonIds) =>
  `${BASE}/forecasts/${id}/download?format=${format}&seasons=${seasonIds.join(',')}`

// --- Comptabilité (spec §8) : plan comptable, compte sur chaque ligne, caisse ---

// { level, natures: [{ id, label }], accounts: [{ id, number, label, nature, event, keywords, active, used }] }.
export const planComptable = () => appel('/chart')
export const choisirNiveau = (level) => appel('/chart/level', json('PUT', { level }))
export const creerCompte = (donnees) => appel('/chart', json('POST', donnees))
export const modifierCompte = (id, donnees) => appel(`/chart/${id}`, json('PUT', donnees))
export const supprimerCompte = (id) => appel(`/chart/${id}`, { method: 'DELETE' })
// Fiche d'une opération : { id, date, label, details, amount, bankAccount, transfer, lines, proposal, piece, level }.
export const operation = (id) => appel(`/operations/${id}`)
// Ventilation confirmée : [{ accountId, amount }] ; une seule ligne = tout le montant ; vide = compte retiré.
export const ventiler = (id, lines) => appel(`/operations/${id}/accounts`, json('PUT', { lines }))
// Caisse : { balance, asOf, lines: [{ id, date, label, amount, account, transferOperationId }] }.
export const caisse = () => appel('/cash')
export const ajouterLigneCaisse = (donnees) => appel('/cash', json('POST', donnees))
export const supprimerLigneCaisse = (id) => appel(`/cash/${id}`, { method: 'DELETE' })

// --- Documents de l'AG (spec §8.6), sous un bilan ---

// { level, documents: [{ id, title, format, level }], synthese: {...} }.
export const documentsAG = (reportId) => appel(`/reports/${reportId}/documents`)
export const urlDocumentAG = (reportId, kind) => `${BASE}/reports/${reportId}/documents/${kind}`
// Rapport financier rédigé (financier.md §8.6) : le modèle écrit, l'appli place les chiffres.
export const rapportFinancier = (reportId) => appel(`/reports/${reportId}/rapport`)
export const redigerRapport = (reportId, donnees) => appel(`/reports/${reportId}/rapport`, json('POST', donnees))
export const urlRapportFinancier = (reportId, format) => `${BASE}/reports/${reportId}/rapport/download?format=${format}`
// Niveau Complet (financier.md §8.7) : soldes de départ, clôture, écritures d'une opération.
export const soldesDepart = (seasonId) => appel(`/opening-balances/${seasonId}`)
export const enregistrerSoldesDepart = (seasonId, accounts) => appel(`/opening-balances/${seasonId}`, json('PUT', { accounts }))
export const cloturer = (reportId) => appel(`/reports/${reportId}/close`, { method: 'POST' })
export const rouvrir = (reportId) => appel(`/reports/${reportId}/close`, { method: 'DELETE' })
export const ecritures = (operationId) => appel(`/operations/${operationId}/entries`)
// L'œil des documents de l'AG : produit le fichier, le range dans Docs › Financier › AG, rend { id, orgId }.
export const documentAGDansDocs = (reportId, kind) => appel(`/reports/${reportId}/documents/${kind}/docs`, { method: 'POST' })
export const rapportDansDocs = (reportId, format) => appel(`/reports/${reportId}/rapport/docs?format=${format}`, { method: 'POST' })
