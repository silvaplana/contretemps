import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import { demarrerTeleversement, finaliserTeleversement, useProgressionVideo, useTeleversementsTermines } from '../../utils/videoUploads.js'
import * as api from './api.js'

// Fights › Labo (spec/modules/video-combats.md §6.5 bis, maquette
// spec/maquettes/fights-labo.html) : un coach importe une vidéo déjà filmée
// et voit ce que la découpe y repère, sans filmer et sans rien ranger dans
// Mes combats. Le graphe : le temps en abscisse, une flèche verticale par
// signe repéré, avec l'image de la vidéo à ce moment, son nom et son heure.

const ANNULER_MS = 10000

// Mêmes noms que backend/src/session_clips/fights.py (SIGNS).
const SIGNES = [
  { id: 'fist_up', g: 'deb', l: 'Poing levé', court: 'Poing levé', d: 'Chacun lève le poing au-dessus de la tête, bras plié' },
  { id: 'fists_touch', g: 'deb', l: 'Poings touchés en l’air', court: 'Poings en l’air', d: 'Les deux se touchent les poings, bras vers le haut' },
  { id: 'handshake', g: 'fin', l: 'Poignée de main', court: 'Poignée de main', d: 'Mains serrées, bras vers le bas, sans bouger' },
  { id: 'x', g: 'fin', l: 'X au-dessus de la tête', court: 'X', d: 'Avant-bras croisés en l’air' },
  { id: 'time', g: 'fin', l: '« Time ! » crié', court: '« Time ! »', d: 'Son : l’entraîneur annonce la fin' },
]
const signe = (id) => SIGNES.find((s) => s.id === id) ?? { id, g: 'fin', l: id, court: id, d: '' }

