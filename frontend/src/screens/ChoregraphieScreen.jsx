import { useState } from 'react'
import Modal from '../components/Modal.jsx'
import ChoregraphieDetailScreen from './choregraphie/ChoregraphieDetailScreen.jsx'
import ChoregraphieListScreen from './choregraphie/ChoregraphieListScreen.jsx'

// Écran Chorégraphie (Admin, Professeur, Parent — voir spec/SPEC.md 5.3 et
// images/choregraphie.png). Deux écrans distincts, comme la Messagerie : la
// liste des chorégraphies du cours, puis (au clic) le détail en plein écran
// avec une flèche de retour — jamais les deux affichés en même temps.
export default function ChoregraphieScreen({ cours, list, setList, eleves, videos, setVideos }) {
  const [selectedId, setSelectedId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  const selected = list.find((ch) => ch.id === selectedId) ?? null

  function update(id, patch) {
    setList((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((ch) => (ch.id === id ? { ...ch, ...patch } : ch)),
    }))
  }

  function removeChoregraphie(id) {
    if (!window.confirm('Supprimer cette chorégraphie ?')) return
    setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((ch) => ch.id !== id) }))
    setSelectedId(null)
  }

  // Gestion des vidéos depuis le détail d'une chorégraphie : mêmes données
  // que l'onglet Vidéo (videosParCours), juste manipulées depuis cet écran.
  function addVideo(donnees) {
    const nouvelle = {
      id: crypto.randomUUID(),
      titre: donnees.titre,
      description: donnees.description,
      duree: donnees.duree || '00:00',
      choregraphieId: donnees.choregraphieId ?? null,
      datePublication: new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    }
    setVideos((byC) => ({ ...byC, [cours.id]: [...(byC[cours.id] ?? []), nouvelle] }))
  }

  function updateVideo(id, patch) {
    setVideos((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((v) => (v.id === id ? { ...v, ...patch } : v)),
    }))
  }

  function removeVideo(id) {
    if (!window.confirm('Supprimer cette vidéo ?')) return
    setVideos((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((v) => v.id !== id) }))
  }

  function toggleVideoTag(id, choregraphieId) {
    setVideos((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((v) =>
        v.id === id
          ? { ...v, choregraphieId: v.choregraphieId === choregraphieId ? null : choregraphieId }
          : v,
      ),
    }))
  }

  if (selected) {
    return (
      <ChoregraphieDetailScreen
        choregraphie={selected}
        eleves={eleves}
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
      <ChoregraphieListScreen list={list} onSelect={setSelectedId} onAddNew={() => setShowAdd(true)} />

      {showAdd && (
        <Modal title="Nouvelle chorégraphie" onClose={() => setShowAdd(false)}>
          <NewChoregraphieForm
            // Les élèves proposés sont ceux inscrits à ce cours (voir
            // eleves[].coursIds) — pas toute la base élèves de l'école.
            roster={eleves.filter((el) => el.coursIds.includes(cours.id))}
            onCreate={(donnees) => {
              const nouvelle = { id: crypto.randomUUID(), ...donnees }
              setList((byC) => ({ ...byC, [cours.id]: [...(byC[cours.id] ?? []), nouvelle] }))
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

  function toggleEleve(id) {
    setEleveIds((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]))
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

      <button
        type="button"
        className="btn btn--primary btn--block"
        disabled={!nom}
        onClick={() => onCreate({ nom, eleveIds, costume, horaireRepetition })}
      >
        Créer
      </button>
    </>
  )
}
