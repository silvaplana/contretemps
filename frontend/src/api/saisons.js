// Domaine "saisons" (Admin > École, voir spec/SPEC.md §2.6 et §5.1.1) —
// voir api/README.md pour le principe général. Réservé aux admins côté
// serveur (backend/src/saisons/receiver.py).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function versEcran(s) {
  return {
    id: s.id,
    nom: s.nom,
    dateDebut: s.date_debut,
    dateFin: s.date_fin,
    courante: s.courante,
    ouverte: s.ouverte,
  }
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

// Ce que « Créer une saison » peut reprendre de la courante : nombres
// d'élèves, de profs et de cours, champs de la fiche des élèves.
export const contenu = (ecoleId) => requete(`/ecoles/${ecoleId}/saisons/courante/contenu`)

// `cases` : { profs, cours, eleves, documents } (voir spec §2.6 : chacune
// exige la précédente). `structureEleves` : 'last' ou 'base' ;
// `champsMasques` : ids des champs à masquer (spec/modules/saisons.md §3).
// Renvoie la saison créée et la nouvelle fiche de l'admin qui l'a créée
// (`compteId`) : sa fiche actuelle vient de passer en lecture seule.
export async function creer(ecoleId, { nom, dateDebut, dateFin, cases, structureEleves = 'last', champsMasques = [] }) {
  const resultat = await requete(`/ecoles/${ecoleId}/saisons`, {
    method: 'POST',
    body: JSON.stringify({
      nom,
      date_debut: dateDebut,
      date_fin: dateFin,
      dupliquer_profs: cases.profs,
      dupliquer_cours: cases.cours,
      dupliquer_eleves: cases.eleves,
      dupliquer_documents: cases.documents,
      structure_eleves: structureEleves,
      champs_masques: champsMasques,
    }),
  })
  return { saison: versEcran(resultat.saison), compteId: resultat.compte_id }
}

// Nom et dates de la courante ou d'une ancienne saison ouverte.
export async function modifier(ecoleId, saisonId, { nom, dateDebut, dateFin }) {
  const saison = await requete(`/ecoles/${ecoleId}/saisons/${saisonId}`, {
    method: 'PUT',
    body: JSON.stringify({ nom, date_debut: dateDebut, date_fin: dateFin }),
  })
  return versEcran(saison)
}

// Ouvre ou referme une ancienne saison aux modifications (administrateur
// principal et Super User).
export async function ouvrir(ecoleId, saisonId, ouverte) {
  const saison = await requete(`/ecoles/${ecoleId}/saisons/${saisonId}/ouverture`, {
    method: 'PUT',
    body: JSON.stringify({ ouverte }),
  })
  return versEcran(saison)
}

// Supprime la saison et tout ce qui lui appartient (voir
// backend/src/saisons/gestion.py : supprimer ; une sauvegarde complète est
// écrite sur le serveur juste avant). Renvoie la fiche à utiliser désormais
// par l'admin (`compteId`) : la même, sa fiche de la saison précédente s'il
// vient de supprimer la courante, ou null.
export async function supprimer(ecoleId, saisonId) {
  const resultat = await requete(`/ecoles/${ecoleId}/saisons/${saisonId}`, { method: 'DELETE' })
  return { compteId: resultat.compte_id }
}
