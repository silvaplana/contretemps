// Session de l'appelant (voir spec/SPEC.md §2.2 et backend/src/comptes/
// rbac.py) : chaque requête vers NOTRE API porte le jeton de session
// (`Authorization: Bearer ...`) et l'id du profil actif (`X-Compte-Id`).
// Le serveur vérifie le jeton, et que le profil appartient bien à l'adresse
// email connectée : sans session valide, il ne répond plus à rien (sauf
// connexion, liens reçus par mail et inscription publique).
//
// Installé UNE fois au démarrage (voir main.jsx), autour de `fetch`, plutôt
// qu'ajouté à la main dans chaque fichier api/*.js : un appel oublié
// casserait une action, et chaque nouvel appel en hérite tout seul.
// Seules les requêtes vers BASE_URL sont concernées — jamais celles vers un
// autre site (ex. Google Drive, voir utils/googleDrive.js), qui n'ont pas à
// connaître ce jeton.

import { ENTETE_SAISON, lireSaisonConsultee, signalerSaison } from './saison.js'
import { compteEnCours, jetonEnCours, remplacerJeton } from './session.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const ENTETE_COMPTE = 'X-Compte-Id'
const ENTETE_JETON_RENOUVELE = 'X-Jeton-Renouvele'

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
    const compteId = compteEnCours()
    const jeton = jetonEnCours()
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
      // Session prolongée (30 jours glissants) : le serveur remet de temps
      // en temps un jeton neuf, qui remplace l'ancien.
      const renouvele = reponse.headers.get(ENTETE_JETON_RENOUVELE)
      if (renouvele && jetonEnCours() === jeton) remplacerJeton(renouvele)
      if ([401, 403, 409].includes(reponse.status)) analyserRefus(reponse)
      return reponse
    })
  }
}

// Repère, sans consommer la réponse (qui reste lue normalement par
// l'appelant), les refus qui concernent toute l'appli, et la prévient (voir
// App.jsx) — ici plutôt que dans chaque api/*.js, pour que n'importe quelle
// requête puisse les déclencher : session expirée (§2.2), saisons (§2.6).
function analyserRefus(reponse) {
  reponse
    .clone()
    .json()
    .then(({ detail }) => {
      if (detail?.code === 'session_expiree') signalerSaison({ code: 'session_expiree' })
      else if (detail?.code === 'nouvelle_saison') signalerSaison({ code: 'nouvelle_saison', compteId: detail.compte_id })
      else if (detail?.code === 'hors_saison') signalerSaison({ code: 'hors_saison' })
      else if (typeof detail === 'string' && detail.includes('lecture seule')) signalerSaison({ code: 'lecture_seule' })
    })
    .catch(() => {})
}
