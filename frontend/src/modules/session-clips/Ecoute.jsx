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
const OBJECTIF = 20
const TEST_MS = 10000 // « Tester » : 10 s écoutées par l'écoute du club (Seb, 14/11)
const virgule = (x, n) => x.toFixed(n).replace('.', ',')

// Le micro pendant `ms` millisecondes ; null si le micro est refusé.
async function enregistrerSon(ms) {
  let flux
  try {
    flux = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    return null
  }
  const morceaux = []
  const rec = new MediaRecorder(flux)
  rec.ondataavailable = (ev) => ev.data.size && morceaux.push(ev.data)
  const fini = new Promise((ok) => (rec.onstop = ok))
  rec.start()
  setTimeout(() => rec.state !== 'inactive' && rec.stop(), ms)
  await fini
  flux.getTracks().forEach((t) => t.stop())
  return new Blob(morceaux, { type: rec.mimeType || 'audio/webm' })
}

export default function Ecoute({ montrer }) {
  const [mot, setMot] = useState('fight')
  const [liste, setListe] = useState(null)
  const [enregistre, setEnregistre] = useState(false)
  const [lecture, setLecture] = useState(null)
  const [test, setTest] = useState(null) // 'ecoute' puis 'analyse'
  const [resultat, setResultat] = useState(null)
  const [testNom, setTestNom] = useState(null)
  const [reponses, setReponses] = useState({}) // moment -> ce qui a été rangé
  const [quelMot, setQuelMot] = useState(null) // moment dont on choisit le mot (Mauvais)
  const audio = useRef(null)

  useEffect(() => {
    api.enregistrements().then(setListe, (e) => montrer(e.message))
  }, [montrer])

  async function enregistrer() {
    if (enregistre || test) return
    setEnregistre(true)
    try {
      const son = await enregistrerSon(DUREE_MS)
      if (son) setListe(await api.envoyerEnregistrement(mot, son))
      else montrer('Le micro n’est pas autorisé.')
    } catch (e) {
      montrer(e.message)
    } finally {
      setEnregistre(false)
    }
  }

  // Tester : 10 s au micro, puis les mots reconnus par l'écoute du club.
  async function tester() {
    if (enregistre || test) return
    setResultat(null)
    setTest('ecoute')
    try {
      const son = await enregistrerSon(TEST_MS)
      if (!son) {
        montrer('Le micro n’est pas autorisé.')
        return
      }
      setTest('analyse')
      const { name } = await api.envoyerTest(son)
      setTestNom(name)
      setReponses({})
      for (let i = 0; i < 60; i++) {
        await new Promise((ok) => setTimeout(ok, 2000))
        const r = await api.resultatTest(name)
        if (r.done) {
          setResultat(r.words)
          return
        }
      }
      montrer('Pas de réponse : réessayez dans un moment.')
    } catch (e) {
      montrer(e.message)
    } finally {
      setTest(null)
    }
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

  // Bon, Mauvais ou Inventé (Seb, 14/11) : le cri est rangé comme exemple.
  async function repondre(w, answer, word) {
    try {
      await api.repondreTest(testNom, { t: w.t, answer, word })
      const nomMot = MOTS.find(([id]) => id === word)?.[1]
      setReponses((r) => ({
        ...r,
        [w.t]: answer === 'invented' ? 'Rangé : inventé' : nomMot ? `Rangé : « ${nomMot} »` : 'Rangé : autre mot',
      }))
      setQuelMot(null)
      if (nomMot) setListe(await api.enregistrements())
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
      <button type="button" className="btn btn--primary sc-tournage__bouton" disabled={enregistre || !!test || !liste} onClick={enregistrer}>
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
      <p className="sc-meta">Tester l’écoute du club</p>
      <p className="sc-meta">Touchez « Tester », puis parlez et criez des mots pendant 10 s : l’appli montre ce qu’elle a reconnu.</p>
      <button type="button" className="btn sc-tournage__bouton" disabled={enregistre || !!test} onClick={tester}>
        {test === 'ecoute' ? '● Parlez et criez…' : test === 'analyse' ? 'Écoute en cours…' : 'Tester (10 s)'}
      </button>
      {resultat &&
        (resultat.length ? (
          <ul className="sc-ecoute__liste">
            {resultat.map((w) => (
              <li key={w.t} className="sc-ecoute__trouve">
                <span>
                  « {MOTS.find(([id]) => id === w.kind)?.[1] ?? w.kind} ! » à {virgule(w.t, 1)} s · sûr {virgule(w.note, 2)} ·{' '}
                  {Math.round(w.db)} dB
                </span>
                {reponses[w.t] ? (
                  <span className="sc-meta">{reponses[w.t]}</span>
                ) : quelMot === w.t ? (
                  <span className="sc-ecoute__choix">
                    {[...MOTS.filter(([id]) => id !== w.kind), ['other', 'Autre mot']].map(([id, l]) => (
                      <button key={id} type="button" className="btn" onClick={() => repondre(w, 'wrong', id)}>
                        {l}
                      </button>
                    ))}
                  </span>
                ) : (
                  <span className="sc-ecoute__choix">
                    <button type="button" className="btn" onClick={() => repondre(w, 'good', w.kind)}>
                      Bon
                    </button>
                    <button type="button" className="btn" onClick={() => setQuelMot(w.t)}>
                      Mauvais
                    </button>
                    <button type="button" className="btn" onClick={() => repondre(w, 'invented')}>
                      Inventé
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>Aucun cri reconnu.</p>
        ))}
      <audio ref={audio} onEnded={() => setLecture(null)} />
    </div>
  )
}
