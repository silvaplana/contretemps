// Domaine "école" (Admin > École, voir spec/SPEC.md §5.1.1 et §6.1) — voir
// api/README.md pour le principe général.
//
// L'appli reste mono-école côté écran (voir auth.js : resoudreEcoleReelle),
// donc pas de lister()/creer() ici — juste modifier(), le seul besoin de
// AdminParametres.jsx.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function versEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
    codeAccesAdmin: e.code_acces_admin,
    codeAccesProf: e.code_acces_prof,
    codeAccesEleve: e.code_acces_eleve,
  }
}

export async function modifier(ecoleId, patch) {
  const corps = {
    ...(patch.nom !== undefined && { nom: patch.nom }),
    ...(patch.codePostal !== undefined && { code_postal: patch.codePostal }),
    ...(patch.codeAccesAdmin !== undefined && { code_acces_admin: patch.codeAccesAdmin }),
    ...(patch.codeAccesProf !== undefined && { code_acces_prof: patch.codeAccesProf }),
    ...(patch.codeAccesEleve !== undefined && { code_acces_eleve: patch.codeAccesEleve }),
  }
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps),
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return versEcran(await reponse.json())
}
