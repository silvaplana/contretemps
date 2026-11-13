import { useEffect, useRef, useState } from 'react'
import { Deroulant } from './Labo.jsx'
import clocheDebut from './sons/cloche-debut-de-round.mp3'
import clocheFin from './sons/cloche-fin-de-round.mp3'
import clacClac from './sons/clac-clac-10-secondes.mp3'
import bips from './sons/bips-fin-du-repos.mp3'

// Fights › Timer (coachs ; Seb, 13/11, maquette https://claude.ai/artifact/2U8ASb7oeDcgbib9vwkyza) :
// un round seul, ou des rounds avec repos. Cloche d'un coup au début, clac clac
// 10 s avant la fin (case à cocher), trois coups à la fin, bips à la fin du repos.
// Le décompte suit l'horloge (pas les tics du navigateur, ralentis écran éteint).

const SONS = { debut: clocheDebut, fin: clocheFin, clac: clacClac, bips }
const REGLAGES = 'sc-timer'
const DEPART = { mode: 'un', round: 180, repos: 60, nombre: 3, prevenir: true }

function lire() {
  try {
    return { ...DEPART, ...JSON.parse(localStorage.getItem(REGLAGES) || '{}') }
  } catch {
    return DEPART
  }
}

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

export default function Timer() {
  const [r, setR] = useState(lire)
  const [run, setRun] = useState(null) // { phase: 'round'|'repos', n, fin (ms), total, pause (ms restants) }
  const [, setTic] = useState(0)
  const sons = useRef({})
  const dit = useRef(new Set()) // sons déjà joués dans cette phase
  const veille = useRef(null)

  useEffect(() => {
    for (const [k, f] of Object.entries(SONS)) sons.current[k] = new Audio(f)
  }, [])
  useEffect(() => {
    try {
      localStorage.setItem(REGLAGES, JSON.stringify(r))
    } catch {
      // stockage refusé : réglages pour cette fois
    }
  }, [r])

  function jouer(k) {
    const a = sons.current[k]
    if (!a) return
    a.currentTime = 0
    a.play().catch(() => {})
  }

  function phase(nom, n) {
    dit.current = new Set()
    const total = nom === 'round' ? r.round : r.repos
    if (nom === 'round') jouer('debut')
    return { phase: nom, n, total, fin: Date.now() + total * 1000, pause: null }
  }

  const reste = run ? Math.max(0, Math.ceil(((run.pause ?? run.fin - Date.now())) / 1000)) : r.round

  useEffect(() => {
    if (!run || run.pause != null) return
    const id = setInterval(() => {
      const left = Math.ceil((run.fin - Date.now()) / 1000)
      if (run.phase === 'round' && left <= 10 && left > 0 && r.prevenir && !dit.current.has('clac')) {
        dit.current.add('clac')
        jouer('clac')
      }
      if (run.phase === 'repos' && left <= 3 && left > 0 && !dit.current.has('bips')) {
        dit.current.add('bips')
        jouer('bips')
      }
      if (left <= 0) {
        if (run.phase === 'round') {
          jouer('fin')
          setRun(r.mode === 'rounds' && run.n < r.nombre ? phase('repos', run.n) : null)
        } else setRun(phase('round', run.n + 1))
      }
      setTic((t) => t + 1)
    }, 250)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, r])

  // L'écran reste allumé pendant le décompte, si le téléphone le permet.
  useEffect(() => {
    if (!run) return
    navigator.wakeLock?.request('screen').then(
      (v) => (veille.current = v),
      () => {},
    )
    return () => {
      veille.current?.release().catch(() => {})
      veille.current = null
    }
  }, [run == null]) // eslint-disable-line react-hooks/exhaustive-deps

  function demarrer() {
    if (!run) return setRun(phase('round', 1))
    if (run.pause != null) setRun({ ...run, fin: Date.now() + run.pause, pause: null })
    else setRun({ ...run, pause: run.fin - Date.now() })
  }

  const regler = (k, d, min, max) => setR((x) => ({ ...x, [k]: Math.min(max, Math.max(min, x[k] + d)) }))
  const repos = run?.phase === 'repos'
  const resume = r.mode === 'rounds' ? `${r.nombre} × ${mmss(r.round)} · repos ${mmss(r.repos)}` : mmss(r.round)

  return (
    <div className="sc-timer">
      <div className="sc-timer__modes" role="group" aria-label="Mode">
        {[
          ['un', 'Un round'],
          ['rounds', 'Rounds et repos'],
        ].map(([m, l]) => (
          <button key={m} type="button" aria-pressed={r.mode === m} disabled={!!run} onClick={() => setR({ ...r, mode: m })}>
            {l}
          </button>
        ))}
      </div>

      <div className="sc-timer__horloge">
        <div className={`sc-timer__phase${repos ? ' sc-timer__phase--repos' : run ? '' : ' sc-timer__phase--pret'}`}>
          {run ? (repos ? 'Repos' : 'Combat') : 'Prêt'}
        </div>
        <div className={`sc-timer__temps${run && !repos && reste <= 10 ? ' sc-timer__temps--fin' : ''}`}>{mmss(reste)}</div>
        <div className="sc-timer__round">
          {r.mode === 'rounds' && (run ? `Round ${run.n} sur ${r.nombre}` : `${r.nombre} rounds`)}
        </div>
        <div className="sc-timer__barre">
          <i
            className={repos ? 'sc-timer__barre--repos' : ''}
            style={{ width: run ? `${100 * (1 - reste / run.total)}%` : 0 }}
          />
        </div>
      </div>

      <button type="button" className="btn btn--primary sc-timer__go" onClick={demarrer}>
        {!run ? 'Démarrer' : run.pause != null ? 'Reprendre' : 'Pause'}
      </button>
      {run && (
        <button type="button" className="sc-timer__stop" onClick={() => setRun(null)}>
          Arrêter
        </button>
      )}

      {!run && (
        <Deroulant
          titre={
            <>
              Réglages <span className="sc-timer__resume">{resume}</span>
            </>
          }
        >
          <Ligne libelle="Durée du round" valeur={mmss(r.round)} moins={() => regler('round', -30, 30, 900)} plus={() => regler('round', 30, 30, 900)} min={r.round <= 30} />
          {r.mode === 'rounds' && (
            <>
              <Ligne libelle="Repos" valeur={mmss(r.repos)} moins={() => regler('repos', -15, 15, 300)} plus={() => regler('repos', 15, 15, 300)} min={r.repos <= 15} />
              <Ligne libelle="Nombre de rounds" valeur={r.nombre} moins={() => regler('nombre', -1, 1, 12)} plus={() => regler('nombre', 1, 1, 12)} min={r.nombre <= 1} />
            </>
          )}
          <label className="sc-timer__ligne sc-timer__case">
            <span>Prévenir 10 s avant la fin (clac clac)</span>
            <input type="checkbox" checked={r.prevenir} onChange={(e) => setR({ ...r, prevenir: e.target.checked })} />
          </label>
        </Deroulant>
      )}
    </div>
  )
}

function Ligne({ libelle, valeur, moins, plus, min }) {
  return (
    <div className="sc-timer__ligne">
      <span>{libelle}</span>
      <button type="button" aria-label={`${libelle} : moins`} onClick={moins} disabled={min}>
        −
      </button>
      <output>{valeur}</output>
      <button type="button" aria-label={`${libelle} : plus`} onClick={plus}>
        +
      </button>
    </div>
  )
}
