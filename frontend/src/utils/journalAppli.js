// Journal de l'appli (Seb, 20/11/2026 : « des fois il y a 0 élève, il faut
// fermer et relancer »). Chaque demande au serveur qui échoue est notée sur
// le téléphone, puis envoyée au serveur dès qu'une demande repasse (voir
// api/identite.js et backend/src/app/journal_appli.py). Seb donne l'heure
// du problème, Claude lit le journal.

const CLE = 'contretemps:journal'
const MAX = 50
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
export const CHEMIN_JOURNAL = '/journal/appli'

function lire() {
  try {
    return JSON.parse(localStorage.getItem(CLE)) ?? []
  } catch {
    return []
  }
}

function ecrire(lignes) {
  try {
    if (lignes.length) localStorage.setItem(CLE, JSON.stringify(lignes.slice(-MAX)))
    else localStorage.removeItem(CLE)
  } catch {
    // Pas de stockage : tant pis pour le journal.
  }
}

// Heure locale du téléphone, lisible telle quelle (heure de Paris pour Seb).
function maintenant() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

export function noter(methode, chemin, raison) {
  ecrire([...lire(), { at: maintenant(), method: methode, path: String(chemin).slice(0, 300), reason: String(raison).slice(0, 300) }])
}

let envoiEnCours = false

// Appelé après chaque réponse du serveur : la connexion est revenue.
export function envoyer() {
  const lignes = lire()
  if (!lignes.length || envoiEnCours) return
  envoiEnCours = true
  fetch(`${BASE_URL}${CHEMIN_JOURNAL}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(lignes),
  })
    .then((reponse) => {
      // Seulement les lignes envoyées : d'autres ont pu s'ajouter entre-temps.
      if (reponse.ok) ecrire(lire().slice(lignes.length))
    })
    .catch(() => {})
    .finally(() => {
      envoiEnCours = false
    })
}
