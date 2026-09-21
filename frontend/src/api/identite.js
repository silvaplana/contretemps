// Identité de l'appelant pour le RBAC du serveur (voir spec/SPEC.md §2.4 et
// backend/src/comptes/rbac.py) : chaque requête vers NOTRE API porte l'id du
// profil actif dans l'en-tête `X-Compte-Id`. Le serveur s'en sert pour
// réserver les routes de l'onglet Admin aux admins de l'école.
//
// Installé UNE fois au démarrage (voir main.jsx), autour de `fetch`, plutôt
// qu'ajouté à la main dans chaque fichier api/*.js : un appel oublié
// casserait une action Admin, et chaque nouvel appel en hérite tout seul.
// Seules les requêtes vers BASE_URL sont concernées — jamais celles vers un
// autre site (ex. Google Drive, voir utils/googleDrive.js), qui n'ont pas à
// connaître cet id.
//
// ⚠️ Ce n'est PAS une authentification : le serveur croit cet en-tête sur
// parole (limite assumée, voir rbac.py).

import { lireCompteSauvegarde } from './session.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const ENTETE_COMPTE = 'X-Compte-Id'

// BASE_URL peut être relative en prod ("/contretemps/api") ou absolue en
// dev ("http://localhost:8000") : on compare des URL complètes.
function versNotreApi(url) {
  const base = new URL(BASE_URL, window.location.origin).href.replace(/\/$/, '')
  const cible = new URL(url, window.location.origin).href
  return cible === base || cible.startsWith(`${base}/`)
}

export function installerIdentiteAppelant() {
  const fetchNatif = window.fetch.bind(window)
  window.fetch = (entree, options = {}) => {
    const url = entree instanceof Request ? entree.url : String(entree)
    const compteId = lireCompteSauvegarde()
    if (compteId === null || !versNotreApi(url)) {
      return fetchNatif(entree, options)
    }
    const entetes = new Headers(options.headers ?? (entree instanceof Request ? entree.headers : undefined))
    entetes.set(ENTETE_COMPTE, String(compteId))
    return fetchNatif(entree, { ...options, headers: entetes })
  }
}
