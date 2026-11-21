import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Deroulant } from './Labo.jsx'
import { CAMERA, CHRONO, CLOCHE, POING } from './timerDessins.js'
import { ecrire, estEtendu, lire } from './timerReglages.js'
import { useFilm } from './timerFilm.js'
import { DANS_L_APPLI, Natif } from './natif.js'
import { demarrerTeleversement, finaliserTeleversement } from '../../utils/videoUploads.js'
import * as api from './api.js'
import clocheDebut from './sons/cloche-debut-de-round.mp3'
import clocheFin from './sons/cloche-fin-de-round.mp3'
import clacClac from './sons/clac-clac-10-secondes.mp3'
import bips from './sons/bips-fin-du-repos.mp3'

// Fights › Timer (coachs ; Seb, 13/11, maquette https://claude.ai/artifact/2U8ASb7oeDcgbib9vwkyza) :
// un round seul, ou des rounds avec repos. Cloche d'un coup au début, clac clac
// 10 s avant la fin (case à cocher), trois coups à la fin, bips à la fin du repos.
// Le décompte suit l'horloge (pas les tics du navigateur, ralentis écran éteint).

const SONS = { debut: clocheDebut, fin: clocheFin, clac: clacClac, bips }
const COUP_MS = 200 // l'écart des trois coups dans cloche-fin-de-round.mp3 (aussi dans sparring.css)
const ANNULER_MS = 10000
const RETARD_S = 5 // le retardateur : la cloche sonne 5 s après (Seb, 21/11)
const plat = (t) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

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

