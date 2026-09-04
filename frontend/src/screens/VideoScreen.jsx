import { useState } from 'react'
import Badge from '../components/Badge.jsx'
import Icon from '../components/Icon.jsx'
import AddVideoModal from './video/AddVideoModal.jsx'

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

  function add({ titre, description, duree, url, choregraphieId }) {
    const nouvelle = {
      id: crypto.randomUUID(),
      titre,
      description,
      duree: duree || '00:00',
      url: url || null,
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
                {v.url ? (
                  <video className="video-card__player" src={v.url} controls preload="metadata" />
                ) : (
                  <>
                    <button type="button" className="video-card__play" aria-label={`Lire ${v.titre}`} disabled>
                      <Icon name="play" size={22} />
                    </button>
                    <span className="video-card__duree">{v.duree}</span>
                  </>
                )}
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
