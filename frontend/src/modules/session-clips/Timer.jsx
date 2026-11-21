import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Deroulant } from './Labo.jsx'
import { CAMERA, CHRONO, CLOCHE, POING } from './timerDessins.js'
import { ecrire, estEtendu, lire } from './timerReglages.js'
import { useFilm } from './timerFilm.js'
import { DANS_L_APPLI, Natif } from './natif.js'
import { demarrerTeleversement, finaliserTeleversement, sansCopieLocale, useProgressionTeleversement } from '../../utils/videoUploads.js'
import * as api from './api.js'
import clocheDebut from './sons/cloche-debut-de-round.mp3'
import clocheFin from './sons/cloche-fin-de-round.mp3'
import clacClac from './sons/clac-clac-10-secondes.mp3'
import bips from './sons/bips-fin-du-repos.mp3'
// L'annonce du vainqueur, voix « George » (Seb, 21/11) ; le nom vient du serveur.
import annonceVainqueur from './sons/annonce-vainqueur.mp3'
import annonceNul from './sons/annonce-nul.mp3'
import annonceGauche from './sons/annonce-gauche.mp3'
import annonceDroite from './sons/annonce-droite.mp3'
import foule from './sons/foule.mp3'
// Les musiques à incruster dans la vidéo archivée, composées pour Fights (Seb, 21/11).
import musiqueMontage from './sons/musique-montage.mp3'
import musiqueEntree from './sons/musique-entree.mp3'
import musiqueRock from './sons/musique-rock.mp3'

// Fights › Timer (coachs ; Seb, 13/11, maquette https://claude.ai/artifact/2U8ASb7oeDcgbib9vwkyza) :
// un round seul, ou des rounds avec repos. Cloche d'un coup au début, clac clac
// 10 s avant la fin (case à cocher), trois coups à la fin, bips à la fin du repos.
// Le décompte suit l'horloge (pas les tics du navigateur, ralentis écran éteint).

const SONS = { debut: clocheDebut, fin: clocheFin, clac: clacClac, bips, vainqueur: annonceVainqueur, nul: annonceNul, gauche: annonceGauche, droite: annonceDroite, foule }
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

// Timer étendu : le choix du combattant, comme l'écran de sélection d'un jeu de
// combat (Seb, 21/11) : pas de clavier, une barre de lettres (★ : les habitués
// de ce jour de la semaine), puis des cartes qu'on fait défiler.
const TEINTES = [0, 28, 200, 265, 150, 330, 45, 180]
const teinte = (n) => TEINTES[[...n].reduce((a, c) => a + c.charCodeAt(0), 0) % TEINTES.length]
const initiale = (n) => plat(n)[0]?.toUpperCase() ?? '?'
const INCONNU = { id: null, name: 'Inconnu' }
const ALPHABET = [...'ABCDEFGHIJKLMNOPQRSTUVWXYZ']
const MUSIQUES = [
  ['montage', 'Entraînement', '🎺', 45, musiqueMontage],
  ['entree', 'Entrée du combattant', '🥁', 265, musiqueEntree],
  ['rock', 'Rock de victoire', '🎸', 0, musiqueRock],
  [null, 'Sans musique', '🔇', 220],
]

