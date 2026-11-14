import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import * as api from './api.js'

// Fights › ⋮ › Entraîner l'écoute (spec/modules/video-combats.md §5, Seb
// 14/11) : enregistrer chaque cri plusieurs fois, pour apprendre ces mots à
// l'écoute. Un appui = 2 s d'enregistrement, envoyé tout de suite.

const MOTS = [
  ['hajime', 'Hajime'],
  ['combat', 'Combat'],
  ['time', 'Time'],
]
const DUREE_MS = 2000
const OBJECTIF = 20
const TEST_MS = 10000 // « Tester » : 10 s écoutées par l'écoute du club (Seb, 14/11)
const ANNULER_MS = 10000
const virgule = (x, n) => x.toFixed(n).replace('.', ',')

// Le micro pendant `ms` millisecondes ; null si le micro est refusé.
async function enregistrerSon(ms) {
  let flux
  try {
    // Le son brut, comme la caméra du Tournage (étude du 14/11) : sans la
    // réduction de bruit ni le gain automatique du navigateur.
    flux = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    })
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
  const [mot, setMot] = useState('hajime')
  const [liste, setListe] = useState(null)
  const [enregistre, setEnregistre] = useState(false)
  const [lecture, setLecture] = useState(null)
  const [test, setTest] = useState(null) // 'ecoute' puis 'analyse'
  const [resultat, setResultat] = useState(null)
  const [testNom, setTestNom] = useState(null)
  const [reponses, setReponses] = useState({}) // moment -> ce qui a été rangé
  const [quelMot, setQuelMot] = useState(null) // moment dont on choisit le mot (Mauvais)
  const [manques, setManques] = useState([]) // « Il manque un mot » : les mots ajoutés
  const [choixManque, setChoixManque] = useState(false)
  const [historique, setHistorique] = useState([])
  const [rejoue, setRejoue] = useState(false)
  const audio = useRef(null)

  useEffect(() => {
    api.rejeux().then(setHistorique, () => {})
  }, [])

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
      setManques([])
      setChoixManque(false)
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

  async function manque(word) {
    try {
      await api.motManque(testNom, word)
      setManques((m) => [...m, MOTS.find(([id]) => id === word)[1]])
      setChoixManque(false)
    } catch (e) {
      montrer(e.message)
    }
  }

  // Rejouer tous les essais (Seb, 14/11) : les points de l'écoute du club sur tous les tests répondus.
  async function rejouer() {
    if (rejoue) return
    setRejoue(true)
    try {
      await api.rejouerEssais()
      for (let i = 0; i < 300; i++) {
        await new Promise((ok) => setTimeout(ok, 2000))
        const h = await api.rejeux()
        setHistorique(h)
        if (h.length && h[h.length - 1].done) return
      }
    } catch (e) {
      montrer(e.message)
    } finally {
      setRejoue(false)
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

  // Deux boutons (Seb, 14/11) : les enregistrements des mots, ou les tests
  // avec leurs réponses et les points. Effacés au bout de 10 s, sauf Annuler.
  const [cache, setCache] = useState(null) // 'mots' ou 'tests' pendant les 10 s
  function effacerTout(quoi) {
    setCache(quoi)
    if (quoi === 'tests') setResultat(null)
    const retard = setTimeout(async () => {
      try {
        if (quoi === 'mots') {
          await api.effacerEnregistrements()
          setListe(await api.enregistrements())
        } else {
          await api.effacerTests()
          setHistorique([])
        }
      } catch (e) {
        montrer(e.message)
      } finally {
        setCache(null)
      }
    }, ANNULER_MS)
    montrer(quoi === 'mots' ? 'Enregistrements effacés' : 'Tests effacés', () => {
      clearTimeout(retard)
      setCache(null)
    })
  }

  const sons = cache === 'mots' ? [] : (liste?.[mot] ?? [])
  const libelle = MOTS.find(([id]) => id === mot)[1]
  return (
    <div className="sc-ecoute">
      <SegmentedTabs
        className="sc-onglets"
        value={mot}
        onChange={setMot}
        options={MOTS.map(([value, label]) => ({
          value,
          label: `${label} (${cache === 'mots' ? 0 : (liste?.[value]?.length ?? 0)})`,
        }))}
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
      {Object.values(liste ?? {}).some((l) => l.length) && cache !== 'mots' && (
        <button type="button" className="btn" disabled={!!cache} onClick={() => effacerTout('mots')}>
          Effacer tous les enregistrements
        </button>
      )}
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
      {resultat && (
        <div className="sc-ecoute__choix">
          {manques.length > 0 && <span className="sc-meta">Ajouté : {manques.join(', ')}</span>}
          {choixManque ? (
            MOTS.map(([id, l]) => (
              <button key={id} type="button" className="btn" onClick={() => manque(id)}>
                {l}
              </button>
            ))
          ) : (
            <button type="button" className="btn" onClick={() => setChoixManque(true)}>
              Il manque un mot
            </button>
          )}
        </div>
      )}
      <p className="sc-meta">Progrès de l’écoute du club</p>
      <p className="sc-meta">
        Réécoute tous les tests où vous avez répondu : +1 par bon mot, −1 par mauvais, −2 par mot inventé, −1 par mot
        oublié. Répondez à tous les mots d’un test.
      </p>
      <button type="button" className="btn sc-tournage__bouton" disabled={rejoue} onClick={rejouer}>
        {rejoue ? 'Réécoute en cours…' : 'Rejouer tous les essais'}
      </button>
      {cache !== 'tests' && <Progres historique={historique.filter((h) => h.done)} />}
      <button type="button" className="btn" disabled={!!cache || rejoue || !!test} onClick={() => effacerTout('tests')}>
        Effacer tous les tests
      </button>
      <audio ref={audio} onEnded={() => setLecture(null)} />
    </div>
  )
}

// La courbe des points (en % du meilleur possible) et la liste des rejeux, le plus récent en haut.
function Progres({ historique }) {
  if (!historique.length) return null
  const pct = (h) => (h.best ? Math.max(0, Math.min(100, (100 * h.points) / h.best)) : 0)
  const W = 300
  const H = 80
  const x = (i) => (historique.length === 1 ? W / 2 : 10 + (i * (W - 20)) / (historique.length - 1))
  const y = (h) => H - 8 - (pct(h) * (H - 16)) / 100
  const quand = (h) =>
    new Date(h.at * 1000).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  return (
    <>
      <svg className="sc-ecoute__courbe" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Points de l’écoute du club, rejeu après rejeu">
        <polyline points={historique.map((h, i) => `${x(i)},${y(h)}`).join(' ')} />
        {historique.map((h, i) => (
          <circle key={h.at} cx={x(i)} cy={y(h)} r="4" />
        ))}
      </svg>
      <ul className="sc-ecoute__liste">
        {[...historique].reverse().map((h) => (
          <li key={h.at}>
            <span>
              {quand(h)} · {h.points} points sur {h.best} · {h.tests} tests, {h.examples} exemples
              <small className="sc-meta">
                {' '}
                (bons {h.good}, mauvais {h.wrong}, inventés {h.invented}, oubliés {h.missed})
              </small>
              {h.min_score != null && (
                <small className="sc-meta sc-ecoute__mot">
                  Réglage trouvé : ressemblance au moins {virgule(h.min_score, 2)}, avance sur le 2e mot au moins{' '}
                  {virgule(h.min_margin, 2)}
                </small>
              )}
              {/* Mot par mot (étude du 14/11) : pour choisir le mot du début. */}
              {h.words &&
                MOTS.map(([id, l]) => {
                  const w = h.words[id]
                  if (!w) return null
                  const pris = Object.entries(w.heard_as)
                    .map(([autre, n]) => `${n} pris pour ${MOTS.find(([x]) => x === autre)?.[1] ?? autre}`)
                    .join(', ')
                  return (
                    <small key={id} className="sc-meta sc-ecoute__mot">
                      {l} : {w.good} bons, {w.missed} oubliés, {w.invented} inventés, {w.wrong} à la place d’un autre mot
                      {pris ? `, ${pris}` : ''}
                    </small>
                  )
                })}
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}
