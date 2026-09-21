// Tableau des administrateurs (Admin > École, voir spec/SPEC.md §2.4) —
// voir backend/src/administrateurs/. Droits vérifiés par le serveur : tout
// admin lit la liste, seuls les Owners créent/modifient/suppriment.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Le serveur explique ses refus (ex. "L'école doit garder au moins un
// Owner") : on remonte SON message, pas un "Requête échouée" muet.
async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const detail = typeof corps?.detail === 'string' ? corps.detail : null
    throw new Error(detail ?? `Requête échouée (${reponse.status})`)
  }
  return reponse.status === 204 ? null : reponse.json()
}

function versEcran(a) {
  return {
    id: a.id,
    nom: a.nom,
    prenom: a.prenom,
    email: a.email ?? '',
    estOwner: a.est_owner,
    // Professeur-admin : nom/prénom/email se modifient dans Admin > Profs,
    // et le "supprimer" lui retire seulement les droits d'admin.
    estProf: a.est_prof,
    estEleve: a.est_eleve,
    codeRecuperationDefini: a.code_recuperation_defini,
  }
}

export async function lister(ecoleId) {
  return (await requete(`/ecoles/${ecoleId}/administrateurs`)).map(versEcran)
}

// Deux façons (§2.4) : `compteId` (promouvoir un professeur ou un élève) OU
// nom/prénom/email (nouveau compte). Code de récupération dans les deux cas.
export async function creer(ecoleId, { compteId, nom, prenom, email, codeRecuperation, owner }) {
  const corps =
    compteId != null
      ? { compte_id: compteId, code_recuperation: codeRecuperation, owner }
      : { nom, prenom, email: email || null, code_recuperation: codeRecuperation, owner }
  return versEcran(await requete(`/ecoles/${ecoleId}/administrateurs`, { method: 'POST', body: JSON.stringify(corps) }))
}

// Seuls les champs présents dans `patch` sont envoyés (et modifiés).
export async function modifier(id, { nom, prenom, email, codeRecuperation, owner }) {
  const corps = {
    ...(nom !== undefined && { nom }),
    ...(prenom !== undefined && { prenom }),
    ...(email !== undefined && { email: email || null }),
    ...(codeRecuperation !== undefined && { code_recuperation: codeRecuperation }),
    ...(owner !== undefined && { owner }),
  }
  return versEcran(await requete(`/administrateurs/${id}`, { method: 'PUT', body: JSON.stringify(corps) }))
}

export async function supprimer(id) {
  await requete(`/administrateurs/${id}`, { method: 'DELETE' })
}
