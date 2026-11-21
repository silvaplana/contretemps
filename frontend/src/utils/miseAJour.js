// Serveur en cours de mise en ligne (Seb, 21/11/2026 : écrans vides, ex.
// Combats, pendant chaque mise en ligne). Une demande sans réponse ou en
// erreur serveur (voir api/identite.js) fait vérifier /health : s'il ne
// répond pas non plus, c'est le serveur entier qui redémarre, pas une route
// en panne. Le bandeau « Mise à jour en cours » s'affiche
// (components/BandeauMiseAJour.jsx), /health est relu toutes les 3 s, et
// quand il répond l'appli se recharge pour tout relire (nouvelle version
// comprise). Téléphone hors réseau : pas de bandeau, ce n'est pas une mise
// à jour.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const INTERVALLE = 3000

let injoignable = false
let verification = false
const abonnes = new Set()

export const estInjoignable = () => injoignable

export function surChangement(rappel) {
  abonnes.add(rappel)
  return () => abonnes.delete(rappel)
}

function changer(valeur) {
  injoignable = valeur
  abonnes.forEach((rappel) => rappel(valeur))
}

async function repond(fetchNatif) {
  try {
    return (await fetchNatif(`${BASE_URL}/health`, { cache: 'no-store' })).ok
  } catch {
    return false
  }
}

// Revenu : un rechargement relit tout, sur tous les écrans. Sauf si une
// saisie est en cours (elle serait perdue) : les listes de l'appli sont
// alors relues sans recharger la page (voir App.jsx).
function revenu() {
  changer(false)
  const champ = document.activeElement
  const saisie = champ && (champ.tagName === 'INPUT' || champ.tagName === 'TEXTAREA' || champ.isContentEditable)
  if (saisie) window.dispatchEvent(new Event('contretemps:donnees-modifiees'))
  else window.location.reload()
}

function attendre(fetchNatif) {
  setTimeout(async () => {
    if (await repond(fetchNatif)) revenu()
    else attendre(fetchNatif)
  }, INTERVALLE)
}

export async function verifierServeur(fetchNatif) {
  if (injoignable || verification || navigator.onLine === false) return
  verification = true
  const ok = await repond(fetchNatif)
  verification = false
  if (ok || injoignable) return
  changer(true)
  attendre(fetchNatif)
}
