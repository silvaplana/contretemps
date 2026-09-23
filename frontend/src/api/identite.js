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
// parole (limite assumée, voir rbac.py). SAUF pour le Superuser (§2.5) :
// son jeton signé part en plus dans `Authorization`, et c'est lui seul que
// le serveur croit pour ce compte.

import { ENTETE_SAISON, lireSaisonConsultee, signalerSaison } from './saison.js'
import { lireCompteSauvegarde, lireJeton } from './session.js'

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
    const jeton = lireJeton()
    if ((compteId === null && !jeton) || !versNotreApi(url)) {
      return fetchNatif(entree, options)
    }
    const entetes = new Headers(options.headers ?? (entree instanceof Request ? entree.headers : undefined))
    if (compteId !== null) entetes.set(ENTETE_COMPTE, String(compteId))
    if (jeton) entetes.set('Authorization', `Bearer ${jeton}`)
    // Ancienne saison consultée par un admin (voir api/saison.js).
    const saison = lireSaisonConsultee()
    if (saison) entetes.set(ENTETE_SAISON, String(saison.id))
    return fetchNatif(entree, { ...options, headers: entetes }).then((reponse) => {
      if ([401, 403, 409].includes(reponse.status)) analyserRefusSaison(reponse)
      return reponse
    })
  }
}

// Saisons (spec §2.6) : repère, sans consommer la réponse (qui reste lue
// normalement par l'appelant), les refus propres aux saisons, et prévient
// l'appli (voir App.jsx) — ici plutôt que dans chaque api/*.js, pour que
// n'importe quelle requête puisse les déclencher.
function analyserRefusSaison(reponse) {
  reponse
    .clone()
    .json()
    .then(({ detail }) => {
      if (detail?.code === 'nouvelle_saison') signalerSaison({ code: 'nouvelle_saison', compteId: detail.compte_id })
      else if (detail?.code === 'hors_saison') signalerSaison({ code: 'hors_saison' })
      else if (typeof detail === 'string' && detail.includes('lecture seule')) signalerSaison({ code: 'lecture_seule' })
    })
    .catch(() => {})
}
