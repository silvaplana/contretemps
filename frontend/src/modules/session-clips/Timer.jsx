import { useEffect, useRef, useState } from 'react'
import { Deroulant } from './Labo.jsx'
import { CHRONO, CLOCHE } from './timerDessins.js'
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
const COUP_MS = 200 // l'écart des trois coups dans cloche-fin-de-round.mp3 (aussi dans sparring.css)
const DEPART = { mode: 'un', round: 180, repos: 60, nombre: 3, prevenir: true }

function lire() {
  try {
    return { ...DEPART, ...JSON.parse(localStorage.getItem(REGLAGES) || '{}') }
  } catch {
    return DEPART
  }
}

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

// Le temps en chiffres rouges à sept segments, comme sur une horloge de salle
// (Seb, 21/11). Les segments éteints restent à peine visibles.
const H = (y) => `9,${y} 14,${y - 5} 46,${y - 5} 51,${y} 46,${y + 5} 14,${y + 5}`
const V = (x, y) => `${x},${y} ${x + 5},${y + 5} ${x + 5},${y + 37} ${x},${y + 42} ${x - 5},${y + 37} ${x - 5},${y + 5}`
const SEGMENTS = { a: H(6), g: H(54), d: H(102), f: V(6, 9), b: V(54, 9), e: V(6, 57), c: V(54, 57) }
const ALLUMES = ['abcdef', 'bc', 'abged', 'abgcd', 'fgbc', 'afgcd', 'afgedc', 'abc', 'abcdefg', 'abcdfg']

function Afficheur({ texte, className }) {
  return (
    <div className={className} role="timer" aria-label={texte}>
      {[...texte].map((c, i) =>
        c === ':' ? (
          <svg key={i} viewBox="0 0 24 108" aria-hidden="true">
            <rect x="7" y="27" width="11" height="11" rx="2" />
            <rect x="7" y="70" width="11" height="11" rx="2" />
          </svg>
        ) : (
          <svg key={i} viewBox="0 0 60 108" aria-hidden="true">
            {Object.entries(SEGMENTS).map(([nom, points]) => (
              <polygon key={nom} points={points} className={ALLUMES[c].includes(nom) ? '' : 'sc-timer__eteint'} />
            ))}
          </svg>
        ),
      )}
    </div>
  )
}

export default function Timer() {
  const [r, setR] = useState(lire)
  const [run, setRun] = useState(null) // { phase: 'round'|'repos', n, fin (ms), total, pause (ms restants) }
  const [, setTic] = useState(0)
  // La cloche bouge comme elle sonne (Seb, 21/11) : un coup au début du round,
  // trois à la fin ou quand on arrête. { n: coups, id } relance l'animation.
  const [sonne, setSonne] = useState(null)
  const finSonne = useRef(null)
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

  function sonner(n) {
    jouer(n === 1 ? 'debut' : 'fin')
    clearTimeout(finSonne.current)
    setSonne((avant) => ({ n, id: (avant?.id ?? 0) + 1 }))
    finSonne.current = setTimeout(() => setSonne(null), n * COUP_MS + 900)
  }

  function phase(nom, n) {
    dit.current = new Set()
    const total = nom === 'round' ? r.round : r.repos
    if (nom === 'round') sonner(1)
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
          sonner(3)
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

  function pause() {
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
        <Afficheur className={`sc-timer__temps${run && !repos && reste <= 10 ? ' sc-timer__temps--fin' : ''}`} texte={mmss(reste)} />
        <div className="sc-timer__round">
          {r.mode === 'rounds' && (run ? `Round ${run.n} sur ${r.nombre}` : `${r.nombre} rounds`)}
        </div>
      </div>

      {/* Comme au bord du ring (Seb, 21/11) : la cloche démarre et arrête le
          round, le chronomètre ne sert qu'à Pause et Reprendre. Les deux
          restent toujours là ; le chronomètre est en retrait tant que rien ne tourne. */}
      <div className="sc-timer__dessins">
        <button
          type="button"
          className={`sc-timer__dessin${run?.pause != null ? ' sc-timer__dessin--reprendre' : ''}`}
          disabled={!run}
          onClick={pause}
        >
          <span dangerouslySetInnerHTML={{ __html: CHRONO }} />
          {/* Rien d'écrit sous le chronomètre tant que rien ne tourne (Seb, 21/11). */}
          <span className="sc-timer__mot">{!run ? '' : run.pause != null ? 'Reprendre' : 'Pause'}</span>
        </button>
        <button
          type="button"
          className={`sc-timer__dessin sc-timer__dessin--cloche${sonne ? ' sc-timer__dessin--sonne' : ''}`}
          style={sonne ? { '--coups': sonne.n } : undefined}
          onClick={() => {
            if (!run) return setRun(phase('round', 1))
            setRun(null)
            sonner(3)
          }}
        >
          <span key={sonne?.id ?? 0} dangerouslySetInnerHTML={{ __html: CLOCHE }} />
          <span className="sc-timer__mot">{run ? 'Arrêter' : 'Démarrer'}</span>
        </button>
      </div>

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
