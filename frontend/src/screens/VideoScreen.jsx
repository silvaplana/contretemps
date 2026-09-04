import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'

// Écran Vidéo (Admin, Professeur, Parent — voir spec/SPEC.md 5.4 et
// images/video.png). Une chorégraphie filmée par entrée, liée au cours
// sélectionné dans l'en-tête. Le "+" est accessible aux 3 rôles.
export default function VideoScreen({ cours, list, setList }) {
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  function remove(id) {
    if (window.confirm('Supprimer cette vidéo ?')) {
      setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((v) => v.id !== id) }))
    }
  }

  function add(titre, description) {
    const nouvelle = {
      id: crypto.randomUUID(),
      titre,
      description,
      duree: '00:00',
      datePublication: new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    }
    setList((byC) => ({ ...byC, [cours.id]: [...(byC[cours.id] ?? []), nouvelle] }))
  }

  const videos = list[cours.id] ?? []

  return (
    <div className="screen">
      <div className="video-list">
        {videos.map((v) => (
          <div key={v.id} className="video-card">
            <div className="video-card__thumb">
              <button type="button" className="video-card__play" aria-label={`Lire ${v.titre}`}>
                <Icon name="play" size={22} />
              </button>
              <span className="video-card__duree">{v.duree}</span>
            </div>
            <div className="video-card__body">
              <div>
                <strong>{v.titre}</strong>
                <p className="muted">Publié le {v.datePublication}</p>
                {v.description && <p>{v.description}</p>}
              </div>
              <button
                type="button"
                className="icon-btn icon-btn--sm"
                onClick={() => remove(v.id)}
                aria-label="Supprimer la vidéo"
              >
                <Icon name="trash" size={16} />
              </button>
            </div>
          </div>
        ))}
        {videos.length === 0 && <p className="muted" style={{ padding: '0 16px' }}>Aucune vidéo pour ce cours.</p>}
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter une vidéo">
        <Icon name="plus" size={24} />
      </button>

      {showAdd && (
        <AddVideoModal
          onClose={() => setShowAdd(false)}
          onAdd={(titre, description) => {
            add(titre, description)
            setShowAdd(false)
          }}
        />
      )}
    </div>
  )
}

function AddVideoModal({ onClose, onAdd }) {
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')

  return (
    <Modal
      title="Ajouter une vidéo"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!titre}
          onClick={() => onAdd(titre, description)}
        >
          Ajouter
        </button>
      }
    >
      <label htmlFor="add-video-titre">Titre</label>
      <input id="add-video-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
      <label htmlFor="add-video-desc">Description (optionnelle)</label>
      <textarea
        id="add-video-desc"
        className="modal-textarea"
        rows={3}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
    </Modal>
  )
}
