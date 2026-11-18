import { useEffect, useState } from 'react'
import * as api from './api.js'

// Pastille de la boîte du club (spec/modules/mail.md §2) : non lus de la
// réception, relus toutes les 2 minutes et après une lecture
// (api.signalerNonLus). Sans le droit ou Mail éteint : 0, et plus de relecture.
const RELIRE_MS = 120000

export default function useMailNonLus(actif, ecoleId) {
  const [n, setN] = useState(0)
  useEffect(() => {
    if (!actif) return undefined
    let minuteur
    const lire = () => {
      if (document.hidden) return
      api.nonLus(ecoleId).then(
        (r) => setN(r.unread),
        () => {
          setN(0)
          clearInterval(minuteur)
          window.removeEventListener('mail:non-lus', lire)
        },
      )
    }
    lire()
    minuteur = setInterval(lire, RELIRE_MS)
    window.addEventListener('mail:non-lus', lire)
    document.addEventListener('visibilitychange', lire)
    return () => {
      clearInterval(minuteur)
      window.removeEventListener('mail:non-lus', lire)
      document.removeEventListener('visibilitychange', lire)
    }
  }, [actif, ecoleId])
  return actif ? n : 0
}