// Où en est un combat archivé (Seb, 21/11) : l'envoi, puis le travail du
// serveur, puis où le retrouver. Relu toutes les 10 s tant qu'il n'est pas prêt.
function Envoi({ envoi, me, onFini }) {
  const progression = useProgressionTeleversement(envoi.uploadId)
  const [relu, setClip] = useState(null)
  const clip = relu ?? envoi.clip
  const envoye = !progression || progression.complet
  const pret = clip && envoye && !clip.preparing && clip.video?.statut !== 'en_cours'
  useEffect(() => {
    if (!clip || pret) return undefined
    const id = setTimeout(() => api.obtenirClip(clip.id).then(setClip, () => {}), 10000)
    return () => clearTimeout(id)
  }, [clip, pret])
  useEffect(() => {
    if (!pret) return undefined
    const id = setTimeout(onFini, 15000)
    return () => clearTimeout(id)
  }, [pret]) // eslint-disable-line react-hooks/exhaustive-deps
  const moi = clip?.participants.some((p) => p.person_id === me?.person_id)
  const pourcent = progression?.octetsTotal ? Math.round((100 * progression.octetsEnvoyes) / progression.octetsTotal) : 100
  const texte = !envoye
    ? `Envoi ${pourcent} %`
    : !pret
      ? 'En préparation…'
      : clip.to_check
        ? 'Prêt : à vérifier dans Tournage'
        : moi
          ? 'Prêt dans Combats'
          : 'Prêt dans Tournage, séance du jour'
  return (
    <div className="sc-te__envoi" role="status">
      <span>
        <b>{envoi.nom}</b> · {texte}
      </span>
      <i className={pret ? 'sc-te__envoi-barre sc-te__envoi-barre--pret' : envoye ? 'sc-te__envoi-barre sc-te__envoi-barre--prep' : 'sc-te__envoi-barre'}>
        <i style={{ width: `${envoye ? 100 : pourcent}%` }} />
      </i>
    </div>
  )
}

