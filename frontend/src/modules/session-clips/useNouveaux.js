import { useEffect, useState } from 'react'
import * as api from './api.js'

// Pastille de Fights dans la barre du bas (Seb, 17/11) : le nombre de
// combats validés de la personne qu'elle n'a pas encore ouverts. Relu à
// chaque changement d'onglet et toutes les minutes.
const RELIRE_MS = 60000

export default function useNouveaux(actif, cle) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!actif) return undefined
    let minuteur
    const lire = () =>
      api.nouveaux().then(
        (r) => setN(r.count),
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
