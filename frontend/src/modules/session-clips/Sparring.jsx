import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
import Modal from '../../components/Modal.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import VideoThumb from '../../components/VideoThumb.jsx'
import {
  annulerTeleversement,
  demarrerTeleversement,
  finaliserTeleversement,
  useProgressionVideo,
  useTeleversementsTermines,
} from '../../utils/videoUploads.js'
import * as api from './api.js'
import { Deroulant, EssaiLabo, Graphe, Labo, ParametresTournage, useSuppressionEssai } from './Labo.jsx'
import Tournage from './Tournage.jsx'
import './sparring.css'

// Sparring (spec/modules/video-combats.md §6, maquette validée
// spec/maquettes/sparring.html). Un membre n'a que « Mes combats » ; un coach
// a aussi Tournage (Tournage.jsx), Séances, À vérifier et Labo (Labo.jsx). Une séance ouverte et un clip lu s'affichent
// en plein écran avec la flèche de retour, comme une chorégraphie.
//
// Le + filme un combat à la main (FilmerCombat) ; la séance entière filmée
// en continu viendra avec l'enregistreur (étape 3).

const ANNULER_MS = 10000
const AUCUN = new Map()
// Le dernier sous-onglet ouvert, retrouvé à la réouverture de l'appli (Seb, 12/11).
const ONGLET_VU = 'sc-onglet'

function ongletGarde() {
  try {
    return localStorage.getItem(ONGLET_VU)
  } catch {
    return null
  }
}

export default function Sparring({ ecoleId, cours }) {
  const [me, setMe] = useState(null)
  const [onglet, setOnglet] = useState('mes')
  const [ouvert, setOuvert] = useState(null) // { seanceId } | { clipId, retour }
  const [toast, setToast] = useState(null) // { texte, annuler }
  const minuteur = useRef(null)
  const [version, setVersion] = useState(0)
  const rafraichir = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    api.moi().then((m) => {
      setMe(m)
      if (m.is_coach) setOnglet(['tournage', 'mes'].includes(ongletGarde()) ? ongletGarde() : 'tournage')
    }, () => setMe({ person_id: null, is_coach: false }))
  }, [])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const montrer = useCallback((texte, annuler) => {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), annuler ? ANNULER_MS : 3000)
  }, [])

  // Supprimer : les clips disparaissent tout de suite, partent vraiment au
  // bout de 10 s. Un numéro ou une liste (sélection par appui long).
  const [caches, setCaches] = useState(new Set())
  const supprimer = useCallback(
    (ids) => {
      const liste = [].concat(ids)
      setCaches((c) => new Set([...c, ...liste]))
      const retard = setTimeout(() => {
        Promise.all(liste.map((id) => api.supprimer(id))).then(rafraichir, (e) => montrer(e.message))
      }, ANNULER_MS)
      montrer(liste.length > 1 ? `${liste.length} clips supprimés` : 'Clip supprimé', () => {
        clearTimeout(retard)
        setCaches((c) => {
          const n = new Set(c)
          liste.forEach((id) => n.delete(id))
          return n
        })
      })
    },
    [montrer, rafraichir],
  )

  // Sélection par appui long sur un combat (Seb, 27/10) : Favoris, Partager,
  // Supprimer (coachs). Elle appartient à l'écran où elle a été faite : on
  // change d'écran, elle disparaît.
  const cle = `${onglet}|${ouvert?.seanceId ?? ''}|${ouvert?.favoris ? 'f' : ''}|${ouvert?.clipId ?? ''}`
  const [selection, setSelection] = useState({ cle: '', clips: new Map() })
  const choisis = selection.cle === cle ? selection.clips : AUCUN
  const basculer = useCallback(
    (c) => {
      setSelection((sel) => {
        const n = new Map(sel.cle === cle ? sel.clips : AUCUN)
        if (n.has(c.id)) n.delete(c.id)
        else n.set(c.id, c)
        return { cle, clips: n }
      })
    },
    [cle],
  )
  const vider = useCallback(() => setSelection({ cle: '', clips: AUCUN }), [])

  const [essaisCaches, supprimerEssai] = useSuppressionEssai(montrer, rafraichir)
  // Combats à identifier : pastille de l'onglet Tournage et de son volet.
  const [aIdentifier, setAIdentifier] = useState(0)
  useEffect(() => {
    if (me?.is_coach) api.aVerifier().then((l) => setAIdentifier(l.length), () => {})
  }, [version, me])
  function choisirOnglet(o) {
    setOnglet(o)
    try {
      localStorage.setItem(ONGLET_VU, o)
    } catch {
      // stockage refusé : on garde l'onglet pour cette fois
    }
  }

  if (!me) return <div className="screen sc" aria-busy="true" />

  const contexte = { me, ecoleId, cours, version, rafraichir, montrer, supprimer, caches, choisis, basculer }

  let ecran
  if (ouvert?.essaiId) {
    ecran = (
      <EssaiLabo
        {...contexte}
        essaiId={ouvert.essaiId}
        onBack={() => setOuvert({ labo: true })}
        onSupprimer={(id) => {
          setOuvert({ labo: true })
          supprimerEssai(id)
        }}
      />
    )
  } else if (ouvert?.parametres) {
    ecran = <ParametresTournage montrer={montrer} onBack={() => setOuvert(null)} />
  } else if (ouvert?.labo) {
    // Fights › ⋮ › Tests de découpage vidéo (Seb, 12/11 : l'ancien
    // sous-onglet Labo, sorti des puces).
    ecran = (
      <div className="screen sc">
        <div className="thread-screen__header">
          <button type="button" className="icon-btn" onClick={() => setOuvert(null)} aria-label="Retour">
            <Icon name="chevronLeft" size={22} />
          </button>
          <strong className="sc__titre">Tests de découpage vidéo</strong>
        </div>
        <div className="sc__corps">
          <Labo
            {...contexte}
            essaisCaches={essaisCaches}
            onOpen={(id) => setOuvert({ essaiId: id })}
            onSupprimer={supprimerEssai}
          />
        </div>
      </div>
    )
  } else if (ouvert?.clipId) {
    ecran = (
      <Lecture
        {...contexte}
        clipId={ouvert.clipId}
        onBack={() => setOuvert(ouvert.retour)}
        onOpen={(id) => setOuvert({ clipId: id, retour: ouvert.retour })}
      />
    )
  } else if (ouvert?.favoris) {
    ecran = (
      <Favoris
        {...contexte}
        onBack={() => setOuvert(null)}
        onOpen={(id) => setOuvert({ clipId: id, retour: ouvert })}
      />
    )
  } else if (ouvert?.seanceId) {
    ecran = (
      <DossierSeance
        {...contexte}
        seanceId={ouvert.seanceId}
        onBack={() => setOuvert(null)}
        onOpen={(id) => setOuvert({ clipId: id, retour: ouvert })}
      />
    )
  } else {
    ecran = (
      <div className="screen sc">
        {me.is_coach && (
          <MenuEntete
            label="Actions de Fights"
            actions={[
              { label: 'Paramètres de tournage', icon: 'camera', onClick: () => setOuvert({ parametres: true }) },
              { label: 'Tests de découpage vidéo', icon: 'video', onClick: () => setOuvert({ labo: true }) },
            ]}
          />
        )}
        {me.is_coach && <Onglets onglet={onglet} onChange={choisirOnglet} aIdentifier={aIdentifier} />}
        <div className="sc__corps">
          {onglet !== 'tournage' && <EntreeFavoris onOpen={() => setOuvert({ favoris: true })} />}
          {/* Tournage, Montage (les séances filmées), puis Identifier combattants
              (l'ancien onglet À vérifier) en volets (Seb, 12/11 au soir). */}
          {onglet === 'tournage' && (
            <>
              <Deroulant titre="Tournage" ouvertAuDepart>
                <Tournage montrer={montrer} rafraichir={rafraichir} />
              </Deroulant>
              <Deroulant titre="Montage" ouvertAuDepart>
                <Seances {...contexte} onOpen={(id) => setOuvert({ seanceId: id })} />
              </Deroulant>
              <Deroulant
                titre={
                  <>
                    Identifier combattants
                    {aIdentifier > 0 && <span className="sc-pastille">{aIdentifier}</span>}
                  </>
                }
                ouvertAuDepart
              >
                <AVerifier {...contexte} />
              </Deroulant>
            </>
          )}
          {onglet === 'mes' && <MesCombats {...contexte} onOpen={(id) => setOuvert({ clipId: id, retour: null })} />}
        </div>
      </div>
    )
  }

  return (
    <>
      {ecran}
      {choisis.size > 0 && (
        <BarreSelection me={me} choisis={choisis} vider={vider} montrer={montrer} supprimer={supprimer} rafraichir={rafraichir} />
      )}
      {toast && (
        <div className="sc-toast" role="status">
          <span>{toast.texte}</span>
          {toast.annuler && (
            <button
              type="button"
              onClick={() => {
                toast.annuler()
                clearTimeout(minuteur.current)
                setToast(null)
              }}
            >
              Annuler
            </button>
          )}
        </div>
      )}
    </>
  )
}

