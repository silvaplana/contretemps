// Onglet Docs : dossiers et fichiers (module `documents` du serveur, voir
// backend/src/documents/receiver.py). Les fichiers sont protégés : jamais
// d'URL publique, on les lit avec la session (en-têtes ajoutés par
// api/identite.js) puis on les affiche par une URL locale (blob).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ErreurDocuments extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

async function appel(chemin, options = {}) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, options)
  if (!reponse.ok) {
    let message = `Requête échouée (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // réponse sans JSON : message par défaut
    }
    throw new ErreurDocuments(reponse.status, message)
  }
  if (reponse.status === 204) return null
  return reponse.json()
}

const json = (methode, corps) => ({
  method: methode,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corps),
})

export function documentsApi(orgId) {
  const base = `/documents/orgs/${orgId}`
  return {
    spaces: () => appel(`${base}/spaces`),
    browse: (space, folderId) => appel(`${base}/spaces/${space}${folderId ? `?folder=${folderId}` : ''}`),
    search: (space, q) => appel(`${base}/spaces/${space}/search?q=${encodeURIComponent(q)}`),
    trash: (space) => appel(`${base}/spaces/${space}/trash`),
    detail: (id) => appel(`${base}/nodes/${id}`),
    createFolder: (space, parentId, name) => appel(`${base}/folders`, json('POST', { space, parent_id: parentId, name })),
    upload: (space, parentId, file) => {
      const donnees = new FormData()
      donnees.append('space', space)
      if (parentId) donnees.append('parent_id', String(parentId))
      donnees.append('file', file, file.name)
      return appel(`${base}/files`, { method: 'POST', body: donnees })
    },
    newVersion: (id, file) => {
      const donnees = new FormData()
      donnees.append('file', file, file.name)
      return appel(`${base}/nodes/${id}/versions`, { method: 'POST', body: donnees })
    },
    rename: (id, name) => appel(`${base}/nodes/${id}`, json('PATCH', { name })),
    move: (id, space, parentId) => appel(`${base}/nodes/${id}`, json('PATCH', { move: true, space, parent_id: parentId })),
    copy: (id, space, parentId) => appel(`${base}/nodes/${id}/copy`, json('POST', { space, parent_id: parentId })),
    setStatus: (id, status) => appel(`${base}/nodes/${id}`, json('PATCH', { change_status: true, status })),
    remove: (id) => appel(`${base}/nodes/${id}`, { method: 'DELETE' }),
    restore: (id) => appel(`${base}/nodes/${id}/restore`, { method: 'POST' }),
    getAccess: (id) => appel(`${base}/nodes/${id}/access`),
    setAccess: (id, restricted, entries) =>
      appel(`${base}/nodes/${id}/access`, json('PUT', { restricted, entries })),
    principals: (q) => appel(`${base}/principals?q=${encodeURIComponent(q)}`),
    // Contenu protégé : lu avec la session, rendu par une URL blob: (à
    // libérer avec URL.revokeObjectURL quand on n'en a plus besoin).
    blobUrl: async (id, { thumbnail = false, version } = {}) => {
      const chemin = thumbnail
        ? `${base}/nodes/${id}/thumbnail`
        : `${base}/nodes/${id}/content${version ? `?version=${version}` : ''}`
      const reponse = await fetch(`${BASE_URL}${chemin}`)
      if (!reponse.ok) throw new ErreurDocuments(reponse.status, `Requête échouée (${reponse.status})`)
      return URL.createObjectURL(await reponse.blob())
    },
  }
}
