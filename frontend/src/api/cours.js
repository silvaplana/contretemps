// Domaine "cours" (Admin > Cours, voir spec/SPEC.md §6.5) — voir
// api/README.md pour le principe général.
//
// ⚠️ Simplification volontaire : les écrans actuels (AdminCours,
// Présence, PlanningHebdoView, HeuresScreen) supposent UN SEUL
// `professeurId` par cours. Le backend modélise en réalité plusieurs
// profs par cours (table de jointure cours_professeurs, voir
// backend/src/cours/models.py) — la couche ci-dessous s'adapte (ne
// prend que le premier professeur assigné) plutôt que de forcer une
// refonte des écrans aujourd'hui. À revoir si un jour l'IHM a besoin de
// plusieurs profs par cours.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

async function avecProfesseurId(cours) {
  const professeurs = await requete(`/cours/${cours.id}/professeurs`)
  return {
    id: cours.id,
    nom: cours.nom,
    jour: cours.jour ?? '',
    heureDebut: cours.heure_debut ?? '',
    heureFin: cours.heure_fin ?? '',
    salle: cours.salle ?? '',
    professeurId: professeurs[0]?.id ?? '',
  }
}

export async function lister(ecoleId) {
  const liste = await requete(`/cours?ecole_id=${ecoleId}`)
  return Promise.all(liste.map(avecProfesseurId))
}

function versChampsBackend({ heureDebut, heureFin, ...reste }) {
  return {
    ...reste,
    ...(heureDebut !== undefined && { heure_debut: heureDebut }),
    ...(heureFin !== undefined && { heure_fin: heureFin }),
  }
}

export async function creer(ecoleId, { professeurId, ...donnees }) {
  const cours = await requete(`/cours?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify(versChampsBackend(donnees)),
  })
  if (professeurId) {
    await requete(`/cours/${cours.id}/professeurs/${professeurId}`, { method: 'POST' })
  }
  return avecProfesseurId(cours)
}

export async function modifier(coursId, { professeurId, ...patch }) {
  if (Object.keys(patch).length > 0) {
    await requete(`/cours/${coursId}`, { method: 'PUT', body: JSON.stringify(versChampsBackend(patch)) })
  }
  if (professeurId !== undefined) {
    const actuels = await requete(`/cours/${coursId}/professeurs`)
    await Promise.all(actuels.map((p) => requete(`/cours/${coursId}/professeurs/${p.id}`, { method: 'DELETE' })))
    if (professeurId) {
      await requete(`/cours/${coursId}/professeurs/${professeurId}`, { method: 'POST' })
    }
  }
  return avecProfesseurId(await requete(`/cours/${coursId}`))
}

export async function supprimer(coursId) {
  await requete(`/cours/${coursId}`, { method: 'DELETE' })
}
