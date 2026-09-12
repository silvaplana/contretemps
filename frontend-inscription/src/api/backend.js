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

// Upload multipart, séparé de creerInscription (appelé juste après, une
// fois le token connu) — ne passe PAS par `requete` : il ne faut jamais
// fixer soi-même le Content-Type d'un FormData, le navigateur doit
// poser la frontière multipart lui-même. Jamais bloquant pour
// l'inscription si ça échoue (voir FormulaireInscription.jsx).
export async function uploaderPhotoEleve(token, fichier) {
  const corps = new FormData()
  corps.append('fichier', fichier)
  const reponse = await fetch(`${BASE_URL}/inscriptions/${token}/photo`, {
    method: 'POST',
    body: corps,
  })
  if (!reponse.ok) {
    throw new Error(`Envoi de la photo échoué (${reponse.status})`)
  }
}

export function urlDossierPdf(token) {
  return `${BASE_URL}/inscriptions/${token}/dossier.pdf`
}

export function urlFacturePdf(token) {
  return `${BASE_URL}/inscriptions/${token}/facture.pdf`
}

// Recharge une inscription par son token — utilisé au retour de
// paiement HelloAsso (voir App.jsx) : la redirection HelloAsso recharge
// entièrement la page, l'état React de la soumission initiale est perdu.
export async function obtenirInscription(token) {
  return requete(`/inscriptions/${token}`)
}

// Étape 2 du flux (voir spec/SPEC-inscription.md) : fixe le moyen de
// paiement d'une inscription déjà créée (étape 1, sans moyen de paiement
// connu). Chèque : finalise tout de suite côté serveur (PDF/email).
// HelloAsso : enregistre juste le choix, la finalisation attend la
// confirmation du paiement (voir initierPaiementHelloAsso ensuite).
export async function choisirPaiement(token, moyenPaiement, paiementNbEcheances) {
  return requete(`/inscriptions/${token}/paiement/choix`, {
    method: 'POST',
    body: JSON.stringify({
      moyen_paiement: moyenPaiement,
      paiement_nb_echeances: paiementNbEcheances,
    }),
  })
}

// Crée le Checkout Intent HelloAsso et renvoie l'URL de paiement — voir
// Confirmation.jsx : redirige ensuite `window.location` vers cette URL
// (departure complète du SPA, pas un fetch en arrière-plan).
export async function initierPaiementHelloAsso(token, retourUrl) {
  return requete(`/inscriptions/${token}/paiement/helloasso`, {
    method: 'POST',
    body: JSON.stringify({ retour_url: retourUrl }),
  })
}

// Ré-interroge HelloAsso (jamais confiance au simple retour navigateur,
// voir spec/SPEC-inscription.md §4) et renvoie l'inscription à jour
// (statut_paiement inclus) — LE check qui fait foi, toujours appelé au
// retour de paiement (voir App.jsx).
export async function verifierPaiementHelloAsso(token) {
  return requete(`/inscriptions/${token}/paiement/helloasso/verifier`, { method: 'POST' })
}
