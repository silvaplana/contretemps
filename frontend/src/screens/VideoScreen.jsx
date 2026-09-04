import { useState } from 'react'
import Badge from '../components/Badge.jsx'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'

// Écran Vidéo (Admin, Professeur, Parent — voir spec/SPEC.md 5.4 et
// images/video.png). Une chorégraphie filmée par entrée, liée au cours
// sélectionné dans l'en-tête. Le "+" est accessible aux 3 rôles.
export default function VideoScreen({ cours, list, setList, choregraphies }) {
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  function remove(id) {
    if (window.confirm('Supprimer cette vidéo ?')) {
      setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((v) => v.id !== id) }))
    }
  }

  function add({ titre, description, duree, choregraphieId }) {
    const nouvelle = {
      id: crypto.randomUUID(),
      titre,
      description,
      duree: duree || '00:00',
      choregraphieId: choregraphieId || null,
      datePublication: new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' }),
    }
    setList((byC) => ({ ...byC, [cours.id]: [...(byC[cours.id] ?? []), nouvelle] }))
  }

  const videos = list[cours.id] ?? []

  return (
    <div className="screen">
      <div className="video-list">
        {videos.map((v) => {
          const choregraphie = choregraphies.find((ch) => ch.id === v.choregraphieId)
          return (
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
                  {choregraphie && (
                    <Badge className="video-card__tag">
                      <Icon name="music" size={12} /> {choregraphie.nom}
                    </Badge>
                  )}
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
          )
        })}
        {videos.length === 0 && <p className="muted" style={{ padding: '0 16px' }}>Aucune vidéo pour ce cours.</p>}
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter une vidéo">
        <Icon name="plus" size={24} />
      </button>

      {showAdd && (
        <AddVideoModal
          choregraphies={choregraphies}
          onClose={() => setShowAdd(false)}
          onAdd={(donnees) => {
            add(donnees)
            setShowAdd(false)
          }}
        />
      )}
    </div>
  )
}

function AddVideoModal({ choregraphies, onClose, onAdd }) {
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [choregraphieId, setChoregraphieId] = useState('')
  const [fichier, setFichier] = useState(null)

  // Lit la vidéo choisie (fichier ou caméra) juste pour en extraire la durée
  // réelle — rien n'est envoyé nulle part, tout reste local au navigateur.
  function handleFichier(file) {
    if (!file) return
    const url = URL.createObjectURL(file)
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.src = url
    probe.onloadedmetadata = () => {
      const total = Math.round(probe.duration || 0)
      const mm = String(Math.floor(total / 60)).padStart(2, '0')
      const ss = String(total % 60).padStart(2, '0')
      setFichier({ nom: file.name, duree: `${mm}:${ss}` })
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
            onAdd({ titre, description, duree: fichier?.duree, choregraphieId: choregraphieId || null })
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