// Timer étendu : un nom à taper. On touche « … », les premières lettres
// proposent les membres, Entrée ou un appui valide (Seb, 21/11).
function ChampNom({ nom, autre, membres, libelle, onChoisir }) {
  const [texte, setTexte] = useState(null) // null : pas en train de taper
  const debut = plat((texte ?? '').trim())
  const propositions =
    texte === null
      ? []
      : membres
          .filter((m) => m.id !== autre?.id && plat(m.name).split(/\s+/).some((mot) => mot.startsWith(debut)))
          .slice(0, 3)
  const choisir = (m) => {
    onChoisir(m)
    setTexte(null)
    document.activeElement?.blur()
  }
  return (
    <div className="sc-te__champ">
      <input
        value={texte ?? nom?.name ?? ''}
        placeholder="…"
        aria-label={libelle}
        autoComplete="off"
        enterKeyHint="done"
        onFocus={() => setTexte('')}
        onChange={(ev) => setTexte(ev.target.value)}
        onKeyDown={(ev) => ev.key === 'Enter' && (propositions[0] ? choisir(propositions[0]) : ev.target.blur())}
        onBlur={() => setTexte(null)}
      />
      {propositions.length > 0 && (
        <div className="sc-te__propositions">
          {propositions.map((m) => (
            // Sans prendre la main au champ : l'appui choisit avant que la liste se ferme.
            <button key={m.id} type="button" onPointerDown={(ev) => ev.preventDefault()} onClick={() => choisir(m)}>
              {m.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Timer({ ecoleId, rafraichir }) {
  const [r, setR] = useState(lire)
  // Timer étendu (Seb, 21/11) : en paysage, il filme le combat, nomme les deux
  // combattants et déclare le résultat, selon les cases de Paramètres du Timer.
  const etendu = estEtendu(r)
  const [noms, setNoms] = useState([null, null]) // { id, name } des deux combattants
  const [resultat, setResultat] = useState(null) // 0 ou 1 (la place du vainqueur), 'nul', ou rien
  const [termine, setTermine] = useState(false) // le combat vient de finir : on attend le résultat
  const [fin, setFin] = useState(null) // { fichier, url } : le combat filmé, à archiver, partager ou jeter
  const [retard, setRetard] = useState(0) // secondes avant la cloche (retardateur)
  const bip = useRef(null)
  const [message, setMessage] = useState(null) // { texte, annuler }
  const [membres, setMembres] = useState([])
  const finMessage = useRef(null)
  const [run, setRun] = useState(null) // { phase: 'round'|'repos', n, fin (ms), total, pause (ms restants) }
  const [, setTic] = useState(0)
  // La cloche bouge comme elle sonne (Seb, 21/11) : un coup au début du round,
  // trois à la fin ou quand on arrête. { n: coups, id } relance l'animation.
  const [sonne, setSonne] = useState(null)
  // Dès qu'on ouvre le Timer, il prend tout l'écran, sans le reste de l'appli
  // (ni en-tête ni barre du bas) ; une croix discrète en haut à droite en sort
  // (Seb, 21/11).
  const [plein, setPlein] = useState(true)
  const finSonne = useRef(null)
  const sons = useRef({})
  const dit = useRef(new Set()) // sons déjà joués dans cette phase
  const veille = useRef(null)

  useEffect(() => {
    for (const [k, f] of Object.entries(SONS)) sons.current[k] = new Audio(f)
  }, [])
  useEffect(() => ecrire(r), [r])
  const film = useFilm(etendu && r.film && plein)
  useEffect(() => {
    if (r.noms) api.membres().then(setMembres, () => {})
  }, [r.noms])
  // Tout se passe en paysage : l'appli Tournage tourne l'écran elle-même,
  // le navigateur le fait s'il le permet. Sinon, on demande de tourner le téléphone.
  useEffect(() => {
    if (!etendu || !plein) return undefined
    if (DANS_L_APPLI) Natif.landscape({ on: true }).catch(() => {})
    else {
      Promise.resolve(document.documentElement.requestFullscreen?.())
        .catch(() => {})
        .then(() => screen.orientation?.lock?.('landscape'))
        .catch(() => {})
    }
    return () => {
      if (DANS_L_APPLI) Natif.landscape({ on: false }).catch(() => {})
      else {
        screen.orientation?.unlock?.()
        if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
      }
    }
  }, [etendu, plein])

  // Le « tin » du retardateur, à chaque seconde.
  function tin() {
    try {
      bip.current ??= new AudioContext()
      const ctx = bip.current
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.frequency.value = 880
      g.gain.setValueAtTime(0.3, ctx.currentTime)
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15)
      o.connect(g).connect(ctx.destination)
      o.start()
      o.stop(ctx.currentTime + 0.15)
    } catch {
      // pas de son : le compte à rebours se voit
    }
  }
  useEffect(() => {
    if (!retard) return undefined
    const id = setTimeout(() => {
      if (retard > 1) {
        tin()
        setRetard(retard - 1)
      } else debuter()
    }, 1000)
    return () => clearTimeout(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retard])

  function dire(texte, annuler) {
    clearTimeout(finMessage.current)
    setMessage({ texte, annuler })
    finMessage.current = setTimeout(() => setMessage(null), annuler ? ANNULER_MS : 5000)
  }

  function debuter() {
    setPlein(true)
    setRetard(0)
    if (etendu) {
      setResultat(null)
      setTermine(false)
      setMessage(null)
      if (r.film) film.demarrer()
    }
    setRun(phase('round', 1))
  }

  // Fin du combat : dernier round fini, ou cloche touchée.
  function terminer() {
    setRun(null)
    sonner(3)
    if (!etendu) return
    setTermine(true)
    if (r.film) film.arreter().then((fichier) => fichier && setFin({ fichier, url: URL.createObjectURL(fichier) }))
  }

  function suivant() {
    setFin(null)
    setNoms([null, null])
    setResultat(null)
    setTermine(false)
  }

  const titre = () => (noms.some(Boolean) ? noms.map((n) => n?.name ?? '?').join(' vs ') : 'Combat')

  // « Archiver » : le combat part dans Combats, l'envoi continue derrière.
  async function archiver() {
    const corps = { people: noms.map((n) => n?.id ?? null), winner: typeof resultat === 'number' ? resultat : null, draw: resultat === 'nul' }
    const { fichier, url } = fin
    const nom = titre()
    suivant()
    URL.revokeObjectURL(url)
    try {
      const uploadId = await demarrerTeleversement(ecoleId, fichier)
      await finaliserTeleversement(uploadId, async (id) => (await api.filmerCombat({ upload_id: id, ...corps })).video)
      dire(`${nom} : archivé dans Combats`)
      rafraichir?.()
    } catch (e) {
      dire(e.message)
    }
  }

  // « Partager » : le menu du téléphone (WhatsApp…) ; sinon la vidéo est téléchargée.
  async function partager() {
    try {
      if (navigator.canShare?.({ files: [fin.fichier] })) await navigator.share({ files: [fin.fichier], title: titre() })
      else {
        const lien = document.createElement('a')
        lien.href = fin.url
        lien.download = fin.fichier.name
        lien.click()
        dire('Vidéo téléchargée')
      }
    } catch (e) {
      if (e.name !== 'AbortError') dire(e.message)
    }
  }

  // « Jeter » : Annuler pendant 10 s.
  function jeter() {
    const avant = { fin, noms, resultat }
    suivant()
    dire('Combat jeté', () => {
      setFin(avant.fin)
      setNoms(avant.noms)
      setResultat(avant.resultat)
      setTermine(true)
      setMessage(null)
    })
  }

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
          if (r.mode === 'rounds' && run.n < r.nombre) {
            sonner(3)
            setRun(phase('repos', run.n))
          } else terminer()
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
    film.pause(run.pause == null)
    if (run.pause != null) setRun({ ...run, fin: Date.now() + run.pause, pause: null })
    else setRun({ ...run, pause: run.fin - Date.now() })
  }

  const regler = (k, d, min, max) => setR((x) => ({ ...x, [k]: Math.min(max, Math.max(min, x[k] + d)) }))
  const repos = run?.phase === 'repos'
  const resume = r.mode === 'rounds' ? `${r.nombre} × ${mmss(r.round)} · repos ${mmss(r.repos)}` : mmss(r.round)

  const chrono = (
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
  )
  const cloche = (
    <button
      type="button"
      className={`sc-timer__dessin sc-timer__dessin--cloche${sonne ? ' sc-timer__dessin--sonne' : ''}`}
      style={sonne ? { '--coups': sonne.n } : undefined}
      disabled={!!fin || retard > 0}
      onClick={run ? terminer : debuter}
    >
      <span key={sonne?.id ?? 0} dangerouslySetInnerHTML={{ __html: CLOCHE }} />
      <span className="sc-timer__mot">{run ? 'Arrêter' : 'Démarrer'}</span>
    </button>
  )

  if (etendu && plein) {
    const appel = termine && resultat === null ? ' sc-te__poing--appel' : ''
    const poing = (i) => (
      <button
        type="button"
        className={`sc-te__poing${i ? ' sc-te__poing--droite' : ''}${appel}`}
        aria-pressed={resultat === i}
        aria-label={`Vainqueur : ${noms[i]?.name ?? (i ? 'à droite' : 'à gauche')}`}
        onClick={() => setResultat(resultat === i ? null : i)}
        dangerouslySetInnerHTML={{ __html: POING }}
      />
    )
    const champ = (i) =>
      r.noms ? (
        <ChampNom
          nom={noms[i]}
          autre={noms[1 - i]}
          membres={membres}
          libelle={i ? 'Combattant de droite' : 'Combattant de gauche'}
          onChoisir={(m) => setNoms(i ? [noms[0], m] : [m, noms[1]])}
        />
      ) : (
        <span />
      )
    return createPortal(
      <div className="sc-timer sc-te">
        <button type="button" className="sc-timer__fermer" aria-label="Quitter le plein écran" onClick={() => setPlein(false)}>
          ✕
        </button>
        <p className="sc-te__tourner">Tournez le téléphone en paysage.</p>
        <div className="sc-te__gauche">
          {/* Entre les deux noms : un poing levé de chaque côté, « = » pour le match nul. */}
          <div className="sc-te__noms">
            {champ(0)}
            {r.vainqueur ? (
              <div className="sc-te__resultat">
                {poing(0)}
                <button
                  type="button"
                  className={`sc-te__nul${appel}`}
                  aria-pressed={resultat === 'nul'}
                  aria-label="Match nul"
                  onClick={() => setResultat(resultat === 'nul' ? null : 'nul')}
                >
                  =
                </button>
                {poing(1)}
              </div>
            ) : (
              <span className="sc-te__contre">{r.noms ? 'contre' : ''}</span>
            )}
            {champ(1)}
          </div>
          {fin ? (
            // La cloche de fin a sonné : on revoit le combat, puis Archiver, Partager ou Jeter.
            <div className="sc-te__milieu">
              <div className="sc-te__mini">
                <video key="revoir" src={fin.url} controls playsInline />
              </div>
              <p className="sc-te__question">
                {r.vainqueur && resultat === null ? 'Qui a gagné ? Touchez un poing, ou « = ».' : 'Que faire de ce combat ?'}
              </p>
            </div>
          ) : (
            <div className={`sc-te__milieu${r.film ? '' : ' sc-te__milieu--sans-film'}`}>
              {r.film && (
                <div className={`sc-te__mini${run ? ' sc-te__mini--filme' : ''}`}>
                  <video key="direct" ref={film.brancher} muted playsInline autoPlay />
                  <b>{film.etat === 'refus' ? 'Caméra indisponible' : run ? 'Ça filme' : film.etat === 'pret' ? 'Prêt à filmer' : 'Caméra…'}</b>
                  {retard > 0 ? (
                    <strong className="sc-te__compte">{retard}</strong>
                  ) : (
                    !run && (
                      // Se filmer soi-même : on pose le téléphone, la cloche sonne 5 s après.
                      <button
                        type="button"
                        className="sc-te__retardateur"
                        aria-label="Retardateur : la cloche sonne dans 5 secondes"
                        onClick={() => {
                          tin()
                          setRetard(RETARD_S)
                        }}
                      >
                        <span dangerouslySetInnerHTML={{ __html: CAMERA }} />5 s
                      </button>
                    )
                  )}
                </div>
              )}
              <div>
                <Afficheur className={`sc-timer__temps${run && !repos && reste <= 10 ? ' sc-timer__temps--fin' : ''}`} texte={mmss(reste)} />
                <div className="sc-te__round">
                  {repos ? 'Repos' : ''}
                  {r.mode === 'rounds' && run ? `${repos ? ' · ' : ''}Round ${run.n} sur ${r.nombre}` : ''}
                </div>
              </div>
            </div>
          )}
        </div>
        {fin ? (
          <div className="sc-te__choix">
            <button type="button" className="sc-te__choix-principal" onClick={archiver}>
              <b>Archiver</b>
              <small>Il va dans Combats</small>
            </button>
            <button type="button" onClick={partager}>
              <b>Partager</b>
              <small>WhatsApp, messages…</small>
            </button>
            <button type="button" className="sc-te__jeter" onClick={jeter}>
              Jeter
            </button>
          </div>
        ) : (
          <div className="sc-te__dessins">
            {cloche}
            {chrono}
          </div>
        )}
        {message && (
          <div className="sc-te__message" role="status">
            {message.texte}
            {message.annuler && (
              <button type="button" onClick={message.annuler}>
                Annuler
              </button>
            )}
          </div>
        )}
      </div>,
      document.body,
    )
  }

  const ecran = (
    <div className={`sc-timer${plein ? ' sc-timer--plein' : ''}${run ? ' sc-timer--marche' : ''}`}>
      {plein && (
        <button type="button" className="sc-timer__fermer" aria-label="Quitter le plein écran" onClick={() => setPlein(false)}>
          ✕
        </button>
      )}
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

      {/* Sorti du plein écran : toucher le temps y revient. */}
      <div className="sc-timer__horloge" onClick={() => setPlein(true)}>
        <div className={`sc-timer__phase${repos ? ' sc-timer__phase--repos' : run ? '' : ' sc-timer__phase--pret'}`}>
          {/* Pas de « Combat » pendant le round : on le sait (Seb, 21/11). */}
          {run ? (repos ? 'Repos' : '') : 'Prêt'}
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
        {chrono}
        {cloche}
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
  return plein ? createPortal(ecran, document.body) : ecran
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
