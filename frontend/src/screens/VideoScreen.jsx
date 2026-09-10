import { useState } from 'react'
import * as videosApi from '../api/videos.js'
import Badge from '../components/Badge.jsx'
import Icon from '../components/Icon.jsx'
import VideoThumb from '../components/VideoThumb.jsx'
import AddVideoModal from './video/AddVideoModal.jsx'
import EditVideoModal from './video/EditVideoModal.jsx'

// Écran Vidéo (Admin, Professeur, Élève — voir spec/SPEC.md 5.4 et
// images/video.png). Une chorégraphie filmée par entrée, liée au cours
// sélectionné dans l'en-tête. Le "+" est accessible aux 3 rôles.
//
// Données via api/videos.js (voir api/README.md, et sa note sur la
// limite de l'upload réel de fichier — pas encore construite côté
// backend).
export default function VideoScreen({ cours, list, setList, choregraphies, uploaderId }) {
  const [showAdd, setShowAdd] = useState(false)
  const [editingVideo, setEditingVideo] = useState(null)

  if (!cours) return null

  async function remove(id) {
    if (!window.confirm('Supprimer cette vidéo ?')) return
    await videosApi.supprimer(cours.id, id)
    setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((v) => v.id !== id) }))
  }

  async function update(id, patch) {
    const miseAJour = await videosApi.modifier(id, patch)
    setList((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((v) => (v.id === id ? miseAJour : v)),
    }))
  }

  async function add(donnees) {
    const nouvelle = await videosApi.creer(cours.id, donnees, uploaderId)
    // Voir AdminEleves.jsx : updater idempotent, StrictMode (dev) peut
    // l'appliquer 2 fois de suite sur son propre résultat.
    setList((byC) => {
      const liste = byC[cours.id] ?? []
      return liste.some((v) => v.id === nouvelle.id) ? byC : { ...byC, [cours.id]: [...liste, nouvelle] }
    })
  }

  const videos = list[cours.id] ?? []

  return (
    <div className="screen">
      <div className="video-list">
        {videos.map((v) => {
          const choregraphie = choregraphies.find((ch) => ch.id === v.choregraphieId)
          return (
            <div key={v.id} className="video-card">
              <VideoThumb url={v.url} poster={v.poster} titre={v.titre} duree={v.duree} />
              <div className="video-card__body">
                <div>
                  <strong>{v.titre}</strong>
                  {choregraphie && (
                    <Badge className="video-card__tag">
                      <Icon name="music" size={12} /> {choregraphie.nom}
                    </Badge>
                  )}
                  {v.description && <p>{v.description}</p>}
                </div>
                <div className="row-actions">
                  <button
                    type="button"
                    className="icon-btn icon-btn--sm"
                    onClick={() => setEditingVideo(v)}
                    aria-label={`Modifier ${v.titre}`}
                  >
                    <Icon name="edit" size={16} />
                  </button>
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
          onAdd={async (donnees) => {
            await add(donnees)
            setShowAdd(false)
          }}
        />
      )}

      {editingVideo && (
        <EditVideoModal
          video={editingVideo}
          choregraphies={choregraphies}
          onClose={() => setEditingVideo(null)}
          onSave={(patch) => {
            update(editingVideo.id, patch)
            setEditingVideo(null)
          }}
        />
      )}
    </div>
  )
}
