import { useState } from 'react'
import Modal from '../components/Modal.jsx'
import ChoregraphieDetailScreen from './choregraphie/ChoregraphieDetailScreen.jsx'
import ChoregraphieListScreen from './choregraphie/ChoregraphieListScreen.jsx'

// Écran Chorégraphie (Admin, Professeur, Parent — voir spec/SPEC.md 5.3 et
// images/choregraphie.png). Deux écrans distincts, comme la Messagerie : la
// liste des chorégraphies du cours, puis (au clic) le détail en plein écran
// avec une flèche de retour — jamais les deux affichés en même temps.
export default function ChoregraphieScreen({ cours, list, setList, eleves }) {
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

  function removeVideo(id, index) {
    update(id, { videos: selected.videos.filter((_, i) => i !== index) })
  }

  function addVideo(id, titre) {
    update(id, { videos: [...selected.videos, { titre, url: '#' }] })
  }

  function removeChoregraphie(id) {
    if (!window.confirm('Supprimer cette chorégraphie ?')) return
    setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((ch) => ch.id !== id) }))
    setSelectedId(null)
  }

  if (selected) {
    return (
      <ChoregraphieDetailScreen
        choregraphie={selected}
        eleves={eleves}
        onBack={() => setSelectedId(null)}
        onUpdate={(patch) => update(selected.id, patch)}
        onRemoveVideo={(index) => removeVideo(selected.id, index)}
        onAddVideo={(titre) => addVideo(selected.id, titre)}
        onRemove={() => removeChoregraphie(selected.id)}
      />
    )
  }

  return (
    <>
      <ChoregraphieListScreen list={list} onSelect={setSelectedId} onAddNew={() => setShowAdd(true)} />

      {showAdd && (
        <Modal title="Nouvelle chorégraphie" onClose={() => setShowAdd(false)}>
          <NewChoregraphieForm
            onCreate={(nom) => {
              const nouvelle = {
                id: crypto.randomUUID(),
                nom,
                eleveIds: [],
                costume: '',
                horaireRepetition: '',
                videos: [],
              }
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

function NewChoregraphieForm({ onCreate }) {
  const [nom, setNom] = useState('')
  return (
    <>
      <label htmlFor="new-choregraphie-nom">Nom</label>
      <input id="new-choregraphie-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <button
        type="button"
        className="btn btn--primary btn--block"
        disabled={!nom}
        onClick={() => onCreate(nom)}
      >
        Créer
      </button>
    </>
  )
}
