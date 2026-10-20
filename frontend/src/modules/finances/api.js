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
  return reponse.json()
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
