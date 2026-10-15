// Personnalisation de l'application par école (Admin > École, spec §2.7 et
// §5.1.1) : réglages, adresse web, images (logo, nom) et leur détourage.
// Lecture de l'apparence appliquée à l'appli : voir api/apparence.js.

import { versEcran } from './apparence.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    ...options,
    headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...options.headers },
  })
  if (!reponse.ok) {
    const detail = (await reponse.json().catch(() => null))?.detail
    throw new Error(typeof detail === 'string' ? detail : `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

export async function obtenir(ecoleId) {
  return versEcran(await requete(`/ecoles/${ecoleId}/personnalisation`))
}

export async function modifier(ecoleId, champs) {
  const corps = {
    nom_appli: champs.nomAppli,
    nom_mode: champs.nomMode,
    slogan: champs.slogan,
    couleur_fond: champs.couleurFond,
    couleur_texte: champs.couleurTexte,
    couleur_accent: champs.couleurAccent,
    police: champs.police || null,
    police_titres: champs.policeTitres || null,
    police_nom: champs.policeNom || null,
    police_slogan: champs.policeSlogan || null,
  }
  return versEcran(await requete(`/ecoles/${ecoleId}/personnalisation`, { method: 'PATCH', body: JSON.stringify(corps) }))
}

export async function revenirAuDefaut(ecoleId) {
  return versEcran(await requete(`/ecoles/${ecoleId}/personnalisation/defaut`, { method: 'POST' }))
}

// Réservé aux Owners (spec §2.7). L'ancienne adresse redirige 6 mois.
export async function changerAdresse(ecoleId, adresse) {
  return versEcran(
    await requete(`/ecoles/${ecoleId}/sous-domaine`, { method: 'PATCH', body: JSON.stringify({ sous_domaine: adresse }) }),
  )
}

// { adresse, disponible, raison: 'invalide' | 'reserve' | 'pris' | null, proposition }
export async function disponibilite(adresse, ecoleId) {
  return requete(`/sous-domaines/${encodeURIComponent(adresse)}/disponible?ecole_id=${ecoleId}`)
}

// --- Images (type : 'logo' ou 'nom') : brouillon, détourage, validation ---

function versBrouillon(b) {
  return {
    type: b.type,
    original: b.original,
    traite: b.traite,
    detourage: b.detourage,
    detouragesDisponibles: b.detourages_disponibles,
    couleurFondProposee: b.couleur_fond_proposee,
    coutUsd: b.cout_usd,
  }
}

export async function envoyerImage(ecoleId, type, fichier) {
  const corps = new FormData()
  corps.append('fichier', fichier)
  return versBrouillon(await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}`, { method: 'POST', body: corps }))
}

export async function choisirDetourage(ecoleId, type, detourage) {
  return versBrouillon(
    await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}/detourage`, {
      method: 'POST',
      body: JSON.stringify({ detourage }),
    }),
  )
}

export async function validerImage(ecoleId, type) {
  return versEcran(await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}/valider`, { method: 'POST' }))
}

export async function annulerImage(ecoleId, type) {
  await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}`, { method: 'DELETE' }).catch(() => {})
}

// --- Historique des images validées (demande du 2026-10-15) ---

// [{ fichier, version, actuelle }], la plus récente d'abord.
export async function historique(ecoleId, type) {
  return requete(`/ecoles/${ecoleId}/personnalisation/images/${type}/historique`)
}

export async function reprendreImage(ecoleId, type, fichier) {
  return versEcran(
    await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}/historique/${fichier}`, { method: 'POST' }),
  )
}

export async function supprimerImage(ecoleId, type, fichier) {
  await requete(`/ecoles/${ecoleId}/personnalisation/images/${type}/historique/${fichier}`, { method: 'DELETE' })
}