const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`

function titreFichier(fichier) {
  const d = new Date(fichier.lastModified || Date.now())
  const p = (n) => String(n).padStart(2, '0')
  return `Combat du ${p(d.getDate())}/${p(d.getMonth() + 1)} à ${p(d.getHours())}:${p(d.getMinutes())}`
}

// Supprimer un essai : il disparaît tout de suite, part vraiment au bout de 10 s.
export function useSuppressionEssai(montrer, rafraichir) {
  const [caches, setCaches] = useState(new Set())
  const supprimer = useCallback(
    (id) => {
      setCaches((c) => new Set([...c, id]))
      const retard = setTimeout(() => {
        api.supprimerEssai(id).then(rafraichir, (e) => montrer(e.message))
      }, ANNULER_MS)
      montrer('Essai supprimé', () => {
        clearTimeout(retard)
        setCaches((c) => new Set([...c].filter((x) => x !== id)))
      })
    },
    [montrer, rafraichir],
  )
  return [caches, supprimer]
}

export function Labo({ ecoleId, version, rafraichir, montrer, essaisCaches, onOpen, onSupprimer }) {
  const [liste, setListe] = useState(null)
  const [renomme, setRenomme] = useState(null) // l'essai au crayon
  useEffect(() => {
    api.essais().then(setListe, (e) => montrer(e.message))
  }, [version, montrer])
  useTeleversementsTermines(rafraichir)
  // Tant qu'un essai est lu, la liste se met à jour seule.
  const attente = liste?.some((e) => e.status === 'processing' || e.status === 'uploading')
  useEffect(() => {
    if (!attente) return undefined
    const minuteur = setInterval(rafraichir, 5000)
    return () => clearInterval(minuteur)
  }, [attente, rafraichir])

  async function importer(fichier) {
    if (!fichier) return
    try {
      const uploadId = await demarrerTeleversement(ecoleId, fichier)
      await finaliserTeleversement(uploadId, async (id) => (await api.creerEssai({ upload_id: id, title: titreFichier(fichier) })).video)
      rafraichir()
    } catch (e) {
      montrer(e.message)
    }
  }

  function choisi(ev) {
    importer(ev.target.files?.[0])
    ev.target.value = ''
  }

  const visibles = liste?.filter((e) => !essaisCaches.has(e.id))
  return (
    <>
      {/* Comme les vidéos d'une chorégraphie (AjouterVideo.jsx, Seb 12/11) : la
          caméra filme tout de suite (essais entre amis), le dossier prend une
          vidéo de la Galerie. */}
      <label className="fab--secondary" aria-label="Filmer une vidéo">
        <Icon name="camera" size={20} />
        <input type="file" accept="video/*" capture="environment" hidden onChange={choisi} />
      </label>
      <label className="fab" aria-label="Importer une vidéo">
        <Icon name="folder" size={24} />
        <input type="file" accept="video/*" hidden onChange={choisi} />
      </label>
      <p className="sc-meta">Étudiez la détection des signes dans une vidéo : filmez-la avec la caméra ou prenez-la dans la Galerie avec le dossier. Rien ne va dans Mes combats.</p>
      {visibles?.length === 0 && <p className="sc-vide">Aucun essai pour l’instant.</p>}
      {visibles?.map((e) => (
        <div key={e.id} className="sc-essai">
          <button
            type="button"
            className="sc-essai__ouvrir"
            aria-disabled={e.status !== 'ready'}
            onClick={() => e.status === 'ready' && onOpen(e.id)}
          >
            <span className="sc-vignette sc-vignette--petite">
              {e.video?.poster ? <img src={e.video.poster} alt="" /> : <Icon name="video" size={20} />}
              {e.video?.dureeSecondes > 0 && <span className="sc-vignette__duree">{mmss(e.video.dureeSecondes)}</span>}
            </span>
            <span>
              <strong>{e.title || 'Essai'}</strong>
              <span className="sc-meta">
                <EtatEssai e={e} />
              </span>
            </span>
          </button>
          <button type="button" className="icon-btn" aria-label="Renommer l’essai" onClick={() => setRenomme(e)}>
            <Icon name="edit" size={20} />
          </button>
          <button type="button" className="icon-btn" aria-label="Supprimer l’essai" onClick={() => onSupprimer(e.id)}>
            <Icon name="trash" size={20} />
          </button>
        </div>
      ))}
      {renomme && (
        <RenommerEssai
          essai={renomme}
          montrer={montrer}
          onClose={() => setRenomme(null)}
          onRenomme={() => {
            setRenomme(null)
            rafraichir()
          }}
        />
      )}
    </>
  )
}

function EtatEssai({ e }) {
  const progression = useProgressionVideo(e.status === 'uploading' ? e.video?.id : null)
  if (e.status === 'uploading') {
    const pct = progression?.octetsTotal ? Math.round((progression.octetsEnvoyes / progression.octetsTotal) * 100) : null
    return <span className="sc-chip sc-chip--info">{pct === null ? 'Envoi…' : `Envoi ${pct} %`}</span>
  }
  if (e.status === 'processing') return <span className="sc-chip sc-chip--info">Lecture des signes…</span>
  if (e.status === 'failed') return <span className="sc-chip sc-chip--warn">Vidéo illisible</span>
  return <span>{api.jour(e.created_at.slice(0, 10))}</span>
}

export function EssaiLabo({ essaiId, version, rafraichir, montrer, onBack, onSupprimer }) {
  const [e, setE] = useState(null)
  const [reglages, setReglages] = useState(null) // ceux de l'écran
  const [club, setClub] = useState(null) // ceux enregistrés
  const [enCours, setEnCours] = useState(false)
  const [duree, setDuree] = useState(null)
  const [regarde, setRegarde] = useState(null) // le combat ouvert
  const [renomme, setRenomme] = useState(false) // le crayon
  const lecteur = useRef(null)
  const cadre = useCadre(lecteur, e?.fights)
  useEffect(() => {
    api.essaiLabo(essaiId).then(setE, (err) => montrer(err.message))
  }, [essaiId, version, montrer])
  useEffect(() => {
    api.reglagesDuClub().then((r) => {
      setClub(r)
      setReglages(r)
    }, (err) => montrer(err.message))
  }, [montrer])

  function aller(t) {
    const v = lecteur.current
    if (!v) return
    v.currentTime = t
    v.scrollIntoView?.({ behavior: 'smooth', block: 'center' }) // la vidéo est en haut de l'écran
    v.play?.().catch(() => {})
  }

  const coches = reglages?.signs ?? []
  function cocher(id) {
    setReglages((r) => ({ ...r, signs: r.signs.includes(id) ? r.signs.filter((x) => x !== id) : [...r.signs, id] }))
  }

  async function relancer() {
    setEnCours(true)
    try {
      const r = await api.reglerClub(reglages)
      setClub(r)
      setReglages(r)
      rafraichir()
      montrer('Découpe relancée')
    } catch (err) {
      montrer(err.message)
    } finally {
      setEnCours(false)
    }
  }

  const fin = Math.max(duree || e?.video?.dureeSecondes || 0, ...(e?.signs ?? []).map((s) => s.end + 2), 1)
  const cle = (r) => r && JSON.stringify({ ...r, signs: [...r.signs].sort() })
  const change = reglages && club && cle(reglages) !== cle(club)
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour au Labo">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">{e?.title ?? ''}</strong>
        {e && (
          <button type="button" className="icon-btn" onClick={() => setRenomme(true)} aria-label="Renommer l’essai">
            <Icon name="edit" size={20} />
          </button>
        )}
      </div>
      {e && reglages && (
        <div className="sc__corps">
          {e.video?.url && (
            // Le cadre du combat en cours (Moyen ou Serré) est montré sur la
            // vidéo d'origine, comme le clip sera coupé.
            <div className="sc-cadreur">
              <video
                ref={lecteur}
                className="sc-apercu"
                style={cadreStyle(cadre)}
                src={e.video.url}
                // Recadrée, la barre de lecture serait coupée : un appui lit ou arrête.
                controls={!cadre}
                onClick={(ev) => cadre && (ev.currentTarget.paused ? ev.currentTarget.play() : ev.currentTarget.pause())}
                playsInline
                onLoadedMetadata={(ev) => setDuree(ev.currentTarget.duration)}
              />
            </div>
          )}
          <h3 className="sc-section">Signes repérés</h3>
          <div className="sc-cadre">
            <Graphe signes={e.signs} combats={e.fights} coches={coches} fin={fin} aller={aller} />
            {e.signs.length === 0 && <p className="sc-vide">Aucun signe repéré dans cette vidéo.</p>}
            {e.signs.map((s, i) => {
              const sg = signe(s.kind)
              const on = coches.includes(s.kind)
              return (
                <button key={i} type="button" className="sc-geste" onClick={() => aller(s.start)}>
                  <span className="sc-geste__t">{mmss(s.start)}</span>
                  <span className={`sc-geste__pt sc-geste__pt--${on ? sg.g : 'off'}`} />
                  <span>
                    {sg.l}
                    <small>{on ? (sg.g === 'deb' ? 'Début de combat' : 'Fin de combat') : 'Signe décoché : ignoré'}</small>
                  </span>
                </button>
              )
            })}
          </div>
          <h3 className="sc-section">Combats coupés</h3>
          {e.fights.length === 0 && <p className="sc-vide">Aucun combat : aucun signe de début coché n’a été vu.</p>}
          {e.fights.map((c, i) => (
            <button key={i} type="button" className="sc-clip" onClick={() => setRegarde({ ...c, numero: i + 1 })}>
              <span className="sc-vignette">
                {vignette(e.signs, c) ? <img src={vignette(e.signs, c)} alt="" /> : <Icon name="video" size={22} />}
                <span className="sc-vignette__duree">{mmss(c.end - c.start)}</span>
              </span>
              <span>
                <strong>Combat {i + 1}</strong>
                <span className="sc-meta">
                  {mmss(c.start)} → {mmss(c.end)}
                  {c.check_reason && <span className="sc-chip sc-chip--warn">Fin non repérée</span>}
                </span>
              </span>
            </button>
          ))}
          {/* Fermé par défaut : sinon ça prend trop de place (Seb, 12/11). */}
          <details className="sc-cadre sc-deroulant">
            <summary>Signes et sons du club</summary>
            {['deb', 'fin'].map((g) => (
              <div key={g}>
                <p className="sc-meta">{g === 'deb' ? 'Début de combat' : 'Fin de combat'}</p>
                {SIGNES.filter((s) => s.g === g).map((s) => (
                  <label key={s.id} className="sc-coche">
                    <input type="checkbox" checked={coches.includes(s.id)} onChange={() => cocher(s.id)} />
                    <span>
                      {s.l}
                      <small>{s.d}</small>
                    </span>
                  </label>
                ))}
              </div>
            ))}
          </details>
          {/* Fermé par défaut : sinon ça prend trop de place (Seb, 12/11). */}
          <details className="sc-cadre sc-deroulant">
            <summary>Clips du club</summary>
            <p className="sc-meta">Cadrage</p>
            <SegmentedTabs
              className="sc-onglets"
              value={reglages.framing}
              onChange={(framing) => setReglages((r) => ({ ...r, framing }))}
              options={CADRAGES.map(([value, label]) => ({ value, label }))}
            />
            <Secondes
              libelle="Démarrer après le signe de début"
              valeur={reglages.start_skip}
              onChange={(start_skip) => setReglages((r) => ({ ...r, start_skip }))}
            />
            <Secondes
              libelle="Couper avant la fin"
              valeur={reglages.end_skip}
              onChange={(end_skip) => setReglages((r) => ({ ...r, end_skip }))}
            />
          </details>
          <button type="button" className="btn btn--primary sc-bouton" disabled={!change || enCours} onClick={relancer}>
            Relancer la découpe
          </button>
          <button type="button" className="btn btn--secondary sc-bouton" onClick={() => onSupprimer(e.id)}>
            Supprimer l’essai
          </button>
        </div>
      )}
      {regarde && (
        <Modal title={`Combat ${regarde.numero}`} onClose={() => setRegarde(null)}>
          <LecteurCombat url={e.video.url} combat={regarde} />
        </Modal>
      )}
      {renomme && (
        <RenommerEssai
          essai={e}
          montrer={montrer}
          onClose={() => setRenomme(false)}
          onRenomme={(r) => {
            setRenomme(false)
            setE((x) => ({ ...x, title: r.title }))
            rafraichir()
          }}
        />
      )}
    </div>
  )
}

// Le crayon : renommer un essai (Seb, 12/11).
function RenommerEssai({ essai, montrer, onClose, onRenomme }) {
  const [nom, setNom] = useState(essai.title)
  async function enregistrer() {
    try {
      onRenomme(await api.renommerEssai(essai.id, nom))
    } catch (err) {
      montrer(err.message)
    }
  }
  return (
    <Modal
      title="Renommer l’essai"
      onClose={onClose}
      footer={
        <div className="video-upload-form__actions">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="button" className="btn btn--primary" disabled={!nom.trim()} onClick={enregistrer}>
            Enregistrer
          </button>
        </div>
      }
    >
      <input className="sc-champ" value={nom} autoFocus maxLength={150} onChange={(ev) => setNom(ev.target.value)} />
    </Modal>
  )
}

// La vignette d'un combat : l'image de son signe de début.
function vignette(signes, combat) {
  const debuts = signes.filter((s) => signe(s.kind).g === 'deb' && s.start <= combat.start + 0.05 && s.thumb)
  return debuts.length ? debuts[debuts.length - 1].thumb : null
}

// Un combat regardé seul : la vidéo de l'essai, du début à la fin du combat.
function LecteurCombat({ url, combat }) {
  const lecteur = useRef(null)
  const combats = useMemo(() => [combat], [combat])
  const cadre = useCadre(lecteur, combats)
  return (
    <div className="sc-cadreur">
      <video
        ref={lecteur}
        className="sc-apercu"
        style={cadreStyle(cadre)}
        src={`${url}#t=${combat.start},${combat.end}`}
        controls={!cadre}
        onClick={(ev) => cadre && (ev.currentTarget.paused ? ev.currentTarget.play() : ev.currentTarget.pause())}
        autoPlay
        playsInline
        onTimeUpdate={(ev) => {
          if (ev.currentTarget.currentTime >= combat.end) ev.currentTarget.pause()
        }}
      />
    </div>
  )
}