function Onglets({ onglet, onChange, aIdentifier }) {
  const onglets = [
    ['mes', 'Combats'],
    ['tournage', 'Tournage'],
  ]
  // Mêmes onglets en pastilles qu'Admin (Seb, 27 octobre).
  return (
    <SegmentedTabs
      className="admin-screen__tabs sc-onglets"
      value={onglet}
      onChange={onChange}
      options={onglets.map(([cle, libelle]) => ({
        value: cle,
        label: (
          <>
            {libelle}
            {cle === 'tournage' && aIdentifier > 0 && <span className="sc-pastille">{aIdentifier}</span>}
          </>
        ),
      }))}
    />
  )
}

function duree(video) {
  const s = video?.dureeSecondes
  return s ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')}` : ''
}

function Vignette({ video }) {
  return (
    <span className="sc-vignette">
      {video?.poster ? <img src={video.poster} alt="" /> : <Icon name="video" size={22} />}
    </span>
  )
}

function adversaires(c, me) {
  const autres = c.participants.filter((p) => p.person_id !== me.person_id).map((p) => p.name ?? '?')
  return autres.length ? `vs ${autres.join(', ')}` : c.title
}

function MesCombats({ me, version, caches, choisis, basculer, onOpen }) {
  const [clips, setClips] = useState(null)
  useEffect(() => {
    api.mesCombats().then(setClips, () => setClips([]))
  }, [version])
  if (!clips) return null
  const visibles = clips.filter((c) => !caches.has(c.id))
  if (!visibles.length) return <p className="sc-vide">Vos combats filmés apparaîtront ici le lendemain de la séance.</p>
  return visibles.map((c, i) => {
    const entete = c.session_id !== visibles[i - 1]?.session_id
    return (
      <div key={c.id} className="sc-groupe">
        {entete && (
          <div className="sc-jour">
            {api.jour(c.held_on)}
            {c.session_title ? ` · ${c.session_title}` : ''}
          </div>
        )}
        <LigneClip c={c} choisis={choisis} basculer={basculer} onOpen={onOpen}>
          <strong>{adversaires(c, me)}</strong>
          <span className="sc-meta">
            Combat {c.position}
            {duree(c.video) && ` · ${duree(c.video)}`}
          </span>
        </LigneClip>
      </div>
    )
  })
}

