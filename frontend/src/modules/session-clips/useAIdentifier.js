import { useEffect, useState } from 'react'
import * as api from './api.js'

// Badge de Fights dans la barre du bas (Seb, 12/11) : le nombre de combats
// dont les combattants restent à identifier, pour les coachs. Relu toutes
// les minutes ; un membre (refusé par le serveur) n'a pas de badge.
const RELIRE_MS = 60000

export default function useAIdentifier(actif, cle) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!actif) return undefined
    let minuteur
    const lire = () =>
      api.aVerifier().then(
        (l) => setN(l.length),
        () => {
          setN(0)
          clearInterval(minuteur)
        },
      )
    lire()
    minuteur = setInterval(lire, RELIRE_MS)
    return () => clearInterval(minuteur)
  }, [actif, cle])
  return actif ? n : 0
}
