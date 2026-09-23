// Domaine "saisons" (Admin > École, voir spec/SPEC.md §2.6 et §5.1.1) —
// voir api/README.md pour le principe général. Réservé aux admins côté
// serveur (backend/src/saisons/receiver.py).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function versEcran(s) {
  return { id: s.id, nom: s.nom, dateDebut: s.date_debut, dateFin: s.date_fin, courante: s.courante }
}

// Le message du serveur (409 : nom déjà pris, dates incohérentes...) est
// renvoyé tel quel pour être affiché dans le panneau.
async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    throw new Error(typeof corps?.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
  }
  return reponse.json()
}

// De la plus récente (la courante) à la plus ancienne.
export async function lister(ecoleId) {
  return (await requete(`/ecoles/${ecoleId}/saisons`)).map(versEcran)
}

// `cases` : { profs, cours, eleves } (voir spec §2.6 : chacune exige la
// précédente). Renvoie la saison créée et la nouvelle fiche de l'admin qui
// l'a créée (`compteId`) : sa fiche actuelle vient de passer en lecture seule.
export async function creer(ecoleId, { nom, dateDebut, dateFin, cases }) {
  const resultat = await requete(`/ecoles/${ecoleId}/saisons`, {
    method: 'POST',
    body: JSON.stringify({
      nom,
      date_debut: dateDebut,
      date_fin: dateFin,
      dupliquer_profs: cases.profs,
      dupliquer_cours: cases.cours,
      dupliquer_eleves: cases.eleves,
    }),
  })
  return { saison: versEcran(resultat.saison), compteId: resultat.compte_id }
}

export async function modifierCourante(ecoleId, { nom, dateDebut, dateFin }) {
  const saison = await requete(`/ecoles/${ecoleId}/saisons/courante`, {
    method: 'PUT',
    body: JSON.stringify({ nom, date_debut: dateDebut, date_fin: dateFin }),
  })
  return versEcran(saison)
}
