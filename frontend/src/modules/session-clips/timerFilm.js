import { useEffect, useRef, useState } from 'react'

// Le film du Timer étendu (Seb, 21/11) : la caméra arrière de ce téléphone,
// de la cloche du début à celle de la fin. `etat` : 'attente', 'pret' ou
// 'refus' (pas de caméra, ou refusée).
export function useFilm(actif) {
  const [etat, setEtat] = useState('attente')
  const flux = useRef(null)
  const image = useRef(null)
  const rec = useRef(null)
  const morceaux = useRef([])
  const voulu = useRef(false) // « Démarrer » touché avant que la caméra soit prête
  const horloge = useRef({ debut: 0, pause: 0, depuis: null }) // le temps filmé, pauses ôtées

  function lancer() {
    morceaux.current = []
    const nature = ['video/mp4', 'video/webm'].find((t) => MediaRecorder.isTypeSupported(t))
    const r = new MediaRecorder(flux.current, { ...(nature && { mimeType: nature }), videoBitsPerSecond: 4_000_000 })
    r.ondataavailable = (ev) => ev.data.size && morceaux.current.push(ev.data)
    r.start(1000)
    rec.current = r
    horloge.current = { debut: performance.now(), pause: 0, depuis: null }
  }

  useEffect(() => {
    if (!actif) return undefined
    let fini = false
    const demande = navigator.mediaDevices?.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      // Le son brut, comme la caméra du Tournage.
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    })
    ;(demande ?? Promise.reject(new Error('pas de caméra'))).then(
      (f) => {
        if (fini) return f.getTracks().forEach((t) => t.stop())
        flux.current = f
        if (image.current) image.current.srcObject = f
        setEtat('pret')
        if (voulu.current) lancer()
      },
      () => !fini && setEtat('refus'),
    )
    return () => {
      fini = true
      if (rec.current?.state !== 'inactive') rec.current?.stop()
      rec.current = null
      flux.current?.getTracks().forEach((t) => t.stop())
      flux.current = null
      setEtat('attente')
    }
  }, [actif])

  return {
    etat,
    // La miniature : <video ref={film.brancher} muted playsInline autoPlay />
    brancher(el) {
      image.current = el
      if (el && flux.current && el.srcObject !== flux.current) el.srcObject = flux.current
    },
    demarrer() {
      voulu.current = true
      if (flux.current && !rec.current) lancer()
    },
    pause(oui) {
      if (rec.current?.state === (oui ? 'recording' : 'paused')) rec.current[oui ? 'pause' : 'resume']()
      const h = horloge.current
      if (oui && h.depuis == null) h.depuis = performance.now()
      if (!oui && h.depuis != null) {
        h.pause += performance.now() - h.depuis
        h.depuis = null
      }
    },
    // Où en est la vidéo (secondes) : pour placer le chrono incrusté.
    temps() {
      const h = horloge.current
      if (!rec.current) return 0
      return Math.max(0, ((h.depuis ?? performance.now()) - h.debut - h.pause) / 1000)
    },
    // Le fichier du combat, ou null si rien n'a été filmé.
    arreter() {
      voulu.current = false
      const r = rec.current
      rec.current = null
      if (!r) return Promise.resolve(null)
      return new Promise((ok) => {
        r.onstop = () => {
          const nature = (r.mimeType || 'video/webm').split(';')[0]
          ok(morceaux.current.length ? new File(morceaux.current, `combat.${nature.includes('mp4') ? 'mp4' : 'webm'}`, { type: nature }) : null)
        }
        r.stop()
      })
    },
  }
}
