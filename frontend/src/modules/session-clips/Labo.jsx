import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
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

export function Labo({ ecoleId, version, rafraichir, montrer, essaisCaches, onOpen }) {
  const [liste, setListe] = useState(null)
  const champ = useRef(null)
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

  const visibles = liste?.filter((e) => !essaisCaches.has(e.id))
  return (
    <>
      <button type="button" className="btn btn--primary sc-bouton" onClick={() => champ.current?.click()}>
        Importer une vidéo
      </button>
      <input
        ref={champ}
        type="file"
        accept="video/*"
        hidden
        onChange={(ev) => {
          importer(ev.target.files?.[0])
          ev.target.value = ''
        }}
      />
      <p className="sc-meta">Une vidéo de la Galerie, lue tout de suite. Pour essayer les signes : rien ne va dans Mes combats.</p>
      {visibles?.length === 0 && <p className="sc-vide">Aucun essai pour l’instant.</p>}
      {visibles?.map((e) => (
        <button
          key={e.id}
          type="button"
          className="sc-carte"
          aria-disabled={e.status !== 'ready'}
          onClick={() => e.status === 'ready' && onOpen(e.id)}
        >
          <span className="sc-carte__info">
            <strong>{e.title || 'Essai'}</strong>
            <span className="sc-meta">
              <EtatEssai e={e} />
            </span>
          </span>
        </button>
      ))}
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
  const [coches, setCoches] = useState(null) // ceux de l'écran
  const [club, setClub] = useState(null) // ceux enregistrés
  const [enCours, setEnCours] = useState(false)
  const [duree, setDuree] = useState(null)
  const lecteur = useRef(null)
  useEffect(() => {
    api.essaiLabo(essaiId).then(setE, (err) => montrer(err.message))
  }, [essaiId, version, montrer])
  useEffect(() => {
    api.signesDuClub().then((s) => {
      setClub(s)
      setCoches(s)
    }, (err) => montrer(err.message))
  }, [montrer])

  function aller(t) {
    const v = lecteur.current
    if (!v) return
    v.currentTime = t
    v.play?.().catch(() => {})
  }

  function cocher(id) {
    setCoches((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]))
  }

  async function relancer() {
    setEnCours(true)
    try {
      const s = await api.reglerSignes(coches)
      setClub(s)
      setCoches(s)
      rafraichir()
      montrer('Découpe relancée')
    } catch (err) {
      montrer(err.message)
    } finally {
      setEnCours(false)
    }
  }

  const fin = Math.max(duree || e?.video?.dureeSecondes || 0, ...(e?.signs ?? []).map((s) => s.end + 2), 1)
  const change = coches && club && [...coches].sort().join() !== [...club].sort().join()
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour au Labo">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">{e?.title ?? ''}</strong>
      </div>
      {e && coches && (
        <div className="sc__corps">
          {e.video?.url && (
            <video
              ref={lecteur}
              className="sc-apercu"
              src={e.video.url}
              controls
              playsInline
              onLoadedMetadata={(ev) => setDuree(ev.currentTarget.duration)}
            />
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
            <button key={i} type="button" className="sc-carte" onClick={() => aller(c.start)}>
              <span className="sc-carte__info">
                <strong>Combat {i + 1}</strong>
                <span className="sc-meta">
                  {mmss(c.start)} → {mmss(c.end)}
                  {c.check_reason && <span className="sc-chip sc-chip--warn">Fin non repérée</span>}
                </span>
              </span>
            </button>
          ))}
          <h3 className="sc-section">Signes et sons du club</h3>
          <div className="sc-cadre">
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
          </div>
          <button type="button" className="btn btn--primary sc-bouton" disabled={!change || enCours} onClick={relancer}>
            Relancer la découpe
          </button>
          <button type="button" className="btn btn--secondary sc-bouton" onClick={() => onSupprimer(e.id)}>
            Supprimer l’essai
          </button>
        </div>
      )}
    </div>
  )
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
