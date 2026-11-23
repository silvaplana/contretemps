import { useEffect, useRef, useState } from 'react'
import { Capacitor } from '@capacitor/core'
import { DANS_L_APPLI, Natif } from './natif.js'

// Le film du Timer étendu (Seb, 21/11) : la caméra arrière de ce téléphone,
// de la cloche du début à celle de la fin. `etat` : 'attente', 'pret' ou
// 'refus' (pas de caméra, ou refusée). Dans l'appli Android, c'est l'appli qui
// filme (useFilmNatif, Seb 23/11) ; ailleurs (Chrome, iPhone), la page.
export function useFilm(actif) {
  const natif = useFilmNatif(actif && FILM_NATIF)
  const page = useFilmPage(actif && !FILM_NATIF)
  return FILM_NATIF ? natif : page
}

// Une appli Android d'avant le 23/11 n'a pas encore la caméra du Timer.
const FILM_NATIF = DANS_L_APPLI && Capacitor.isPluginAvailable('Tournage')

function useHorloge() {
  const horloge = useRef({ debut: 0, pause: 0, depuis: null }) // le temps filmé, pauses ôtées
  return {
    partir() {
      horloge.current = { debut: performance.now(), pause: 0, depuis: null }
    },
    pause(oui) {
      const h = horloge.current
      if (oui && h.depuis == null) h.depuis = performance.now()
      if (!oui && h.depuis != null) {
        h.pause += performance.now() - h.depuis
        h.depuis = null
      }
    },
    temps() {
      const h = horloge.current
      return Math.max(0, ((h.depuis ?? performance.now()) - h.debut - h.pause) / 1000)
    },
  }
}

// La caméra de l'appli (camera/TimerCamera.kt) : 1080p, 30 images/s,
// 4 Mbit/s comme Tournage ; le sens du film est celui de l'écran, figé au
// premier coup de cloche. La miniature est une petite image relue 5 fois par
// seconde. Le film reste sur le téléphone et part par la file d'envoi
// d'Android, sans copie (videoUploads.js : fichier `{ chemin }`).
function useFilmNatif(actif) {
  const [etat, setEtat] = useState('attente')
  const [lampe, setLampe] = useState(false)
  const image = useRef(null)
  const enCours = useRef(false)
  const pret = useRef(false)
  const voulu = useRef(false)
  const horloge = useHorloge()

  function lancer() {
    enCours.current = true
    horloge.partir()
    Natif.timerRecord().catch(() => {
      enCours.current = false
      setEtat('refus')
    })
  }

  useEffect(() => {
    if (!actif) return undefined
    let fini = false
    let minuteur = null
    const relire = async () => {
      try {
        const s = await Natif.timerFrame()
        if (fini) return
        if (s.error) setEtat('refus')
        else if (s.open && !pret.current) {
          pret.current = true
          setEtat('pret')
          if (voulu.current && !enCours.current) lancer()
        }
        if (s.image && image.current) image.current.src = s.image
      } catch {
        // Pont occupé : à la prochaine.
      }
      if (!fini) minuteur = setTimeout(relire, 200)
    }
    Natif.timerOpen().then(relire, () => !fini && setEtat('refus'))
    return () => {
      fini = true
      clearTimeout(minuteur)
      enCours.current = false
      pret.current = false
      Natif.timerClose().catch(() => {})
      setEtat('attente')
      setLampe(false)
    }
  }, [actif]) // eslint-disable-line react-hooks/exhaustive-deps

  return {
    etat,
    natif: true,
    // La miniature : <img ref={film.brancher} alt="" />
    brancher(el) {
      image.current = el
    },
    lampe,
    allumer(oui) {
      setLampe(oui)
      Natif.timerLight({ on: oui }).catch(() => {})
    },
    demarrer() {
      voulu.current = true
      if (pret.current && !enCours.current) lancer()
    },
    pause(oui) {
      if (enCours.current) Natif.timerPause({ on: oui }).catch(() => {})
      horloge.pause(oui)
    },
    temps() {
      return enCours.current ? horloge.temps() : 0
    },
    // Le film du combat : `{ chemin, url, size, name, type }`, ou null.
    async arreter() {
      voulu.current = false
      if (!enCours.current) return null
      enCours.current = false
      const r = await Natif.timerStop().catch(() => ({}))
      if (!r.path) return null
      return { chemin: r.path, url: Capacitor.convertFileSrc(r.path), size: r.size, name: 'combat.mp4', type: 'video/mp4' }
    },
  }
}

function useFilmPage(actif) {
  const [etat, setEtat] = useState('attente')
  const [lampe, setLampe] = useState(undefined)
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
      // 1080p comme la caméra de Tournage et la compression du module Vidéos
      // (Seb, 23/11 : même qualité partout) ; le téléphone descend tout seul
      // s'il ne sait pas faire.
      video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
      // Le son brut, comme la caméra du Tournage.
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    })
    ;(demande ?? Promise.reject(new Error('pas de caméra'))).then(
      (f) => {
        if (fini) return f.getTracks().forEach((t) => t.stop())
        flux.current = f
        if (image.current) image.current.srcObject = f
        // La lampe, si le navigateur sait l'allumer (Chrome sur Android).
        if (f.getVideoTracks()[0]?.getCapabilities?.().torch) setLampe(false)
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
      setLampe(undefined)
    }
  }, [actif])

  return {
    etat,
    // `undefined` : pas de lampe à allumer d'ici.
    lampe,
    allumer(oui) {
      const piste = flux.current?.getVideoTracks()[0]
      if (!piste) return
      setLampe(oui)
      piste.applyConstraints({ advanced: [{ torch: oui }] }).catch(() => setLampe(undefined))
    },
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