function LigneCoach({ c, choisis, basculer, onOpen }) {
  return (
    <LigneClip c={c} choisis={choisis} basculer={basculer} onOpen={onOpen}>
      <strong>{c.title}</strong>
      <span className="sc-meta">
        Combat {c.position}
        {c.to_check && <span className="sc-chip sc-chip--warn">À vérifier</span>}
      </span>
    </LigneClip>
  )
}

// Une ligne de combat : un appui l'ouvre, un appui long la sélectionne ;
// pendant une sélection, un appui ajoute ou retire.
function LigneClip({ c, choisis, basculer, onOpen, children }) {
  const minuteur = useRef(null)
  const long = useRef(false)
  const choisi = choisis?.has(c.id)
  const lacher = () => clearTimeout(minuteur.current)
  return (
    <button
      type="button"
      className={`sc-clip${choisi ? ' sc-clip--choisi' : ''}`}
      onPointerDown={() => {
        long.current = false
        if (!basculer) return
        minuteur.current = setTimeout(() => {
          long.current = true
          basculer(c)
        }, 500)
      }}
      onPointerUp={lacher}
      onPointerLeave={lacher}
      onPointerCancel={lacher}
      onContextMenu={(e) => e.preventDefault()}
      onClick={() => {
        if (long.current) return
        if (choisis?.size) basculer(c)
        else onOpen(c.id)
      }}
    >
      <Vignette video={c.video} />
      <span>
        {children}
        {c.favorite && <Icon name="star" size={16} className="sc-etoile" />}
      </span>
    </button>
  )
}

// En tête de « Mes combats » et de « Séances » : le dossier ★ Favoris.
function EntreeFavoris({ onOpen }) {
  return (
    <button type="button" className="sc-favoris" onClick={onOpen}>
      <Icon name="star" size={22} />
      <strong>Favoris</strong>
      <Icon name="chevronRight" size={20} />
    </button>
  )
}

function Favoris({ me, version, caches, choisis, basculer, onBack, onOpen, montrer }) {
  const [clips, setClips] = useState(null)
  useEffect(() => {
    api.favoris().then(setClips, (e) => montrer(e.message))
  }, [version, montrer])
  const visibles = clips?.filter((c) => !caches.has(c.id))
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">Favoris</strong>
      </div>
      <div className="sc__corps">
        {visibles?.length === 0 && (
          <p className="sc-vide">Appuyez longtemps sur un combat, puis sur l’étoile, pour le garder ici.</p>
        )}
        {visibles?.map((c) => (
          <LigneClip key={c.id} c={c} choisis={choisis} basculer={basculer} onOpen={onOpen}>
            <strong>{me.is_coach ? c.title : adversaires(c, me)}</strong>
            <span className="sc-meta">
              {api.jour(c.held_on)} · combat {c.position}
            </span>
          </LigneClip>
        ))}
      </div>
    </div>
  )
}

// La barre d'une sélection, par-dessus l'en-tête : ★, Partager, Supprimer.
function BarreSelection({ me, choisis, vider, montrer, supprimer, rafraichir }) {
  const clips = [...choisis.values()]
  const tousFavoris = clips.every((c) => c.favorite)

  async function favoris() {
    try {
      await Promise.all(clips.map((c) => api.favori(c.id, !tousFavoris)))
      montrer(tousFavoris ? 'Retiré des favoris' : 'Mis dans les favoris')
      vider()
      rafraichir()
    } catch (e) {
      montrer(e.message)
    }
  }

  async function partager() {
    try {
      if (!(await api.partager(clips))) await api.telecharger(clips)
    } catch (e) {
      montrer(e.message)
    }
  }

  return (
    <div className="sc-selection" role="toolbar">
      <button type="button" className="icon-btn" onClick={vider} aria-label="Annuler la sélection">
        <Icon name="x" size={22} />
      </button>
      <strong>
        {clips.length} sélectionné{clips.length > 1 ? 's' : ''}
      </strong>
      <button
        type="button"
        className="icon-btn"
        onClick={favoris}
        aria-label={tousFavoris ? 'Retirer des favoris' : 'Mettre dans les favoris'}
      >
        <Icon name="star" size={22} />
      </button>
      <button type="button" className="icon-btn" onClick={partager} aria-label="Partager">
        <Icon name="partager" size={22} />
      </button>
      {me.is_coach && (
        <button
          type="button"
          className="icon-btn"
          onClick={() => {
            supprimer(clips.map((c) => c.id))
            vider()
          }}
          aria-label="Supprimer"
        >
          <Icon name="trash" size={22} />
        </button>
      )}
    </div>
  )
}

// Caméra de la salle (Seb, 12/11) : « 21:40 → 21:46 · 6 min », ou
// « Depuis 21:40 » pendant le film.
function horaire(s) {
  const debut = new Date(`${s.started_at}Z`)
  const heure = (d) => d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  // Toujours début et fin (Seb, 13/11) : la fin est l'appui sur Arrêter,
  // sinon la durée filmée arrivée.
  const fin = s.ended_at ? new Date(`${s.ended_at}Z`) : s.filmed_seconds ? new Date(debut.getTime() + s.filmed_seconds * 1000) : null
  if (s.status === 'recording' || !fin) return `${heure(debut)} → …`
  return `${heure(debut)} → ${heure(fin)} · ${Math.max(1, Math.round((fin - debut) / 60000))} min`
}

