import { useEffect } from 'react'

// « Envoyer à… » de la messagerie (spec/modules/messagerie-instantanee.md
// §4.2 et §4.7), ouvert de deux façons :
// - depuis un autre module de l'appli : `envoyerDansLaMessagerie(texte)`,
//   par exemple le lien d'un fichier des Docs. Le module n'a rien d'autre à
//   connaître : App.jsx ouvre la messagerie et l'écran de choix ;
// - depuis une autre appli du téléphone (bouton Partager de YouTube...) :
//   le manifest déclare `share_target` (backend/src/personnalisation), le
//   téléphone ouvre alors `/partage?title=…&text=…&url=…`.

const EVENEMENT = 'messagerie:envoyer-a'

export function envoyerDansLaMessagerie(texte) {
  window.dispatchEvent(new CustomEvent(EVENEMENT, { detail: { texte } }))
}

export function useEnvoyerA(onTexte) {
  useEffect(() => {
    const ecouter = (e) => onTexte(e.detail.texte)
    window.addEventListener(EVENEMENT, ecouter)
    return () => window.removeEventListener(EVENEMENT, ecouter)
  }, [onTexte])
}

// Lu une seule fois au chargement (avant la connexion si besoin) ; l'adresse
// redevient celle de l'accueil pour qu'un rechargement ne repartage pas.
function lirePartageEntrant() {
  if (!window.location.pathname.endsWith('/partage')) return null
  const params = new URLSearchParams(window.location.search)
  const morceaux = []
  for (const cle of ['title', 'text', 'url']) {
    const valeur = params.get(cle)?.trim()
    if (valeur && !morceaux.some((m) => m.includes(valeur))) morceaux.push(valeur)
  }
  window.history.replaceState(null, '', window.location.pathname.replace(/partage$/, ''))
  return morceaux.length > 0 ? morceaux.join('\n') : null
}

export const PARTAGE_ENTRANT = lirePartageEntrant()