// Le cadre [t, x, y, l, h] (de 0 à 1) appliqué à la vidéo d'origine.
function cadreStyle(cadre) {
  return cadre ? { transform: `scale(${1 / cadre[3]}) translate(${-cadre[1] * 100}%, ${-cadre[2] * 100}%)` } : undefined
}

const CADRAGES = [
  ['wide', 'Plan large'],
  ['medium', 'Moyen'],
  ['tight', 'Serré'],
]

// Secondes retirées, de 0 à 10 par demi-seconde : − et + plutôt qu'un champ.
function Secondes({ libelle, valeur, onChange }) {
  const changer = (d) => onChange(Math.min(10, Math.max(0, valeur + d)))
  return (
    <div className="sc-secondes">
      <span>{libelle}</span>
      <button type="button" className="icon-btn" aria-label="Moins" disabled={valeur <= 0} onClick={() => changer(-0.5)}>
        <Icon name="minus" size={22} />
      </button>
      <strong>{String(valeur).replace('.', ',')} s</strong>
      <button type="button" className="icon-btn" aria-label="Plus" disabled={valeur >= 10} onClick={() => changer(0.5)}>
        <Icon name="plus" size={22} />
      </button>
    </div>
  )
}

// Pendant la lecture : le cadre du combat en cours ([t, x, y, l, h], de 0
// à 1), ou null en plan large.
function useCadre(lecteur, combats) {
  const [cadre, setCadre] = useState(null)
  useEffect(() => {
    let id
    function suivre() {
      const v = lecteur.current
      if (v) {
        const t = v.currentTime
        const c = combats?.find((f) => f.frame && t >= f.start && t <= f.end)
        const suivant = c ? c.frame[Math.min(Math.round((t - c.start) / 0.2), c.frame.length - 1)] : null
        setCadre((avant) => (avant === suivant ? avant : suivant))
      }
      id = requestAnimationFrame(suivre)
    }
    id = requestAnimationFrame(suivre)
    return () => cancelAnimationFrame(id)
  }, [lecteur, combats])
  return cadre
}

