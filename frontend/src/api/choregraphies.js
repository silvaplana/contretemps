// Domaine "chorégraphies" (écran Chorégraphie, voir spec/SPEC.md §6.7) —
// voir api/README.md pour le principe général.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

async function avecEleveIds(ch) {
  const eleves = await requete(`/choregraphies/${ch.id}/eleves`)
  return {
    id: ch.id,
    nom: ch.nom,
    costume: ch.costume ?? '',
    horaireRepetition: ch.horaire_repetition ?? '',
    eleveIds: eleves.map((e) => e.id),
  }
}

export async function lister(coursId) {
  const liste = await requete(`/cours/${coursId}/choregraphies`)
  return Promise.all(liste.map(avecEleveIds))
}

function versChampsBackend({ horaireRepetition, ...reste }) {
  return { ...reste, ...(horaireRepetition !== undefined && { horaire_repetition: horaireRepetition }) }
}

export async function creer(coursId, { eleveIds = [], ...donnees }) {
  const ch = await requete(`/cours/${coursId}/choregraphies`, {
    method: 'POST',
    body: JSON.stringify(versChampsBackend(donnees)),
  })
  await Promise.all(eleveIds.map((id) => requete(`/choregraphies/${ch.id}/eleves/${id}`, { method: 'POST' })))
  return avecEleveIds(ch)
}

export async function modifier(choregraphieId, { eleveIds, ...patch }) {
  if (Object.keys(patch).length > 0) {
    await requete(`/choregraphies/${choregraphieId}`, {
      method: 'PUT',
      body: JSON.stringify(versChampsBackend(patch)),
    })
  }
  if (eleveIds !== undefined) {
    const actuels = (await requete(`/choregraphies/${choregraphieId}/eleves`)).map((e) => e.id)
    const aRetirer = actuels.filter((id) => !eleveIds.includes(id))
    const aAjouter = eleveIds.filter((id) => !actuels.includes(id))
    await Promise.all([
      ...aRetirer.map((id) => requete(`/choregraphies/${choregraphieId}/eleves/${id}`, { method: 'DELETE' })),
      ...aAjouter.map((id) => requete(`/choregraphies/${choregraphieId}/eleves/${id}`, { method: 'POST' })),
    ])
  }
  return avecEleveIds(await requete(`/choregraphies/${choregraphieId}`))
}

export async function supprimer(_coursId, choregraphieId) {
  await requete(`/choregraphies/${choregraphieId}`, { method: 'DELETE' })
}
