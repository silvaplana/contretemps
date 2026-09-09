import { useState } from 'react'
import Modal from '../../components/Modal.jsx'

// Modale "Modifier la vidéo", réutilisée par l'onglet Vidéo (VideoScreen.jsx)
// et par le détail d'une chorégraphie (ChoregraphieDetailScreen.jsx) — même
// principe que AddVideoModal.jsx. Ne touche ni au fichier ni à la
// chorégraphie liée, seulement titre/description (voir demande utilisateur :
// pouvoir éditer le nom et la description dans les deux écrans).
export default function EditVideoModal({ video, onClose, onSave }) {
  const [titre, setTitre] = useState(video.titre)
  const [description, setDescription] = useState(video.description)

  return (
    <Modal
      title="Modifier la vidéo"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!titre}
          onClick={() => onSave({ titre, description })}
        >
          Enregistrer
        </button>
      }
    >
      <label htmlFor="edit-video-titre">Titre</label>
      <input id="edit-video-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />
      <label htmlFor="edit-video-desc">Description (optionnelle)</label>
      <textarea
        id="edit-video-desc"
        className="modal-textarea"
        rows={3}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
    </Modal>
  )
}
