import { useState } from 'react'
import * as choregraphiesApi from '../api/choregraphies.js'
import * as videosApi from '../api/videos.js'
import Modal from '../components/Modal.jsx'
import ChoregraphieDetailScreen from './choregraphie/ChoregraphieDetailScreen.jsx'
import ChoregraphieListScreen from './choregraphie/ChoregraphieListScreen.jsx'

// Écran Chorégraphie (Admin, Professeur, Élève — voir spec/SPEC.md 5.3 et
// images/choregraphie.png). Deux écrans distincts, comme la Messagerie : la
// liste des chorégraphies du cours, puis (au clic) le détail en plein écran
// avec une flèche de retour — jamais les deux affichés en même temps.
//
// Chorégraphies (nom/costume/horaire/élèves participants) via
// api/choregraphies.js, vidéos via api/videos.js (voir api/README.md) —
// `list`/`setList`/`videos`/`setVideos` viennent de App.jsx.
export default function ChoregraphieScreen({
  cours,
  list,
  setList,
  eleves,
  videos,
  setVideos,
  uploaderId,
  peutModifier,
}) {
  const [selectedId, setSelectedId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  const selected = list.find((ch) => ch.id === selectedId) ?? null

  function remplacer(choregraphieMiseAJour) {
    setList((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((ch) =>
        ch.id === choregraphieMiseAJour.id ? choregraphieMiseAJour : ch,
      ),
    }))
  }

  async function update(id, patch) {
    remplacer(await choregraphiesApi.modifier(id, patch))
  }

  async function removeChoregraphie(id) {
    if (!window.confirm('Supprimer cette chorégraphie ?')) return
    await choregraphiesApi.supprimer(cours.id, id)
    setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((ch) => ch.id !== id) }))
    setSelectedId(null)
  }

  // Gestion des vidéos depuis le détail d'une chorégraphie : mêmes données
  // que l'onglet Vidéo (api/videos.js), juste manipulées depuis cet écran.
  async function addVideo(donnees) {
    const nouvelle = await videosApi.creer(cours.id, donnees, uploaderId)
    // Voir AdminEleves.jsx : updater idempotent, StrictMode (dev) peut
    // l'appliquer 2 fois de suite sur son propre résultat.
    setVideos((byC) => {
      const liste = byC[cours.id] ?? []
      return liste.some((v) => v.id === nouvelle.id) ? byC : { ...byC, [cours.id]: [...liste, nouvelle] }
    })
  }

  async function updateVideo(id, patch) {
    const miseAJour = await videosApi.modifier(id, patch)
    setVideos((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((v) => (v.id === id ? miseAJour : v)),
    }))
  }

  async function removeVideo(id) {
    if (!window.confirm('Supprimer cette vidéo ?')) return
    await videosApi.supprimer(cours.id, id)
    setVideos((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((v) => v.id !== id) }))
  }

  async function toggleVideoTag(id, choregraphieId) {
    const video = videos.find((v) => v.id === id)
    const nouvelleValeur = video?.choregraphieId === choregraphieId ? null : choregraphieId
    const miseAJour = await videosApi.modifier(id, { choregraphieId: nouvelleValeur })
    setVideos((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((v) => (v.id === id ? miseAJour : v)),
    }))
  }

  if (selected) {
    return (
      <ChoregraphieDetailScreen
        choregraphie={selected}
        eleves={eleves}
        peutModifier={peutModifier}
        // Élèves proposés pour la choré : ceux inscrits à ce cours (voir
        // eleves[].coursIds), pas toute la base élèves de l'école.
        roster={eleves.filter((el) => el.coursIds.includes(cours.id))}
        // Toutes les vidéos du cours : le détail filtre lui-même celles
        // taguées à cette chorégraphie, et permet d'en (dé)taguer d'autres.
        videosDuCours={videos}
        onBack={() => setSelectedId(null)}
        onUpdate={(patch) => update(selected.id, patch)}
        onRemove={() => removeChoregraphie(selected.id)}
        onAddVideo={(donnees) => addVideo({ ...donnees, choregraphieId: selected.id })}
        onUpdateVideo={updateVideo}
        onRemoveVideo={removeVideo}
        onToggleVideoTag={(id) => toggleVideoTag(id, selected.id)}
      />
    )
  }

  return (
    <>
      <ChoregraphieListScreen
        list={list}
        onSelect={setSelectedId}
        onAddNew={() => setShowAdd(true)}
        peutModifier={peutModifier}
      />

      {showAdd && peutModifier && (
        <Modal title="Nouvelle chorégraphie" onClose={() => setShowAdd(false)}>
          <NewChoregraphieForm
            // Les élèves proposés sont ceux inscrits à ce cours (voir
            // eleves[].coursIds) — pas toute la base élèves de l'école.
            roster={eleves.filter((el) => el.coursIds.includes(cours.id))}
            onCreate={async (donnees) => {
              const nouvelle = await choregraphiesApi.creer(cours.id, donnees)
              // Voir AdminEleves.jsx : updater idempotent, StrictMode
              // (dev) peut l'appliquer 2 fois de suite sur son résultat.
              setList((byC) => {
                const liste = byC[cours.id] ?? []
                return liste.some((ch) => ch.id === nouvelle.id)
                  ? byC
                  : { ...byC, [cours.id]: [...liste, nouvelle] }
              })
              setSelectedId(nouvelle.id)
              setShowAdd(false)
            }}
          />
        </Modal>
      )}
    </>
  )
}

function NewChoregraphieForm({ roster, onCreate }) {
  const [nom, setNom] = useState('')
  const [eleveIds, setEleveIds] = useState([])
  const [costume, setCostume] = useState('')
  const [horaireRepetition, setHoraireRepetition] = useState('')
  // Garde-fou contre un double-appel (voir AdminEleves.jsx) : l'appel est
  // async désormais.
  const [enCours, setEnCours] = useState(false)

  function toggleEleve(id) {
    setEleveIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]))
  }

  async function valider() {
    if (enCours) return
    setEnCours(true)
    await onCreate({ nom, eleveIds, costume, horaireRepetition })
  }

  return (
    <>
      <label htmlFor="new-choregraphie-nom">Nom</label>
      <input id="new-choregraphie-nom" value={nom} onChange={(e) => setNom(e.target.value)} />

      <label>Élèves du cours</label>
      <div className="checkbox-list">
        {roster.map((el) => (
          <label key={el.id} className="checkbox-list__item">
            <input
              type="checkbox"
              checked={eleveIds.includes(el.id)}
              onChange={() => toggleEleve(el.id)}
            />
            {el.prenom} {el.nom}
          </label>
        ))}
        {roster.length === 0 && <p className="muted">Aucun élève inscrit à ce cours.</p>}
      </div>

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

      <button type="button" className="btn btn--primary btn--block" disabled={!nom || enCours} onClick={valider}>
        Créer
      </button>
    </>
  )
}
