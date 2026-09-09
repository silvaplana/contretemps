import { useState } from 'react'
import Modal from '../../components/Modal.jsx'

// Modale "Modifier la vidéo", réutilisée par l'onglet Vidéo (VideoScreen.jsx)
// et par le détail d'une chorégraphie (ChoregraphieDetailScreen.jsx) — même
// principe que AddVideoModal.jsx, y compris `lockedChoregraphieId` (verrouille
// le select quand on édite déjà depuis le détail d'une chorégraphie — pas
// besoin de choisir, elle y est forcément déjà taguée ; le (dé)taguer vers
// une AUTRE chorégraphie depuis cet écran reste le rôle de "Choisir des
// vidéos", pas de celui-ci). Depuis l'onglet Vidéo (pas de verrou), on peut
// choisir/changer la chorégraphie liée (demande utilisateur).
export default function EditVideoModal({ video, choregraphies = [], lockedChoregraphieId, onClose, onSave }) {
  const [titre, setTitre] = useState(video.titre)
  const [description, setDescription] = useState(video.description)
  const [choregraphieId, setChoregraphieId] = useState(video.choregraphieId ?? '')

  return (
    <Modal
      title="Modifier la vidéo"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!titre}
          onClick={() =>
            onSave({
              titre,
              description,
              choregraphieId: lockedChoregraphieId ?? (choregraphieId || null),
            })
          }
        >
          Enregistrer
        </button>
      }
    >
      <label htmlFor="edit-video-titre">Titre</label>
      <input id="edit-video-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />

      {lockedChoregraphieId === undefined && (
        <>
          <label htmlFor="edit-video-choregraphie">Chorégraphie</label>
          <select
            id="edit-video-choregraphie"
            value={choregraphieId}
            onChange={(e) => setChoregraphieId(e.target.value)}
          >
            <option value="">Aucune</option>
            {choregraphies.map((ch) => (
              <option key={ch.id} value={ch.id}>
                {ch.nom}
              </option>
            ))}
          </select>
        </>
      )}

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
