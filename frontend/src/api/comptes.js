// Domaine "comptes" (voir spec/SPEC.md §6.2/§6.3) — pour l'instant, couvre
// la vraie liste des comptes admin de l'école (Admin > Messagerie,
// "Ajouter un membre" > Admin, à la place du "Direction" fictif d'avant)
// et la modification email/téléphone depuis Profil (crayon, voir
// ProfilScreen.jsx). Pas encore de module complet (pas d'écran de gestion
// multi-admin, voir spec §8).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Admins de l'école, plus le Super User : absent des listes de personnes,
// il se trouve et s'ajoute dans les conversations de toute école
// (spec/core.md §6.1). Cette liste ne sert qu'aux conversations.
export async function listerAdmins(ecoleId) {
  const [admins, superusers] = await Promise.all(
    [`${BASE_URL}/comptes?ecole_id=${ecoleId}&role=admin`, `${BASE_URL}/super-users`].map(async (url) => {
      const reponse = await fetch(url)
      if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
      return reponse.json()
    }),
  )
  return [...admins, ...superusers]
}

function versFamilleEcran(c) {
  return {
    id: c.id,
    type: c.role,
    roles: c.roles,
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

export async function modifier(compteId, patch) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.json()
}

// Saisons (spec §2.6) : la fiche de la même personne dans la saison
// courante — la même si elle en fait déjà partie, sa nouvelle fiche si elle
// a été recopiée dans une saison créée depuis, `null` si elle n'y a pas été
// reprise (ou compte inconnu). Voir App.jsx : reprise de session.
export async function ficheCourante(compteId) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}/fiche-courante`)
  if (reponse.status === 404) return null
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return (await reponse.json()).compte_id
}

// Une personne = une fiche (spec/core.md §4) : `gardeId` garde tout ce
// qu'avait `autreId`, qui disparaît. Refus lisible (409 : mauvaise fiche,
// 403 : réservé à l'Administrateur principal dès qu'une fiche est admin).
export async function fusionner(gardeId, autreId) {
  const reponse = await fetch(`${BASE_URL}/comptes/${gardeId}/fusion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ autre_id: autreId }),
  })
  if (reponse.status === 403) throw new Error('Une fiche admin ne se fusionne que par un administrateur principal.')
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => ({}))
    throw new Error(typeof corps.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
  }
  return reponse.json()
}
