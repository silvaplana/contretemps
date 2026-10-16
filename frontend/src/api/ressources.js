// « Usage ressources et IA de la saison » (Admin > École, voir spec/SPEC.md
// §5.1.1) : place occupée sur le disque par l'école, et coût de ses
// opérations d'IA par poste (lecture des fiches, détourage du logo...).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function usage(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/ressources`)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  const u = await reponse.json()
  return {
    saison: u.saison,
    memoire: u.memoire.map((r) => ({ cle: r.cle, libelle: r.libelle, octets: r.octets })),
    memoireTotalOctets: u.memoire_total_octets,
    ia: u.ia.map((p) => ({ categorie: p.categorie, libelle: p.libelle, nombre: p.nombre, coutUsd: p.cout_usd })),
    iaTotalUsd: u.ia_total_usd,
    iaTotalToutesSaisonsUsd: u.ia_total_toutes_saisons_usd,
    assistantPlafondUsd: u.assistant_plafond_mensuel_usd,
    assistantCoutDuMoisUsd: u.assistant_cout_du_mois_usd,
    assistantPlafondModifiable: u.assistant_plafond_modifiable,
  }
}

// Plafond mensuel de l'assistant de l'école, en dollars (Super User seul).
export async function definirPlafondAssistant(ecoleId, plafondUsd) {
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/assistant-plafond`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plafond_usd: plafondUsd }),
  })
  if (!reponse.ok) throw new Error(`Plafond non enregistré (${reponse.status})`)
  return (await reponse.json()).plafond_usd
}
