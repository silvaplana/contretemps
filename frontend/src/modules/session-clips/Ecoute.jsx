import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import * as api from './api.js'

// Fights › ⋮ › Entraîner l'écoute (spec/modules/video-combats.md §5, Seb
// 14/11) : enregistrer chaque cri plusieurs fois, pour apprendre ces mots à
// l'écoute. Un appui = 2 s d'enregistrement, envoyé tout de suite.

const MOTS = [
  ['fight', 'Fight'],
  ['hajime', 'Hajime'],
  ['combat', 'Combat'],
  ['time', 'Time'],
]
const DUREE_MS = 2000
const OBJECTIF = 50

export default function Ecoute({ montrer }) {
  const [mot, setMot] = useState('fight')
  const [liste, setListe] = useState(null)
  const [enregistre, setEnregistre] = useState(false)
  const [lecture, setLecture] = useState(null)
  const audio = useRef(null)

  useEffect(() => {
    api.enregistrements().then(setListe, (e) => montrer(e.message))
  }, [montrer])

  async function enregistrer() {
    if (enregistre) return
    let flux
    try {
      flux = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      montrer('Le micro n’est pas autorisé.')
      return
    }
    setEnregistre(true)
    const morceaux = []
    const rec = new MediaRecorder(flux)
    rec.ondataavailable = (ev) => ev.data.size && morceaux.push(ev.data)
    rec.onstop = async () => {
      flux.getTracks().forEach((t) => t.stop())
      try {
        setListe(await api.envoyerEnregistrement(mot, new Blob(morceaux, { type: rec.mimeType || 'audio/webm' })))
      } catch (e) {
        montrer(e.message)
      } finally {
        setEnregistre(false)
      }
    }
    rec.start()
    setTimeout(() => rec.state !== 'inactive' && rec.stop(), DUREE_MS)
  }

  async function ecouter(nom) {
    try {
      const url = await api.lireEnregistrement(mot, nom)
      setLecture(nom)
      audio.current.src = url
      await audio.current.play()
    } catch (e) {
      montrer(e.message)
    }
  }

  async function effacer(nom) {
    try {
      await api.supprimerEnregistrement(mot, nom)
      setListe((l) => ({ ...l, [mot]: l[mot].filter((n) => n !== nom) }))
    } catch (e) {
      montrer(e.message)
    }
  }

  const sons = liste?.[mot] ?? []
  const libelle = MOTS.find(([id]) => id === mot)[1]
  return (
    <div className="sc-ecoute">
      <SegmentedTabs
        className="sc-onglets"
        value={mot}
        onChange={setMot}
        options={MOTS.map(([value, label]) => ({ value, label: `${label} (${liste?.[value]?.length ?? 0})` }))}
      />
      <p className="sc-meta">
        Touchez le bouton et criez « {libelle} ! » comme à l’entraînement. Variez les voix, la distance et le bruit de la
        salle : {OBJECTIF} enregistrements par mot.
      </p>
      <button type="button" className="btn btn--primary sc-tournage__bouton" disabled={enregistre || !liste} onClick={enregistrer}>
        {enregistre ? '● Criez maintenant…' : `● Enregistrer « ${libelle} ! »`}
      </button>
      <p className="sc-meta">
        {sons.length} / {OBJECTIF} enregistrés
      </p>
      <ul className="sc-ecoute__liste">
        {sons.map((nom, i) => (
          <li key={nom}>
            <button type="button" className="icon-btn" onClick={() => ecouter(nom)} aria-label="Écouter">
              <Icon name="play" size={22} />
            </button>
            <span>
              {libelle} {sons.length - i}
              {lecture === nom ? ' · lecture' : ''}
            </span>
            <button type="button" className="icon-btn" onClick={() => effacer(nom)} aria-label="Effacer">
              <Icon name="trash" size={22} />
            </button>
          </li>
        ))}
      </ul>
      <audio ref={audio} onEnded={() => setLecture(null)} />
    </div>
  )
}
