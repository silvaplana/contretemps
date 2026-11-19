// Import auto pièces (spec/modules/import-auto-pieces.md) — voir
// backend/src/auto_import/. Accès au Financier seulement ; sous-module
// éteint : 404.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    ...options,
    headers: { 'Content-Type': 'application/json' },
  })
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null)
    const erreur = new Error(typeof corps?.detail === 'string' ? corps.detail : `Requête échouée (${reponse.status})`)
    erreur.status = reponse.status
    throw erreur
  }
  return reponse.status === 204 ? null : reponse.json()
}

// → { rules: [...], seasons: [{ id, name }], drives: [{ id, name, provider }], mail_boxes: [{ id, name }] }
export const etat = () => requete('/auto-import')
// Le sous-module est-il allumé pour cette personne ? (entrée du menu ⋯)
export const disponible = () => etat().then(() => true, () => false)
export const creer = () => requete('/auto-import', { method: 'POST' })
export const enregistrer = (regle) => requete(`/auto-import/${regle.id}`, { method: 'PUT', body: JSON.stringify(regle) })
export const effacer = (id) => requete(`/auto-import/${id}`, { method: 'DELETE' })
// « Regarder maintenant » → { created, message }
export const regarder = (id) => requete(`/auto-import/${id}/run`, { method: 'POST' })
// « Voir » → { notes }
export const pieces = (id) => requete(`/auto-import/${id}/pieces`)
// Dossiers de Docs → [{ id, name, space }]
export const dossiersDocs = (parent) => requete(`/auto-import-docs-folders${parent ? `?parent=${parent}` : ''}`)
