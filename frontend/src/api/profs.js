// Domaine "professeurs" (Admin > Professeurs, voir spec/SPEC.md §6.3) —
// voir api/README.md pour le principe général. Plus simple qu'eleves.js :
// aucun champ propre côté backend (juste Compte + cours enseignés).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// ProfSortie du backend renvoie déjà cours_ids (pas besoin d'une 2e
// requête comme pour les élèves) — juste traduire vers camelCase.
function versEcran(prof) {
  return {
    id: prof.id,
    nom: prof.nom,
    prenom: prof.prenom,
    email: prof.email ?? '',
    telephone: prof.telephone ?? '',
    coursIds: prof.cours_ids,
  }
}

export async function lister(ecoleId) {
  const profs = await requete(`/profs?ecole_id=${ecoleId}`)
  return profs.map(versEcran)
}

export async function creer(ecoleId, donnees) {
  return versEcran(await requete(`/profs?ecole_id=${ecoleId}`, { method: 'POST', body: JSON.stringify(donnees) }))
}

export async function modifier(profId, patch) {
  return versEcran(await requete(`/profs/${profId}`, { method: 'PUT', body: JSON.stringify(patch) }))
}

export async function supprimer(profId) {
  await requete(`/profs/${profId}`, { method: 'DELETE' })
}

export async function basculerCours(profId, coursId) {
  const prof = await requete(`/profs/${profId}`)
  const inscrit = prof.cours_ids.includes(coursId)
  await requete(`/cours/${coursId}/professeurs/${profId}`, { method: inscrit ? 'DELETE' : 'POST' })
  return versEcran(await requete(`/profs/${profId}`))
}