// Le graphe : vert = début de combat, rouge = fin, gris pointillé = signe
// décoché ; la bande sur l'axe = un combat coupé. Toucher une flèche place
// la vidéo à ce moment.
function Graphe({ signes, combats, coches, fin, aller }) {
  const W = 320
  const H = 300
  const L = 14
  const R = 306
  const base = 262
  const VW = 62
  const VH = 66
  const X = (t) => L + (Math.min(t, fin) / fin) * (R - L)
  const pas = fin > 600 ? 120 : fin > 120 ? 30 : 5
  const ticks = []
  for (let t = 0; t <= fin; t += pas) ticks.push(t)
  return (
    <svg className="sc-graphe" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Signes repérés dans le temps">
      {combats.map((c, i) => (
        <rect key={i} x={X(c.start)} y={base - 10} width={Math.max(X(c.end) - X(c.start), 2)} height="10" rx="3" className="sc-graphe__combat" />
      ))}
      <line x1={L} y1={base} x2={R} y2={base} className="sc-graphe__axe" />
      {ticks.map((t) => (
        <g key={t}>
          <line x1={X(t)} y1={base} x2={X(t)} y2={base + 5} className="sc-graphe__axe" />
          <text x={X(t)} y={base + 18} className="sc-graphe__tick">
            {mmss(t)}
          </text>
        </g>
      ))}
      <text x={R} y={base + 34} className="sc-graphe__tick" style={{ textAnchor: 'end' }}>
        temps
      </text>
      {signes.map((s, i) => {
        const sg = signe(s.kind)
        const cls = coches.includes(s.kind) ? sg.g : 'off'
        const x = X(s.start)
        const top = 4 + (i % 2) * 118
        const bx = Math.min(Math.max(x - VW / 2, 0), W - VW)
        const tip = top + VH + 32
        const tx = Math.min(Math.max(bx + VW / 2, 50), W - 50)
        return (
          <g
            key={i}
            className={`sc-graphe__ev sc-graphe__ev--${cls}`}
            role="button"
            tabIndex={0}
            aria-label={`${mmss(s.start)} ${sg.l}`}
            onClick={() => aller(s.start)}
            onKeyDown={(ev) => ev.key === 'Enter' && aller(s.start)}
          >
            <rect x={bx - 2} y={top - 2} width={VW + 4} height={VH + 4} rx="6" className="sc-graphe__cadre" />
            {s.thumb && <image href={s.thumb} x={bx} y={top} width={VW} height={VH} preserveAspectRatio="xMidYMid slice" />}
            <text x={tx} y={top + VH + 14} className="sc-graphe__nom">
              {sg.court}
            </text>
            <text x={tx} y={top + VH + 27} className="sc-graphe__t">
              {mmss(s.start)}
            </text>
            <line x1={x} y1={base - 1} x2={x} y2={tip + 4} className="sc-graphe__fl" />
            <path d={`M${x - 5} ${tip + 10} L${x} ${tip} L${x + 5} ${tip + 10}Z`} className="sc-graphe__pt" />
          </g>
        )
      })}
    </svg>
  )
}
