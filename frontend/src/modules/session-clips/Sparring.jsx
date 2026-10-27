import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
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
import './sparring.css'

// Sparring (spec/modules/video-combats.md §6, maquette validée
// spec/maquettes/sparring.html). Un membre n'a que « Mes combats » ; un coach
// a aussi Séances et À vérifier. Une séance ouverte et un clip lu s'affichent
// en plein écran avec la flèche de retour, comme une chorégraphie.
//
// Le + filme un combat à la main (FilmerCombat) ; la séance entière filmée
// en continu viendra avec l'enregistreur (étape 3).

const ANNULER_MS = 10000

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
      if (m.is_coach) setOnglet('seances')
    }, () => setMe({ person_id: null, is_coach: false }))
  }, [])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const montrer = useCallback((texte, annuler) => {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), annuler ? ANNULER_MS : 3000)
  }, [])

  // Supprimer : le clip disparaît tout de suite, part vraiment au bout de 10 s.
  const [caches, setCaches] = useState(new Set())
  const supprimer = useCallback(
    (clipId) => {
      setCaches((c) => new Set(c).add(clipId))
      const retard = setTimeout(() => {
        api.supprimer(clipId).then(rafraichir, (e) => montrer(e.message))
      }, ANNULER_MS)
      montrer('Clip supprimé', () => {
        clearTimeout(retard)
        setCaches((c) => {
          const n = new Set(c)
          n.delete(clipId)
          return n
        })
      })
    },
    [montrer, rafraichir],
  )

  if (!me) return <div className="screen sc" aria-busy="true" />

  const contexte = { me, ecoleId, cours, version, rafraichir, montrer, supprimer, caches }

  let ecran
  if (ouvert?.clipId) {
    ecran = (
      <Lecture
        {...contexte}
        clipId={ouvert.clipId}
        onBack={() => setOuvert(ouvert.retour)}
        onOpen={(id) => setOuvert({ clipId: id, retour: ouvert.retour })}
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
        {me.is_coach && <Onglets onglet={onglet} onChange={setOnglet} version={version} />}
        <div className="sc__corps">
          {onglet === 'mes' && <MesCombats {...contexte} onOpen={(id) => setOuvert({ clipId: id, retour: null })} />}
          {onglet === 'seances' && <Seances {...contexte} onOpen={(id) => setOuvert({ seanceId: id })} />}
          {onglet === 'verifier' && <AVerifier {...contexte} />}
        </div>
      </div>
    )
  }

  return (
    <>
      {ecran}
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

function Onglets({ onglet, onChange, version }) {
  const [n, setN] = useState(0)
  useEffect(() => {
    api.aVerifier().then((l) => setN(l.length), () => {})
  }, [version])
  const onglets = [
    ['mes', 'Mes combats'],
    ['seances', 'Séances'],
    ['verifier', 'À vérifier'],
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
            {cle === 'verifier' && n > 0 && <span className="sc-pastille">{n}</span>}
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

function MesCombats({ me, version, caches, onOpen }) {
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
        <button type="button" className="sc-clip" onClick={() => onOpen(c.id)}>
          <Vignette video={c.video} />
          <span>
            <strong>{adversaires(c, me)}</strong>
            <span className="sc-meta">
              Combat {c.position}
              {duree(c.video) && ` · ${duree(c.video)}`}
            </span>
          </span>
        </button>
      </div>
    )
  })
}

function LigneCoach({ c, onOpen }) {
  return (
    <button type="button" className="sc-clip" onClick={() => onOpen(c.id)}>
      <Vignette video={c.video} />
      <span>
        <strong>{c.title}</strong>
        <span className="sc-meta">
          Combat {c.position}
          {c.to_check && <span className="sc-chip sc-chip--warn">À vérifier</span>}
        </span>
      </span>
    </button>
  )
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
  if (s.status === 'processing') return <span className="sc-chip sc-chip--info">Clips prêts demain matin</span>
  if (s.status === 'failed') return <span className="sc-chip sc-chip--warn">Découpe impossible</span>
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

  return (
    <>
      {liste?.length === 0 && (
        <p className="sc-vide">Aucune séance filmée. Le + filme un combat avec le téléphone.</p>
      )}
      {liste?.map((s) => {
        const prete = s.status === 'ready'
        return (
          <button
            key={s.id}
            type="button"
            className="sc-carte"
            aria-disabled={!prete}
            onClick={() => prete && onOpen(s.id)}
          >
            {prete && s.previews.length ? (
              <span className="sc-couverture">
                {s.previews.map((v, i) => (
                  <span key={v.id} className={i === 0 ? 'sc-couverture__grande' : ''}>
                    {v.poster && <img src={v.poster} alt="" />}
                  </span>
                ))}
              </span>
            ) : (
              <span className="sc-couverture sc-couverture--attente">
                {s.status === 'uploading' ? 'La vidéo arrive…' : s.status === 'failed' ? 'Vidéo illisible' : 'Découpe cette nuit'}
              </span>
            )}
            <span className="sc-carte__info">
              <strong>
                {api.jour(s.held_on)}
                {s.title ? ` · ${s.title}` : ''}
              </strong>
              <span className="sc-meta">
                <EtatSeance s={s} />
              </span>
            </span>
          </button>
        )
      })}
      <FilmerCombat ecoleId={ecoleId} onEnvoye={rafraichir} montrer={montrer} />
    </>
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

function DossierSeance({ seanceId, version, caches, onBack, onOpen, montrer }) {
  const [s, setS] = useState(null)
  useEffect(() => {
    api.detailSeance(seanceId).then(setS, (e) => montrer(e.message))
  }, [seanceId, version, montrer])
  return (
    <div className="screen sc">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux séances">
          <Icon name="chevronLeft" size={22} />
        </button>
        <strong className="sc__titre">{s ? `${api.jour(s.held_on)}${s.title ? ` · ${s.title}` : ''}` : ''}</strong>
      </div>
      <div className="sc__corps">
        {s?.attendees.length > 0 && (
          <p className="sc-meta">Présents reconnus : {s.attendees.map((p) => p.name).join(', ')}</p>
        )}
        {s?.clips
          .filter((c) => !caches.has(c.id))
          .map((c) => (
            <LigneCoach key={c.id} c={c} onOpen={onOpen} />
          ))}
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
  const [choix, setChoix] = useState(null) // place à nommer
  useEffect(() => {
    api.aVerifier().then(setFile, (e) => montrer(e.message))
  }, [version, montrer])
  if (!file) return null
  const visibles = file.filter((c) => !caches.has(c.id))
  if (!visibles.length) return <p className="sc-vide">Tout est vérifié. Les clips sont dans « Mes combats » de chaque membre.</p>
  const c = visibles[0]
  const people = c.participants.map((p) => p.person_id)

  async function nommer(nouveaux) {
    try {
      const maj = await api.nommer(c.id, nouveaux)
      setFile((f) => f.map((x) => (x.id === maj.id ? maj : x)))
    } catch (e) {
      montrer(e.message)
    }
  }

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
        <button type="button" className="btn btn--primary" disabled={people.includes(null)} onClick={valider}>
          C’est bon
        </button>
      </div>
      <button type="button" className="sc-lien" onClick={() => supprimer(c.id)}>
        Supprimer ce clip
      </button>
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
