// Domaine "comptes" (voir spec/SPEC.md §6.2/§6.3) — pour l'instant, couvre
// la vraie liste des comptes admin de l'école (Admin > Conversations,
// "Ajouter un membre" > Admin, à la place du "Direction" fictif d'avant)
// et la modification email/code_recuperation depuis Profil (crayon, voir
// ProfilScreen.jsx). Pas encore de module complet (pas d'écran de gestion
// multi-admin, voir spec §8).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function listerAdmins(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/comptes?ecole_id=${ecoleId}&role=admin`)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.json()
}

function versFamilleEcran(c) {
  return {
    id: c.id,
    type: c.role,
    nom: c.nom,
    prenom: c.prenom,
    initiales: `${(c.prenom[0] ?? '').toUpperCase()}${(c.nom[0] ?? '').toUpperCase()}`,
  }
}

// "Ma famille" (Profil) et "Changer de profil" (Header).
export async function listerFamille(compteId) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}/famille`)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  const comptes = await reponse.json()
  return comptes.map(versFamilleEcran)
}

function versChampsBackend({ codeRecuperation, ...reste }) {
  return { ...reste, ...(codeRecuperation !== undefined && { code_recuperation: codeRecuperation }) }
}

export async function modifier(compteId, patch) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(versChampsBackend(patch)),
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.json()
}
