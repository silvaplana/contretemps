import * as session from '../../api/session.js'

// QR code d'essai lu avec l'appareil photo du téléphone (spec/modules/essai.md
// §4) : il contient `<adresse de l'école>/?essai=<jeton>` et ouvre l'appli.
// Lu une fois au chargement (avant la connexion si besoin), puis retiré de
// l'adresse pour qu'un rechargement ne le rejoue pas. L'appli s'ouvre sur
// Admin > Essais, qui affiche le résultat dans l'écran de scan.

let enAttente = (() => {
  const jeton = new URLSearchParams(window.location.search).get('essai')
  if (!jeton) return null
  window.history.replaceState(null, '', window.location.pathname + window.location.hash)
  session.sauvegarderEcran('onglet', 'admin')
  session.sauvegarderEcran('admin', 'essais')
  return jeton
})()

export const ESSAI_AU_CHARGEMENT = enAttente != null

// Le jeton à noter, une seule fois.
export function prendreJetonEnAttente() {
  const jeton = enAttente
  enAttente = null
  return jeton
}
