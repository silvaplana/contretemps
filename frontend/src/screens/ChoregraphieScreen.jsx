import { useMemo, useState } from 'react'
import * as choregraphiesApi from '../api/choregraphies.js'
import Modal from '../components/Modal.jsx'
import { isAdmin } from '../data/roles.js'
import ChoixElevesPanel from './choregraphie/ChoixElevesPanel.jsx'
import ChoregraphieDetailScreen from './choregraphie/ChoregraphieDetailScreen.jsx'
import ChoregraphieListScreen from './choregraphie/ChoregraphieListScreen.jsx'

// Écran Chorégraphie (voir spec/SPEC.md §5.3, refonte du 2026-10-03).
// Deux écrans distincts, comme la Messagerie : la liste, puis (au clic) le
// détail en plein écran avec une flèche de retour.
//
// - Tout le monde voit TOUTES les chorégraphies de l'école ; un sélecteur à
//   deux niveaux (discipline, puis niveau) filtre la liste.
// - Les vidéos se gèrent ici (plus d'onglet Vidéo) : chacun peut en ajouter
//   une dans une chorégraphie.
// - Créer, modifier, supprimer une chorégraphie, modifier ou supprimer une
//   vidéo : un admin, ou un professeur du cours de la chorégraphie. Le
//   serveur revérifie tout (backend/src/choregraphies/receiver.py).
//
// `list`/`setList` (toutes les chorégraphies de l'école) viennent de App.jsx.
export default function ChoregraphieScreen({ ecoleId, cours, list, setList, eleves, activeUser }) {
  const [selectedId, setSelectedId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [discipline, setDiscipline] = useState('')
  const [niveau, setNiveau] = useState('')
  const [erreur, setErreur] = useState('')

  const coursParId = useMemo(() => new Map(cours.map((c) => [c.id, c])), [cours])
  const peutGerer = (c) => Boolean(c) && (isAdmin(activeUser) || c.professeurIds.includes(activeUser.id))
  const coursGerables = cours.filter(peutGerer)

  // Sélecteur : les disciplines des cours de l'école, puis les niveaux de
  // la discipline choisie (dans l'ordre des cours, jamais alphabétique).
  const disciplines = [...new Set(cours.map((c) => c.discipline).filter(Boolean))]
  const niveaux = [
    ...new Set(cours.filter((c) => c.discipline === discipline).map((c) => c.niveau).filter(Boolean)),
  ]
  const correspond = (c) =>
    Boolean(c) && (!discipline || c.discipline === discipline) && (!niveau || c.niveau === niveau)
  const filtrees = list.filter((ch) => correspond(coursParId.get(ch.coursId)))

  const selected = list.find((ch) => ch.id === selectedId) ?? null

  function remplacer(choregraphie) {
    setList((liste) => liste.map((ch) => (ch.id === choregraphie.id ? choregraphie : ch)))
  }

  // Un refus du serveur (droits, saison terminée) s'affiche, sans casser l'écran.
  async function tenter(action) {
    setErreur('')
    try {
      return await action()
    } catch (err) {
      setErreur(err.message)
      return undefined
    }
  }

  function majVideos(choregraphieId, transformer) {
    setList((liste) =>
      liste.map((ch) => (ch.id === choregraphieId ? { ...ch, videos: transformer(ch.videos) } : ch)),
    )
  }

  if (selected) {
    const id = selected.id
    return (
      <ChoregraphieDetailScreen
        choregraphie={selected}
        cours={coursParId.get(selected.coursId) ?? null}
        coursGerables={coursGerables}
        tousLesCours={cours}
        eleves={eleves}
        ecoleId={ecoleId}
        utilisateurId={activeUser.id}
        peutModifier={peutGerer(coursParId.get(selected.coursId))}
        erreur={erreur}
        onBack={() => {
          setErreur('')
          setSelectedId(null)
        }}
        onUpdate={(patch) =>
          tenter(async () => remplacer(await choregraphiesApi.modifier(id, patch)))
        }
        onRemove={() =>
          tenter(async () => {
            if (!window.confirm('Supprimer cette chorégraphie et ses vidéos ?')) return
            await choregraphiesApi.supprimer(id)
            setList((liste) => liste.filter((ch) => ch.id !== id))
            setSelectedId(null)
          })
        }
        // AjouterVideo a déjà envoyé le fichier (voir video/AjouterVideo.jsx) :
        // ici, l'envoi devient une vidéo de CETTE chorégraphie.
        creerVideo={(uploadId, meta) => choregraphiesApi.ajouterVideo(id, uploadId, meta)}
        onAddVideo={(video) =>
          // Idempotent : StrictMode (dev) peut l'appliquer 2 fois.
          majVideos(id, (videos) => (videos.some((v) => v.id === video.id) ? videos : [...videos, video]))
        }
        onUpdateVideo={(videoId, patch) =>
          tenter(async () => {
            const maj = await choregraphiesApi.modifierVideo(id, videoId, patch)
            majVideos(id, (videos) => videos.map((v) => (v.id === videoId ? maj : v)))
          })
        }
        onRemoveVideo={(videoId) =>
          tenter(async () => {
            if (!window.confirm('Supprimer cette vidéo ?')) return
            await choregraphiesApi.supprimerVideo(id, videoId)
            majVideos(id, (videos) => videos.filter((v) => v.id !== videoId))
          })
        }
        onMonterVideo={(videoId) =>
          tenter(async () => {
            const ids = selected.videos.map((v) => v.id)
            const i = ids.indexOf(videoId)
            if (i <= 0) return
            ;[ids[i - 1], ids[i]] = [ids[i], ids[i - 1]]
            await choregraphiesApi.reordonnerVideos(id, ids)
            majVideos(id, (videos) => ids.map((vid) => videos.find((v) => v.id === vid)).filter(Boolean))
          })
        }
      />
    )
  }

  return (
    <>
      <ChoregraphieListScreen
        filtres={
          <div className="choregraphie-filtres">
            <select
              aria-label="Discipline"
              value={discipline}
              onChange={(e) => {
                setDiscipline(e.target.value)
                setNiveau('')
              }}
            >
              <option value="">Toutes les disciplines</option>
              {disciplines.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              aria-label="Niveau"
              value={niveau}
              disabled={!discipline}
              onChange={(e) => setNiveau(e.target.value)}
            >
              <option value="">Tous les niveaux</option>
              {niveaux.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        }
        list={filtrees}
        coursParId={coursParId}
        onSelect={setSelectedId}
        onAddNew={() => setShowAdd(true)}
        peutCreer={coursGerables.length > 0}
      />

      {showAdd && coursGerables.length > 0 && (
        <Modal title="Nouvelle chorégraphie" onClose={() => setShowAdd(false)}>
          <NewChoregraphieForm
            coursGerables={coursGerables}
            // Le filtre en cours propose déjà son cours, s'il n'y en a qu'un.
            coursPropose={coursGerables.filter(correspond).length === 1 ? coursGerables.filter(correspond)[0].id : ''}
            eleves={eleves}
            tousLesCours={cours}
            onCreate={async ({ coursId, ...donnees }) => {
              const nouvelle = await choregraphiesApi.creer(coursId, donnees)
              // Idempotent : StrictMode (dev) peut l'appliquer 2 fois.
              setList((liste) => (liste.some((ch) => ch.id === nouvelle.id) ? liste : [...liste, nouvelle]))
              setSelectedId(nouvelle.id)
              setShowAdd(false)
            }}
          />
        </Modal>
      )}
    </>
  )
}

function NewChoregraphieForm({ coursGerables, coursPropose, eleves, tousLesCours, onCreate }) {
  const [nom, setNom] = useState('')
  // Une chorégraphie est associée à un cours dès sa création (spec §5.3).
  const [coursId, setCoursId] = useState(coursPropose)
  const [eleveIds, setEleveIds] = useState([])
  const [choixEleves, setChoixEleves] = useState(false)
  const [costume, setCostume] = useState('')
  const [horaireRepetition, setHoraireRepetition] = useState('')
  const [erreur, setErreur] = useState('')
  // Garde-fou contre un double-appel (voir AdminEleves.jsx).
  const [enCours, setEnCours] = useState(false)

  async function valider() {
    if (enCours) return
    setEnCours(true)
    setErreur('')
    try {
      await onCreate({ coursId: Number(coursId), nom, eleveIds, costume, horaireRepetition })
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <>
      <label htmlFor="new-choregraphie-nom">Nom</label>
      <input id="new-choregraphie-nom" value={nom} onChange={(e) => setNom(e.target.value)} />

      <label htmlFor="new-choregraphie-cours">Cours</label>
      <select id="new-choregraphie-cours" value={coursId} onChange={(e) => setCoursId(e.target.value)}>
        <option value="">Choisir un cours…</option>
        {coursGerables.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nom}
          </option>
        ))}
      </select>

      <label>Élèves</label>
      <button type="button" className="btn btn--secondary" onClick={() => setChoixEleves(true)}>
        {eleveIds.length === 0
          ? 'Choisir des élèves'
          : `${eleveIds.length} élève${eleveIds.length > 1 ? 's' : ''} choisi${eleveIds.length > 1 ? 's' : ''}`}
      </button>

      <label htmlFor="new-choregraphie-costume">Costume (optionnel)</label>
      <textarea
        id="new-choregraphie-costume"
        className="modal-textarea"
        rows={2}
        value={costume}
        onChange={(e) => setCostume(e.target.value)}
      />

      <label htmlFor="new-choregraphie-horaire">Horaire de répétition (optionnel)</label>
      <input
        id="new-choregraphie-horaire"
        value={horaireRepetition}
        onChange={(e) => setHoraireRepetition(e.target.value)}
      />

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button
        type="button"
        className="btn btn--primary btn--block"
        disabled={!nom || !coursId || enCours}
        onClick={valider}
      >
        Créer
      </button>

      {choixEleves && (
        <ChoixElevesPanel
          eleves={eleves}
          cours={tousLesCours}
          coursInitial={coursId ? Number(coursId) : null}
          choisis={eleveIds}
          onValider={(ids) => {
            setEleveIds(ids)
            setChoixEleves(false)
          }}
          onClose={() => setChoixEleves(false)}
        />
      )}
    </>
  )
}