function EtatSeance({ s }) {
  const progression = useProgressionVideo(s.status === 'uploading' ? s.raw_video?.id : null)
  if (s.status === 'uploading') {
    const pct = progression?.octetsTotal ? Math.round((progression.octetsEnvoyes / progression.octetsTotal) * 100) : null
    return (
      <>
        <span className="sc-chip sc-chip--info">{pct === null ? 'Envoi…' : `Envoi ${pct} %`}</span>
        {pct !== null && (
          <span className="sc-barre">
            <i style={{ width: `${pct}%` }} />
          </span>
        )}
      </>
    )
  }
  if (s.status === 'recording') return <span className="sc-chip sc-chip--warn">Filme</span>
  // La vidéo de la caméra en route vers le serveur (Seb, 13/11).
  if (s.status === 'processing' && s.size_bytes > 0) {
    const pct = Math.min(99, Math.floor((s.sent_bytes / s.size_bytes) * 100))
    return (
      <>
        <span className="sc-chip sc-chip--info">Envoi : {pct} %</span>
        <span className="sc-barre">
          <i style={{ width: `${pct}%` }} />
        </span>
      </>
    )
  }
  if (s.status === 'processing' && s.live) {
    // Où en est la découpe (Seb, 12/11) : la part de la vidéo arrivée déjà
    // lue (morceaux de 2 minutes, sans le dire à l'écran).
    const pct = s.pieces_total ? Math.round((s.pieces_read / s.pieces_total) * 100) : 0
    return (
      <>
        <span className="sc-chip sc-chip--info">Découpe : {pct} %</span>
        <span className="sc-barre">
          <i style={{ width: `${pct}%` }} />
        </span>
      </>
    )
  }
  // Filmée par la caméra, rien d'arrivé encore : la vidéo est sur le téléphone
  // caméra, qui l'envoie s'il est allumé sur « Caméra » (Seb, 13/11).
  if (s.status === 'processing' && !s.raw_video) {
    return s.camera_online ? (
      <span className="sc-chip sc-chip--info">Envoi : 0 %</span>
    ) : (
      <span className="sc-chip sc-chip--warn">Caméra éteinte : rouvrez Tournage</span>
    )
  }
  if (s.status === 'processing') return <span className="sc-chip sc-chip--info">Clips prêts demain matin</span>
  if (s.status === 'failed') return <span className="sc-chip sc-chip--warn">Découpe impossible</span>
  // En gros (Seb, 12/11) : rien n'a pu être découpé.
  if (s.clip_count === 0) return <span className="sc-seance__vide">Aucun combat trouvé</span>
  return (
    <>
      <span>
        {s.clip_count} combat{s.clip_count > 1 ? 's' : ''}
      </span>
      {s.to_check_count > 0 ? (
        <span className="sc-chip sc-chip--warn">{s.to_check_count} à vérifier</span>
      ) : (
        <span className="sc-chip sc-chip--ok">Vérifié</span>
      )}
    </>
  )
}

function Seances({ ecoleId, version, rafraichir, montrer, onOpen }) {
  const [liste, setListe] = useState(null)
  useEffect(() => {
    api.seances().then(setListe, (e) => montrer(e.message))
  }, [version, montrer])
  useTeleversementsTermines(rafraichir)
  // Tant qu'une séance filme, s'envoie ou se découpe, la liste se relit
  // toutes les 5 s : les pourcentages avancent seuls (Seb, 13/11).
  const enCours = liste?.some((x) => x.status === 'recording' || x.status === 'processing')
  useEffect(() => {
    if (!enCours) return undefined
    const minuteur = setInterval(() => api.seances().then(setListe, () => {}), 5000)
    return () => clearInterval(minuteur)
  }, [enCours])
  const [renommee, setRenommee] = useState(null)
  // La poubelle : la séance disparaît tout de suite, part vraiment au bout
  // de 10 s, sauf Annuler.
  const [cachees, setCachees] = useState(new Set())
  function effacer(id) {
    setCachees((c) => new Set([...c, id]))
    const retard = setTimeout(() => api.supprimerSeance(id).then(rafraichir, (e) => montrer(e.message)), ANNULER_MS)
    montrer('Séance supprimée', () => {
      clearTimeout(retard)
      setCachees((c) => new Set([...c].filter((x) => x !== id)))
    })
  }
  const visibles = liste?.filter((s) => !cachees.has(s.id))

  return (
    <>
      {visibles?.length === 0 && (
        <p className="sc-vide">Aucune séance filmée. Le + filme un combat avec le téléphone.</p>
      )}
      {visibles?.map((s) => {
        // Filmée par la caméra : ses clips s'ouvrent dès les premiers combats.
        const prete = s.status === 'ready' || (s.live && s.clip_count > 0)
        const poster = s.cover?.poster ?? s.previews[0]?.poster
        // Une ligne comme un essai du Labo (Seb, 12/11) : petite vignette,
        // crayon pour renommer, poubelle pour effacer.
        return (
          // Encadrée en vert dès un combat trouvé, en rouge si aucun (Seb, 12/11).
          <div
            key={s.id}
            className={`sc-essai${s.status !== 'ready' ? '' : s.clip_count > 0 ? ' sc-essai--trouve' : ' sc-essai--vide'}`}
          >
            <button
              type="button"
              className="sc-essai__ouvrir"
              aria-disabled={!prete}
              // Même sans combat trouvé : on y voit le film et la frise (Seb, 13/11).
              onClick={() => prete && onOpen(s.id)}
            >
              <span className="sc-vignette sc-vignette--petite">
                {poster ? <img src={poster} alt="" /> : <Icon name="video" size={20} />}
              </span>
              <span>
                <strong>
                  {api.jour(s.held_on)}
                  {s.title ? ` · ${s.title}` : ''}
                </strong>
                {/* L'état d'abord, puis l'heure (Seb, 13/11 : l'important dès le début). */}
                <span className="sc-meta">
                  <EtatSeance s={s} />
                </span>
                {s.started_at && <span className="sc-meta">{horaire(s)}</span>}
              </span>
            </button>
            <button type="button" className="icon-btn" aria-label="Renommer la séance" onClick={() => setRenommee(s)}>
              <Icon name="edit" size={20} />
            </button>
            <button type="button" className="icon-btn" aria-label="Supprimer la séance" onClick={() => effacer(s.id)}>
              <Icon name="trash" size={20} />
            </button>
          </div>
        )
      })}
      {renommee && (
        <RenommerSeance
          seance={renommee}
          montrer={montrer}
          onClose={() => setRenommee(null)}
          onRenommee={() => {
            setRenommee(null)
            rafraichir()
          }}
        />
      )}
      <FilmerCombat ecoleId={ecoleId} onEnvoye={rafraichir} montrer={montrer} />
    </>
  )
}