// « Archiver » avec « Une musique » cochée (Seb, 21/11) : un seul geste,
// toucher une musique archive la vidéo avec elle ; ▶ l'écoute avant.
function ChoixMusique({ onChoisir, onFermer }) {
  const [flash, setFlash] = useState(undefined)
  const [ecoute, setEcoute] = useState(null)
  const lecteur = useRef(null)
  useEffect(() => () => lecteur.current?.pause(), [])
  function ecouter(ev, id, son) {
    ev.stopPropagation()
    lecteur.current?.pause()
    if (ecoute === id) return setEcoute(null)
    lecteur.current = new Audio(son)
    lecteur.current.onended = () => setEcoute(null)
    lecteur.current.play().catch(() => {})
    setEcoute(id)
  }
  function choisir(id) {
    lecteur.current?.pause()
    setFlash(id)
    setTimeout(() => onChoisir(id), 350)
  }
  return (
    <div className="sc-te__select" role="dialog" aria-label="Quelle musique ?">
      <div className="sc-te__select-tete">
        <b>Quelle musique ?</b>
        <button type="button" className="sc-te__select-fermer" aria-label="Fermer" onClick={onFermer}>
          ✕
        </button>
      </div>
      <div className="sc-te__musiques">
        {MUSIQUES.map(([id, nom, icone, t, son]) => (
          <div
            key={nom}
            role="button"
            tabIndex={0}
            className={`sc-te__musique${id ? '' : ' sc-te__musique--sans'}${flash === id ? ' sc-te__carte--flash' : ''}`}
            style={{ '--t': t }}
            onClick={() => choisir(id)}
            onKeyDown={(ev) => ev.key === 'Enter' && choisir(id)}
          >
            <span className="sc-te__musique-icone" aria-hidden="true">{icone}</span>
            {nom}
            {son && (
              <button type="button" className="sc-te__ecoute" aria-label={`Écouter ${nom}`} onClick={(ev) => ecouter(ev, id, son)}>
                {ecoute === id ? '❚❚' : '▶'}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function ChoixCombattant({ titre, membres, autre, actuel, onChoisir, onFermer }) {
  const habitues = membres.some((m) => m.regular)
  const [lettre, setLettre] = useState(habitues ? '★' : null)
  const [flash, setFlash] = useState(null)
  // Tout l'alphabet sur deux lignes, sans défiler (Seb, 21/11) ; une lettre sans personne est éteinte.
  const presentes = new Set(membres.map((m) => initiale(m.name)))
  const liste = membres.filter(
    (m) => m.id !== autre?.id && (lettre === '★' ? m.regular : lettre === null || initiale(m.name) === lettre),
  )
  function choisir(m) {
    setFlash(m)
    setTimeout(() => onChoisir(m), 350)
  }
  const carte = (m) => {
    const [prenom, ...reste] = m.name.split(' ')
    return (
      <button
        key={m.id ?? 'inconnu'}
        type="button"
        className={`sc-te__carte${flash === m ? ' sc-te__carte--flash' : ''}${actuel?.id === m.id && m.id ? ' sc-te__carte--prise' : ''}${m.id ? '' : ' sc-te__carte--inconnu'}`}
        style={{ '--t': teinte(m.name) }}
        onClick={() => choisir(m)}
      >
        <span className="sc-te__avatar">{m.id ? m.name.split(' ').map((x) => x[0]).join('').toUpperCase() : '?'}</span>
        <b>{prenom}</b>
        <small>{m.id ? reste.join(' ') : 'pas du club'}</small>
      </button>
    )
  }
  return (
    <div className="sc-te__select" role="dialog" aria-label={titre}>
      <div className="sc-te__select-tete">
        <b>{titre}</b>
        <button type="button" className="sc-te__select-fermer" aria-label="Fermer" onClick={onFermer}>
          ✕
        </button>
      </div>
      <div className="sc-te__lettres">
        {(habitues ? ['★', ...ALPHABET] : ALPHABET).map((l) => (
          <button
            key={l}
            type="button"
            aria-pressed={lettre === l}
            disabled={l !== '★' && !presentes.has(l)}
            onClick={() => setLettre(lettre === l ? null : l)}
          >
            {l}
          </button>
        ))}
      </div>
      <div className="sc-te__cartes">
        {liste.map(carte)}
        {carte(INCONNU)}
      </div>
    </div>
  )
}

export default function Timer({ ecoleId, rafraichir, me }) {
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
  const [choix, setChoix] = useState(null) // la place (0 ou 1) dont on choisit le combattant
  const [choixMusique, setChoixMusique] = useState(false)
  const phases = useRef([]) // rounds et repos dans la vidéo, pour le chrono incrusté
  const [envois, setEnvois] = useState([]) // { uploadId, nom, clip } : les combats archivés qui partent
  const annonces = useRef({}) // id du membre -> adresse du son de son nom (George)
  const joue = useRef([])
  const annonceTour = useRef(0)
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
    if (r.noms) api.nomsTimer().then(setMembres, () => {})
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

  // Le nom du vainqueur dit par George : préparé dès que le combattant est choisi.
  function nommer(i, m) {
    const suite = i ? [noms[0], m] : [m, noms[1]]
    setNoms(suite)
    setChoix(null)
    if (r.annonce && m.id && !annonces.current[m.id]) {
      annonces.current[m.id] = api.annonceNom(m.id).catch(() => null)
    }
  }

  // « And the winner, by unanimous decision, is… », le nom, la foule ; ou « It's a draw! ».
  // Un nouvel appui coupe l'annonce en cours.
  async function annoncer(quoi) {
    const tour = ++annonceTour.current
    joue.current.forEach((a) => a.pause())
    joue.current = []
    const encore = () => tour === annonceTour.current
    const lire = (src, avant) =>
      new Promise((ok) => {
        if (!encore()) return ok()
        const a = new Audio(src)
        joue.current.push(a)
        if (avant) a.onloadedmetadata = () => setTimeout(() => encore() && lire(SONS.foule), (a.duration || 1.5) * 550)
        a.onended = a.onerror = ok
        a.play().catch(ok)
      })
    if (quoi === 'nul') return lire(SONS.nul)
    const nom = noms[quoi]?.id ? await annonces.current[noms[quoi].id] : null
    await lire(SONS.vainqueur)
    await new Promise((ok) => setTimeout(ok, 700))
    // Sans nom (ou voix indisponible) : « the fighter in the left corner! ».
    await lire(nom ?? (quoi ? SONS.droite : SONS.gauche), true)
  }

  function declarer(quoi) {
    const suite = resultat === quoi ? null : quoi
    setResultat(suite)
    if (suite !== null && r.annonce) annoncer(suite)
  }

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
    phases.current = []
    setRun(phase('round', 1))
  }

  // Fin du combat : dernier round fini, ou cloche touchée.
  function terminer() {
    setRun(null)
    sonner(3)
    if (!etendu) return
    setTermine(true)
    const vues = phases.current
    if (r.film) film.arreter().then((fichier) => fichier && setFin({ fichier, url: URL.createObjectURL(fichier), phases: vues }))
  }

  function suivant() {
    setFin(null)
    setNoms([null, null])
    setResultat(null)
    setTermine(false)
  }

  const titre = () => (noms.some(Boolean) ? noms.map((n) => n?.name ?? '?').join(' vs ') : 'Combat')

  // « Archiver » : le combat part dans Combats, l'envoi continue derrière.
  // L'incrustation (Seb, 21/11) se fait au serveur, selon Paramètres du Timer.
  async function archiver(musique = null) {
    setChoixMusique(false)
    const vainqueur = r.vainqueur && r.incrVainqueur
    const overlay = {
      names: r.noms && r.incrNoms,
      winner: vainqueur,
      chrono: r.incrChrono,
      music: r.incrMusique ? musique : null,
      announce: vainqueur && r.annonce,
      rounds: r.mode === 'rounds' ? r.nombre : 1,
      phases: fin.phases ?? [],
    }
    const corps = {
      people: noms.map((n) => n?.id ?? null),
      winner: typeof resultat === 'number' ? resultat : null,
      draw: resultat === 'nul',
      overlay,
    }
    const { fichier, url } = fin
    const nom = titre()
    suivant()
    URL.revokeObjectURL(url)
    try {
      const uploadId = await demarrerTeleversement(ecoleId, fichier)
      setEnvois((l) => [...l, { uploadId, nom, clip: null }])
      let clip = null
      const video = await finaliserTeleversement(uploadId, async (id) => {
        clip = await api.filmerCombat({ upload_id: id, ...corps })
        return clip.video
      })
      setEnvois((l) => l.map((e) => (e.uploadId === uploadId ? { ...e, clip } : e)))
      // Incrusté au serveur : passer à sa version dès qu'elle est prête.
      if (Object.values(overlay).some((v) => v === true) || overlay.music) sansCopieLocale(video.id)
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
    if (etendu && r.film) phases.current.push({ t: film.temps(), n: nom === 'round' ? n : 0, total })
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
        onClick={() => declarer(i)}
        dangerouslySetInnerHTML={{ __html: POING }}
      />
    )
    const champ = (i) =>
      r.noms ? (
        <button
          type="button"
          className={`sc-te__champ${noms[i] ? '' : ' sc-te__champ--vide'}`}
          aria-label={i ? 'Combattant de droite' : 'Combattant de gauche'}
          onClick={() => setChoix(i)}
        >
          {noms[i]?.name ?? '…'}
        </button>
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
                  onClick={() => declarer('nul')}
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
            <button type="button" className="sc-te__choix-principal" onClick={() => (r.incrMusique ? setChoixMusique(true) : archiver())}>
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
        {choix !== null && (
          <ChoixCombattant
            titre={choix ? 'Combattant de droite' : 'Combattant de gauche'}
            membres={membres}
            autre={noms[1 - choix]}
            actuel={noms[choix]}
            onChoisir={(m) => nommer(choix, m)}
            onFermer={() => setChoix(null)}
          />
        )}
        {choixMusique && fin && <ChoixMusique onChoisir={archiver} onFermer={() => setChoixMusique(false)} />}
        {envois.length > 0 && (
          <div className="sc-te__envois">
            {envois.map((e) => (
              <Envoi key={e.uploadId} envoi={e} me={me} onFini={() => setEnvois((l) => l.filter((x) => x !== e))} />
            ))}
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
