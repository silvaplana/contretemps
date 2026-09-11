// Client du backend Contretemps existant (même API que l'appli
// principale, voir frontend/src/api/*.js) — cette page n'a pas de compte,
// donc pas de login : elle résout la seule école existante (voir
// resoudreEcoleReelle, même principe que frontend/src/api/auth.js),
// cohérent avec l'hypothèse mono-école déjà actée ailleurs dans le projet.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) {
    let detail = null
    try {
      detail = (await reponse.json()).detail
    } catch {
      // corps non-JSON, ignoré
    }
    throw new Error(detail || `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

export async function resoudreEcoleReelle() {
  const ecoles = await requete('/ecoles')
  if (ecoles.length === 0) {
    throw new Error('Aucune école configurée côté serveur')
  }
  return ecoles[0]
}

export async function listerCours(ecoleId) {
  return requete(`/cours?ecole_id=${ecoleId}`)
}

export async function creerInscription(ecoleId, donnees) {
  return requete(`/inscriptions?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify(donnees),
  })
}

export function urlDossierPdf(token) {
  return `${BASE_URL}/inscriptions/${token}/dossier.pdf`
}

export function urlFacturePdf(token) {
  return `${BASE_URL}/inscriptions/${token}/facture.pdf`
}