// Le crayon d'une séance (Seb, 12/11), comme celui d'un essai du Labo.
function RenommerSeance({ seance, montrer, onClose, onRenommee }) {
  const [nom, setNom] = useState(seance.title)
  async function enregistrer() {
    try {
      onRenommee(await api.renommerSeance(seance.id, nom))
    } catch (err) {
      montrer(err.message)
    }
  }
  return (
    <Modal
      title="Renommer la séance"
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

// Le + : « Filmer un combat » (Seb, 27/10). L'appareil photo du téléphone
// s'ouvre ; une fois le combat filmé, on le garde ou on le jette, et
// seulement s'il est gardé on choisit les deux combattants. L'envoi par
// blocs du module Vidéos (utils/videoUploads.js) démarre dès la vidéo
// filmée ; le combat rejoint la séance du jour, sans découpe.
function FilmerCombat({ ecoleId, onEnvoye, montrer }) {
  const [film, setFilm] = useState(null) // { url, uploadId, garde }
  const [noms, setNoms] = useState([null, null]) // { id, name } Rouge, Bleu
  const [enCours, setEnCours] = useState(false)

  async function filme(fichier) {
    if (!fichier) return
    const url = URL.createObjectURL(fichier)
    setNoms([null, null])
    setFilm({ url, uploadId: null, garde: false })
    try {
      const uploadId = await demarrerTeleversement(ecoleId, fichier)
      setFilm((f) => (f?.url === url ? { ...f, uploadId } : f))
    } catch (e) {
      URL.revokeObjectURL(url)
      setFilm(null)
      montrer(e.message)
    }
  }

  function fermer() {
    URL.revokeObjectURL(film.url)
    setFilm(null)
  }

  // Jeter : la vidéo disparaît, l'envoi s'arrête au bout de 10 s.
  function jeter() {
    const f = film
    setFilm(null)
    const retard = setTimeout(() => {
      URL.revokeObjectURL(f.url)
      if (f.uploadId) annulerTeleversement(f.uploadId)
    }, ANNULER_MS)
    montrer('Combat jeté', () => {
      clearTimeout(retard)
      setFilm(f)
    })
  }

  async function enregistrer() {
    if (enCours || !film.uploadId) return
    setEnCours(true)
    try {
      await finaliserTeleversement(film.uploadId, async (uploadId) => {
        const c = await api.filmerCombat({ upload_id: uploadId, people: noms.map((n) => n.id) })
        return c.video
      })
      montrer(`${noms.map((n) => n.name).join(' vs ')} : gardé`)
      fermer()
      onEnvoye()
    } catch (e) {
      montrer(e.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <>
      <label className="fab" aria-label="Filmer un combat">
        <Icon name="plus" size={24} />
        <input
          type="file"
          accept="video/*"
          capture="environment"
          hidden
          onChange={(e) => {
            filme(e.target.files[0])
            e.target.value = ''
          }}
        />
      </label>
      {film && !film.garde && (
        <Modal
          title="Garder ce combat ?"
          onClose={jeter}
          footer={
            <div className="video-upload-form__actions">
              <button type="button" className="btn btn--secondary" onClick={jeter}>
                Jeter
              </button>
              <button type="button" className="btn btn--primary" onClick={() => setFilm({ ...film, garde: true })}>
                Garder
              </button>
            </div>
          }
        >
          <video className="sc-apercu" src={film.url} controls playsInline />
        </Modal>
      )}
      {film?.garde && (
        <Modal
          title="Qui combattait ?"
          onClose={jeter}
          footer={
            <div className="video-upload-form__actions">
              <button type="button" className="btn btn--secondary" onClick={jeter}>
                Jeter
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={!film.uploadId || noms.includes(null) || enCours}
                onClick={enregistrer}
              >
                C’est bon
              </button>
            </div>
          }
        >
          {['Rouge', 'Bleu'].map((cote, i) => (
            <ChoixCombattant
              key={cote}
              cote={cote}
              index={i}
              choisi={noms[i]}
              autre={noms[1 - i]}
              onChoisir={(p) => setNoms((n) => n.map((x, j) => (j === i ? p : x)))}
            />
          ))}
        </Modal>
      )}
    </>
  )
}

const sansAccents = (t) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

// La voix du navigateur (comme la dictée de l'assistant, modules/documents/
// Dictee.js) : une seule phrase, ici un nom. Absente de Firefox.
const Reconnaissance = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

// Un combattant : les premières lettres de son nom ou sa voix, puis un
// appui sur le bon membre dans la liste.
function ChoixCombattant({ cote, index, choisi, autre, onChoisir }) {
  const [membres, setMembres] = useState([])
  const [cherche, setCherche] = useState('')
  const [ecoute, setEcoute] = useState(false)
  useEffect(() => {
    api.membres().then(setMembres, () => {})
  }, [])

  function ecouter() {
    const r = new Reconnaissance()
    r.lang = 'fr-FR'
    r.onresult = (e) => setCherche(e.results[0][0].transcript)
    r.onend = () => setEcoute(false)
    setEcoute(true)
    r.start()
  }

  // Chaque mot tapé ou dit doit commencer un mot du nom : « seb r », « richard ».
  const mots = sansAccents(cherche).split(/\s+/).filter(Boolean)
  const liste = mots.length
    ? membres
        .filter((p) => p.id !== autre?.id)
        .filter((p) => {
          const nom = sansAccents(p.name).split(/[\s.-]+/)
          return mots.every((m) => nom.some((n) => n.startsWith(m.replace('.', ''))))
        })
        .slice(0, 6)
    : []

  return (
    <div className="sc-combattant">
      <div className="sc-combattant__cote">
        <span className={`sc-point sc-point--${index === 0 ? 'rouge' : 'bleu'}`} />
        {cote}
      </div>
      {choisi ? (
        <button type="button" className="sc-nom" onClick={() => onChoisir(null)}>
          <b>{choisi.name}</b>
          <Icon name="x" size={20} />
        </button>
      ) : (
        <>
          <div className="sc-combattant__saisie">
            <input
              className="field-input"
              placeholder="Premières lettres du nom"
              value={cherche}
              onChange={(e) => setCherche(e.target.value)}
            />
            {Reconnaissance && (
              <button
                type="button"
                className={`icon-btn${ecoute ? ' sc-micro--ecoute' : ''}`}
                aria-label="Dire le nom"
                onClick={ecouter}
              >
                <Icon name="micro" size={22} />
              </button>
            )}
          </div>
          {liste.map((p) => (
            <button key={p.id} type="button" className="sc-combattant__membre" onClick={() => onChoisir(p)}>
              {p.name}
            </button>
          ))}
        </>
      )}
    </div>
  )
}

function DossierSeance({ seanceId, version, caches, choisis, basculer, onBack, onOpen, montrer, rafraichir }) {
  const [s, setS] = useState(null)
  const [edite, setEdite] = useState(null) // le combat au crayon
  useEffect(() => {
    api.detailSeance(seanceId).then(setS, (e) => montrer(e.message))
  }, [seanceId, version, montrer])
  const [club, setClub] = useState(null) // Paramètres de tournage : signes cochés, frise
  useEffect(() => {
    api.reglagesDuClub().then(setClub, () => {})
  }, [])
  // La frise (Seb, 13/11) : chaque combat de son début à sa fin dans la séance.
  const combats = (s?.clips ?? [])
    .filter((c) => c.start_seconds != null)
    .map((c) => ({ id: c.id, start: c.start_seconds, end: c.start_seconds + (c.video?.dureeSecondes || 0) }))
  const film = s?.film ?? []
  const bout = film.at(-1)
  const fin = Math.max(
    1,
    ...(s?.signs ?? []).map((x) => x.end + 2),
    ...combats.map((c) => c.end),
    bout ? bout.start + (bout.video?.dureeSecondes || 0) : 0,
  )
  const frise = club && club.show_timeline !== false && s

  // Le film de la séance, bout après bout (la caméra l'envoie par 2 minutes).
  const lecteur = useRef(null)
  const [partie, setPartie] = useState(0)
  const saut = useRef(null) // où aller une fois le bon bout chargé
  function voir(t) {
    let i = 0
    while (i + 1 < film.length && film[i + 1].start <= t) i += 1
    const v = lecteur.current
    if (!v) return
    v.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    if (i === partie) {
      v.currentTime = t - film[i].start
      v.play?.().catch(() => {})
    } else {
      saut.current = t - film[i].start
      setPartie(i)
    }
  }

  async function relancer() {
    try {
      await api.relancerDecoupe(seanceId)
      montrer('Découpe relancée')
      rafraichir()
      onBack()
    } catch (e) {
      montrer(e.message)
    }
  }

  // « C'est bon » sous le crayon : validé s'il était à identifier.
  async function fini(c) {
    try {
      if (c.to_check) await api.valider(c.id)
      setEdite(null)
      rafraichir()
    } catch (e) {
      montrer(e.message)
    }
  }
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux séances">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">{s ? `${api.jour(s.held_on)}${s.title ? ` · ${s.title}` : ''}` : ''}</strong>
      </div>
      <div className="sc__corps">
        {film.length > 0 && (
          <Deroulant titre="Vidéo de la séance" ouvertAuDepart>
            <video
              ref={lecteur}
              className="sc-apercu"
              src={film[partie]?.video?.url}
              controls
              playsInline
              onLoadedMetadata={(ev) => {
                if (saut.current == null) return
                ev.currentTarget.currentTime = saut.current
                saut.current = null
                ev.currentTarget.play().catch(() => {})
              }}
              onEnded={() => {
                if (partie + 1 < film.length) {
                  saut.current = 0
                  setPartie(partie + 1)
                }
              }}
            />
          </Deroulant>
        )}
        {frise && (
          <Deroulant titre="Signes repérés" ouvertAuDepart>
            {s.signs.length === 0 ? (
              <p className="sc-meta">Aucun signe repéré.</p>
            ) : (
              <Graphe
                signes={s.signs}
                combats={combats}
                coches={club.signs}
                fin={fin}
                // Toucher un signe le montre dans la vidéo de la séance,
                // sinon ouvre le combat où il tombe.
                aller={(t) => {
                  if (film.length > 0) return voir(t)
                  const c = combats.find((x) => x.start - 2 <= t && t <= x.end + 2)
                  if (c) onOpen(c.id)
                }}
              />
            )}
          </Deroulant>
        )}
        {s?.attendees.length > 0 && (
          <p className="sc-meta">Présents reconnus : {s.attendees.map((p) => p.name).join(', ')}</p>
        )}
        {s?.clips
          .filter((c) => !caches.has(c.id))
          .map((c) => (
            <div key={c.id}>
              <div className="sc-clip-ligne">
                <LigneCoach c={c} choisis={choisis} basculer={basculer} onOpen={onOpen} />
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Changer les combattants"
                  onClick={() => setEdite(edite === c.id ? null : c.id)}
                >
                  <Icon name="edit" size={20} />
                </button>
              </div>
              {edite === c.id && (
                <Combattants
                  c={c}
                  montrer={montrer}
                  onChange={(maj) => setS((x) => ({ ...x, clips: x.clips.map((y) => (y.id === maj.id ? maj : y)) }))}
                  onValider={() => fini(c)}
                />
              )}
            </div>
          ))}
        {/* Les règles de la découpe changent : la refaire sans refilmer (Seb, 13/11). */}
        {s?.live && s.status === 'ready' && (
          <button type="button" className="btn btn--secondary" onClick={relancer}>
            Relancer la découpe
          </button>
        )}
      </div>
    </div>
  )
}

// Choisir un nom : les présents de la séance, puis « Un autre membre… ».
function ChoixNom({ seanceId, onChoisir, onClose }) {
  const [presents, setPresents] = useState([])
  const [tous, setTous] = useState(null)
  const [cherche, setCherche] = useState('')
  useEffect(() => {
    api.detailSeance(seanceId).then((s) => setPresents(s.attendees), () => {})
  }, [seanceId])
  const sansAccents = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
  const liste = tous ? tous.filter((p) => sansAccents(p.name).includes(sansAccents(cherche))) : presents
  return (
    <div className="sc-feuille-fond" onClick={onClose}>
      <div className="sc-feuille" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        {tous ? (
          <input
            className="field-input"
            autoFocus
            placeholder="Chercher un membre"
            value={cherche}
            onChange={(e) => setCherche(e.target.value)}
          />
        ) : (
          <h3>Présents à la séance</h3>
        )}
        {liste.map((p) => (
          <button key={p.id} type="button" onClick={() => onChoisir(p.id)}>
            {p.name}
          </button>
        ))}
        {!tous && (
          <button type="button" onClick={() => api.membres().then(setTous, () => setTous([]))}>
            Un autre membre…
          </button>
        )}
      </div>
    </div>
  )
}

function Noms({ c }) {
  if (c.participants.every((p) => p.person_id === null)) return <div className="sc-noms">Combat sans nom</div>
  return (
    <div className="sc-noms">
      {c.participants.map((p, i) => (
        <span key={i}>
          {c.participants.length === 2 && <span className={`sc-point sc-point--${i === 0 ? 'rouge' : 'bleu'}`} />}
          {p.name ?? '?'}
        </span>
      ))}
    </div>
  )
}

function AVerifier({ version, caches, rafraichir, montrer, supprimer }) {
  const [file, setFile] = useState(null)
  useEffect(() => {
    api.aVerifier().then(setFile, (e) => montrer(e.message))
  }, [version, montrer])
  if (!file) return null
  const visibles = file.filter((c) => !caches.has(c.id))
  if (!visibles.length) return <p className="sc-vide">Tout est vérifié. Les clips sont dans « Mes combats » de chaque membre.</p>
  const c = visibles[0]

  async function valider() {
    try {
      await api.valider(c.id)
      montrer(`${c.participants.map((p) => p.name).join(' – ')} : validé`)
      rafraichir()
    } catch (e) {
      montrer(e.message)
    }
  }

  return (
    <>
      <p className="sc-meta">
        1 sur {visibles.length} · {api.jour(c.held_on)} · combat {c.position}
      </p>
      {c.video && <VideoThumb key={c.id} video={c.video} />}
      {c.check_reason && <p className="sc-raison">{c.check_reason}</p>}
      <Combattants
        c={c}
        montrer={montrer}
        onChange={(maj) => setFile((f) => f.map((x) => (x.id === maj.id ? maj : x)))}
        onValider={valider}
      />
      <button type="button" className="sc-lien" onClick={() => supprimer(c.id)}>
        Supprimer ce clip
      </button>
    </>
  )
}

// Rouge et Bleu (toucher pour choisir), Inverser et « C'est bon » : dans
// Identifier combattants et sous le crayon d'un combat de la séance (Seb, 12/11).
function Combattants({ c, montrer, onChange, onValider }) {
  const [choix, setChoix] = useState(null) // place à nommer
  const people = c.participants.map((p) => p.person_id)

  async function nommer(nouveaux) {
    try {
      onChange(await api.nommer(c.id, nouveaux))
    } catch (e) {
      montrer(e.message)
    }
  }

  return (
    <>
      {c.participants.map((p, i) => (
        <button key={i} type="button" className="sc-nom" onClick={() => setChoix(i)}>
          {c.participants.length === 2 && <span className={`sc-point sc-point--${i === 0 ? 'rouge' : 'bleu'}`} />}
          {c.participants.length === 2 && <span className="sc-nom__cote">{i === 0 ? 'Rouge' : 'Bleu'}</span>}
          <b className={p.person_id === null ? 'sc-nom--vide' : ''}>{p.name ?? 'Choisir…'}</b>
          <Icon name="chevronRight" size={20} />
        </button>
      ))}
      <div className="sc-rangee">
        {people.length === 2 && (
          <button type="button" className="btn btn--secondary" onClick={() => nommer([people[1], people[0]])}>
            Inverser
          </button>
        )}
        <button type="button" className="btn btn--primary" disabled={people.includes(null)} onClick={onValider}>
          C’est bon
        </button>
      </div>
      {choix !== null && (
        <ChoixNom
          seanceId={c.session_id}
          onClose={() => setChoix(null)}
          onChoisir={(id) => {
            const nouveaux = [...people]
            const ailleurs = nouveaux.indexOf(id)
            if (ailleurs !== -1) nouveaux[ailleurs] = nouveaux[choix]
            nouveaux[choix] = id
            setChoix(null)
            nommer(nouveaux)
          }}
        />
      )}
    </>
  )
}

function Lecture({ clipId, me, version, caches, montrer, supprimer, rafraichir, onBack, onOpen }) {
  const [c, setC] = useState(null)
  const [autres, setAutres] = useState([])
  const [menu, setMenu] = useState(false)
  const [choix, setChoix] = useState(null) // 'quel' | 0 | 1…
  useEffect(() => {
    api.obtenirClip(clipId).then(setC, (e) => montrer(e.message))
  }, [clipId, version, montrer])
  useEffect(() => {
    if (!c) return
    const charger = me.is_coach
      ? api.detailSeance(c.session_id).then((s) => s.clips.filter((x) => !x.to_check))
      : api.mesCombats().then((l) => l.filter((x) => x.session_id === c.session_id))
    charger.then((l) => setAutres(l.filter((x) => x.id !== c.id)), () => {})
  }, [c, me.is_coach])

  if (!c) return <div className="screen sc" aria-busy="true" />
  const people = c.participants.map((p) => p.person_id)

  async function nommer(nouveaux, texte) {
    const avant = people
    try {
      setC(await api.nommer(c.id, nouveaux))
      rafraichir()
      montrer(texte, async () => {
        setC(await api.nommer(c.id, avant))
        rafraichir()
      })
    } catch (e) {
      montrer(e.message)
    }
  }

  async function action(quoi) {
    setMenu(false)
    try {
      if (quoi === 'telecharger') await api.telecharger(c)
      if (quoi === 'partager' && !(await api.partager(c))) await api.telecharger(c)
      if (quoi === 'favori') {
        setC(await api.favori(c.id, !c.favorite))
        montrer(c.favorite ? 'Retiré des favoris' : 'Mis dans les favoris')
        rafraichir()
      }
    } catch (e) {
      montrer(e.message)
    }
  }

  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">{c.title}</strong>
        <button type="button" className="icon-btn" onClick={() => setMenu(true)} aria-label="Plus d'actions">
          <Icon name="moreHorizontal" size={22} />
        </button>
      </div>
      <div className="sc__corps">
        {c.video && <VideoThumb key={c.id} video={c.video} />}
        <div className="sc-fiche">
          <Noms c={c} />
          <span className="sc-meta">
            {api.jour(c.held_on)}
            {c.session_title ? ` · ${c.session_title}` : ''} · combat {c.position}
          </span>
        </div>
        {autres.filter((x) => !caches.has(x.id)).length > 0 && (
          <div className="sc-jour">{me.is_coach ? 'Autres combats de la séance' : 'Vos autres combats ce jour-là'}</div>
        )}
        {autres
          .filter((x) => !caches.has(x.id))
          .map((x) => (
            <LigneCoach key={x.id} c={x} onOpen={onOpen} />
          ))}
      </div>

      {menu && (
        <div className="sc-feuille-fond" onClick={() => setMenu(false)}>
          <div className="sc-feuille" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <button type="button" onClick={() => action('telecharger')}>
              <Icon name="download" size={20} /> Télécharger
            </button>
            <button type="button" onClick={() => action('partager')}>
              <Icon name="partager" size={20} /> Partager… (WhatsApp, etc.)
            </button>
            <button type="button" onClick={() => action('favori')}>
              <Icon name="star" size={20} /> {c.favorite ? 'Retirer des favoris' : 'Mettre dans les favoris'}
            </button>
            {me.is_coach && people.length === 2 && (
              <button
                type="button"
                onClick={() => {
                  setMenu(false)
                  nommer([people[1], people[0]], 'Noms inversés')
                }}
              >
                <Icon name="forward" size={20} /> Inverser les noms
              </button>
            )}
            {me.is_coach && (
              <button
                type="button"
                onClick={() => {
                  setMenu(false)
                  setChoix(people.length === 1 ? 0 : 'quel')
                }}
              >
                <Icon name="edit" size={20} /> Changer un nom
              </button>
            )}
            {me.is_coach && (
              <button
                type="button"
                className="sc-feuille__danger"
                onClick={() => {
                  setMenu(false)
                  supprimer(c.id)
                  onBack()
                }}
              >
                <Icon name="trash" size={20} /> Supprimer ce clip
              </button>
            )}
          </div>
        </div>
      )}
      {choix === 'quel' && (
        <div className="sc-feuille-fond" onClick={() => setChoix(null)}>
          <div className="sc-feuille" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>Quel nom changer ?</h3>
            {c.participants.map((p, i) => (
              <button key={i} type="button" onClick={() => setChoix(i)}>
                {c.participants.length === 2 && <span className={`sc-point sc-point--${i === 0 ? 'rouge' : 'bleu'}`} />}
                {p.name ?? 'Sans nom'}
              </button>
            ))}
          </div>
        </div>
      )}
      {typeof choix === 'number' && (
        <ChoixNom
          seanceId={c.session_id}
          onClose={() => setChoix(null)}
          onChoisir={(id) => {
            const nouveaux = [...people]
            const ailleurs = nouveaux.indexOf(id)
            if (ailleurs !== -1) nouveaux[ailleurs] = nouveaux[choix]
            nouveaux[choix] = id
            setChoix(null)
            nommer(nouveaux, 'Nom changé')
          }}
        />
      )}
    </div>
  )
}
