import QrScanner from 'qr-scanner'
import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from './api.js'

// Admin > Essais > Scanner les QR codes (spec/modules/essai.md §4), repris de
// Sambo Admin : caméra arrière en continu (bibliothèque qr-scanner, qui lit
// aussi sur iPhone). Chaque code lu s'ajoute en haut de la liste et la caméra
// continue : plusieurs élèves à la suite sans rien toucher. Un même code
// n'est envoyé qu'une fois tant que l'écran est ouvert.

const dateFr = (iso) => {
  const [a, m, j] = (iso ?? '').split('-')
  return iso ? `${j}/${m}/${a}` : '…'
}

// Message et couleur d'un résultat (backend Trials.check_in).
function message(r) {
  if (r.erreur) return { texte: r.erreur, couleur: 'rouge' }
  if (r.status === 'added' && r.course === 1) return { texte: "ok pour le cours d'essai 1 aujourd'hui", couleur: 'vert' }
  if (r.status === 'added') return { texte: "ok pour le cours d'essai 2 aujourd'hui (dernier)", couleur: 'orange' }
  if (r.status === 'today') return { texte: "déjà noté aujourd'hui", couleur: 'vert' }
  if (r.status === 'full') {
    const s = r.student
    return { texte: `les 2 cours d'essai ont déjà été faits le ${dateFr(s.course1_date)} et le ${dateFr(s.course2_date)}`, couleur: 'rouge' }
  }
  return { texte: 'Code inconnu', couleur: 'rouge' }
}

export default function Scanner({ ecoleId, code, onRetour, onNote }) {
  const video = useRef(null)
  const vus = useRef(new Set())
  const cle = useRef(0)
  const [resultats, setResultats] = useState([])
  const [camera, setCamera] = useState('')

  const verifier = useCallback(
    async (lu) => {
      if (vus.current.has(lu)) return
      vus.current.add(lu)
      let r
      try {
        r = await api.scanner(ecoleId, lu)
        if (r.student) onNote(r.student)
        if (r.status === 'added') navigator.vibrate?.(200)
      } catch (e) {
        r = { erreur: e.message }
      }
      cle.current += 1
      setResultats((l) => [{ ...r, cle: cle.current }, ...l])
    },
    [ecoleId, onNote],
  )

  // Le code qui a ouvert l'appli (appareil photo du téléphone).
  useEffect(() => {
    if (code) verifier(code)
  }, [code, verifier])

  // Caméra allumée tant que l'écran est ouvert. Démarrée au tour suivant :
  // un écran ouvert puis aussitôt refermé (StrictMode) ne la démarre pas, sinon
  // l'arrêt tardif du premier essai coupait l'image du second.
  useEffect(() => {
    let scanner = null
    const depart = setTimeout(() => {
      scanner = new QrScanner(video.current, (lu) => verifier(lu.data), {
        preferredCamera: 'environment',
        highlightScanRegion: true,
        returnDetailedScanResult: true,
        maxScansPerSecond: 8,
      })
      scanner.start().catch(() =>
        setCamera("Caméra indisponible : autorisez l'accès à la caméra pour ce site dans les réglages du navigateur."),
      )
    })
    return () => {
      clearTimeout(depart)
      scanner?.destroy()
    }
  }, [verifier])

  return (
    <div className="admin-panel essais">
      <div className="essais__retour">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          ←
        </button>
        <h2>Scanner les QR codes</h2>
      </div>
      <div className="essais__camera">
        <video ref={video} muted playsInline />
      </div>
      {camera && <p className="login-screen__erreur">{camera}</p>}
      {resultats.length === 0 && !camera && <p className="muted">Présentez le QR code de l'élève devant la caméra.</p>}
      <ul className="essais__scans">
        {resultats.map((r) => {
          const m = message(r)
          return (
            <li key={r.cle} className={`essais__scan essais__scan--${m.couleur}`}>
              {r.student && <strong>{`${r.student.first_name} ${r.student.last_name}`}</strong>}
              <span>{m.texte}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
