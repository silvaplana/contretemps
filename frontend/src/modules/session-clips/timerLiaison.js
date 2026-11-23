import { useEffect, useRef, useState } from 'react'
import * as api from './api.js'

// Le Timer télécommandé (Seb, 23/11 ; maquette
// https://claude.ai/artifact/CYdzVr6fwkGb466jYWsAAo) : un téléphone est la
// caméra (il filme, sonne, éclaire et tient le chrono), l'autre la
// télécommande (il donne les ordres et voit ce que fait la caméra). Les deux
// passent par le serveur (session_clips/timer_link.py), toutes les 400 ms.
const PAS_MS = 400

// La caméra : dépose son état (`etat()`, lu au moment d'envoyer ; et une petite image une fois sur deux), prend
// les ordres de la télécommande. Rend vrai si une télécommande la pilote.
export function useLienCamera(actif, etat, photo, onOrdre) {
  const [relie, setRelie] = useState(false)
  const dernier = useRef({})
  useEffect(() => {
    dernier.current = { etat, photo, onOrdre }
  })
  useEffect(() => {
    if (!actif) return undefined
    let fini = false
    let minuteur = null
    let n = 0
    const tour = async () => {
      try {
        const image = n++ % 2 === 0 ? await dernier.current.photo?.() : null
        const r = await api.lienCamera(dernier.current.etat(), image ?? null)
        if (fini) return
        setRelie(r.linked)
        r.orders.forEach((o) => dernier.current.onOrdre(o))
      } catch {
        if (!fini) setRelie(false)
      }
      if (!fini) minuteur = setTimeout(tour, PAS_MS)
    }
    tour()
    return () => {
      fini = true
      clearTimeout(minuteur)
      setRelie(false)
      api.lienCamera(null, null).catch(() => {})
    }
  }, [actif])
  return relie
}

// La télécommande : envoie ses ordres aussitôt, reçoit l'état de la caméra
// (`etat`, null sans caméra), `recu` (l'heure de réception, pour faire
// tourner le chrono entre deux nouvelles) et la dernière image.
export function useTelecommande(actif) {
  const [lien, setLien] = useState({ relie: false, etat: null, recu: 0 })
  const [image, setImage] = useState(null)
  const ordres = useRef([])
  const vue = useRef(0)
  const reveil = useRef(null)
  useEffect(() => {
    if (!actif) return undefined
    let fini = false
    let minuteur = null
    let enRoute = false
    const tour = async () => {
      clearTimeout(minuteur)
      if (enRoute) return
      enRoute = true
      const envoyes = ordres.current
      ordres.current = []
      try {
        const r = await api.lienTelecommande(envoyes, vue.current)
        if (fini) return
        vue.current = r.frame_id
        if (r.frame) setImage(r.frame)
        else if (!r.linked) setImage(null)
        setLien({ relie: r.linked, etat: r.state, recu: Date.now() })
      } catch {
        ordres.current = [...envoyes, ...ordres.current]
        if (!fini) setLien((l) => ({ ...l, relie: false }))
      }
      enRoute = false
      if (!fini) minuteur = setTimeout(tour, ordres.current.length ? 0 : PAS_MS)
    }
    reveil.current = tour
    tour()
    return () => {
      fini = true
      clearTimeout(minuteur)
      reveil.current = null
      setLien({ relie: false, etat: null, recu: 0 })
      setImage(null)
    }
  }, [actif])
  return {
    ...lien,
    image,
    envoyer(ordre) {
      ordres.current.push(ordre)
      reveil.current?.()
    },
  }
}
