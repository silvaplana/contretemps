import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

// Modale "Ajouter une vidéo", réutilisée par l'onglet Vidéo (VideoScreen.jsx)
// et par le détail d'une chorégraphie (ChoregraphieDetailScreen.jsx) — même
// composant, donc même upload pour les deux, mutualisé une seule fois côté
// api/videos.js (voir sa note en tête de fichier).
// - Source : fichier existant ou caméra (input file, avec/sans "capture").
// - Durée affichée ("fichier choisi") lue en local (metadata du fichier),
//   juste pour le retour visuel immédiat — la VRAIE durée envoyée au
//   serveur est mesurée à nouveau côté backend une fois le fichier reçu
//   (voir videos/duree.py), pas celle-ci.
// - Chorégraphie : select libre, sauf si `lockedChoregraphieId` est fourni
//   (on est déjà dans le détail d'une chorégraphie, pas besoin de choisir).
export default function AddVideoModal({ choregraphies = [], lockedChoregraphieId, onClose, onAdd }) {
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [choregraphieId, setChoregraphieId] = useState('')
  const [fichier, setFichier] = useState(null)

  function handleFichier(file) {
    if (!file) return
    // URL locale et temporaire, juste pour lire la durée (retour visuel
    // "fichier choisi (mm:ss)") — révoquée juste après, jamais envoyée
    // nulle part (voir api/videos.js : le File brut, `fichier.file`,
    // est ce qui est réellement transmis à l'upload).
    const url = URL.createObjectURL(file)
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.src = url
    probe.onloadedmetadata = () => {
      const total = Math.round(probe.duration || 0)
      const mm = String(Math.floor(total / 60)).padStart(2, '0')
      const ss = String(total % 60).padStart(2, '0')
      setFichier({ nom: file.name, duree: `${mm}:${ss}`, file })
      URL.revokeObjectURL(url)
    }
    if (!titre) setTitre(file.name.replace(/\.[^/.]+$/, ''))
  }

  return (
    <Modal
      title="Ajouter une vidéo"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!titre}
          onClick={() =>
            onAdd({
              titre,
              description,
              choregraphieId: lockedChoregraphieId ?? (choregraphieId || null),
              fichier: fichier?.file ?? null,
            })
          }
        >
          Ajouter
        </button>
      }
    >
      <label>Source de la vidéo</label>
      <div className="video-source-buttons">
        <label className="btn btn--secondary video-source-buttons__btn">
          <Icon name="folder" size={18} />
          Choisir un fichier
          <input
            type="file"
            accept="video/*"
            hidden
            onChange={(e) => handleFichier(e.target.files[0])}
          />
        </label>
        <label className="btn btn--secondary video-source-buttons__btn">
          <Icon name="camera" size={18} />
          Filmer
          <input
            type="file"
            accept="video/*"
            capture="environment"
            hidden
            onChange={(e) => handleFichier(e.target.files[0])}
          />
        </label>
      </div>
      {fichier && (
        <p className="muted">
          <Icon name="check" size={14} /> {fichier.nom} ({fichier.duree})
        </p>
      )}

      <label htmlFor="add-video-titre">Titre</label>
      <input id="add-video-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />

      {lockedChoregraphieId === undefined && (
        <>
          <label htmlFor="add-video-choregraphie">Chorégraphie</label>
          <select
            id="add-video-choregraphie"
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
