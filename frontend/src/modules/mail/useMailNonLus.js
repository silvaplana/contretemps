import { useEffect, useState } from 'react'
import * as api from './api.js'

// Pastilles des boîtes du club (spec/modules/mail.md §2, §4 bis) : non lus
// de la réception, le total (onglet Messages) et par boîte (sa puce), relus toutes les 2 minutes et après une lecture
// (api.signalerNonLus). Sans le droit ou Mail éteint : 0, et plus de relecture.
const RELIRE_MS = 120000
const VIDE = { total: 0, parBoite: {} }

export default function useMailNonLus(actif, ecoleId) {
  const [n, setN] = useState(VIDE)
  useEffect(() => {
    if (!actif) return undefined
    let minuteur
    const lire = () => {
      if (document.hidden) return
      api.nonLus(ecoleId).then(
        (r) => setN({ total: r.unread, parBoite: Object.fromEntries((r.boxes ?? []).map((b) => [b.id, b.unread])) }),
        () => {
          setN(VIDE)
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
  return actif ? n : VIDE
}
