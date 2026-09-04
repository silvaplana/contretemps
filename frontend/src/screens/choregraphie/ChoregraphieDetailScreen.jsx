import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import VideoThumb from '../../components/VideoThumb.jsx'
import AddVideoModal from '../video/AddVideoModal.jsx'

// Écran 2/2 de Chorégraphie : le détail d'UNE chorégraphie, plein écran,
// avec une flèche de retour vers ChoregraphieListScreen — même principe que
// la Messagerie. Consultation par défaut ; le bouton stylo (à côté de la
// poubelle) bascule en mode édition pour Admin/Professeur (voir droits,
// spec/SPEC.md section 3). En édition, les vidéos de la chorégraphie
// peuvent aussi être choisies parmi celles du cours, ajoutées, éditées ou
// supprimées — pas seulement consultées.
export default function ChoregraphieDetailScreen({
  choregraphie,
  eleves,
  roster,
  videosDuCours,
  onBack,
  onUpdate,
  onRemove,
  onAddVideo,
  onUpdateVideo,
  onRemoveVideo,
  onToggleVideoTag,
}) {
  const [editing, setEditing] = useState(false)
  const [showChoose, setShowChoose] = useState(false)
  const [showAddVideo, setShowAddVideo] = useState(false)
  const [editingVideo, setEditingVideo] = useState(null)
  const [showChooseEleves, setShowChooseEleves] = useState(false)

  const videos = videosDuCours.filter((v) => v.choregraphieId === choregraphie.id)

  function toggleEleve(id) {
    const dansLaListe = choregraphie.eleveIds.includes(id)
    onUpdate({
      eleveIds: dansLaListe
        ? choregraphie.eleveIds.filter((x) => x !== id)
        : [...choregraphie.eleveIds, id],
    })
  }

  return (
    <div className="screen choregraphie-detail-screen">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux chorégraphies">
          <Icon name="chevronLeft" size={22} />
        </button>

        {editing ? (
          <EditableText value={choregraphie.nom} onChange={(v) => onUpdate({ nom: v })} />
        ) : (
          <strong className="choregraphie-detail-screen__title">{choregraphie.nom}</strong>
        )}

        <button
          type="button"
          className={`icon-btn ${editing ? 'icon-btn--accent' : ''}`}
          onClick={() => setEditing((e) => !e)}
          aria-label={editing ? 'Terminer la modification' : 'Modifier la chorégraphie'}
        >
          <Icon name={editing ? 'check' : 'edit'} size={18} />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn--danger"
          onClick={onRemove}
          aria-label="Supprimer la chorégraphie"
        >
          <Icon name="trash" size={18} />
        </button>
      </div>

      <div className="choregraphie-detail">
        <section>
          <h3>
            <Icon name="users" size={16} /> Élèves
          </h3>
          <div className="badge-list">
            {choregraphie.eleveIds.map((id) => {
              const el = eleves.find((e) => e.id === id)
              if (!el) return null
              return editing ? (
                <span key={id} className="removable-badge">
                  <Badge>{el.prenom}</Badge>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => toggleEleve(id)}
                    aria-label={`Retirer ${el.prenom}`}
                  >
                    <Icon name="x" size={12} />
                  </button>
                </span>
              ) : (
                <Badge key={id}>{el.prenom}</Badge>
              )
            })}
          </div>
          {editing && (
            <button
              type="button"
              className="btn btn--secondary choregraphie-detail__eleves-btn"
              onClick={() => setShowChooseEleves(true)}
            >
              <Icon name="folder" size={16} /> Élèves
            </button>
          )}
        </section>

        <section>
          <h3>Costume</h3>
          {editing ? (
            <textarea
              className="modal-textarea"
              rows={2}
              value={choregraphie.costume}
              onChange={(e) => onUpdate({ costume: e.target.value })}
            />
          ) : (
            <p>{choregraphie.costume || <span className="muted">—</span>}</p>
          )}
        </section>

        <section>
          <h3>Horaire de répétition</h3>
          {editing ? (
            <input
              className="field-input"
              value={choregraphie.horaireRepetition}
              onChange={(e) => onUpdate({ horaireRepetition: e.target.value })}
            />
          ) : (
            <p>{choregraphie.horaireRepetition || <span className="muted">—</span>}</p>
          )}
        </section>

        <section>
          <h3>
            <Icon name="video" size={16} /> Vidéos
          </h3>
          {videos.length > 0 ? (
            <div className="video-list video-list--nested">
              {videos.map((v) => (
                <div key={v.id} className="video-card">
                  <VideoThumb url={v.url} titre={v.titre} duree={v.duree} />
                  <div className="video-card__body">
                    <strong>{v.titre}</strong>
                    {editing && (
                      <div className="row-actions">
                        <button
                          type="button"
                          className="icon-btn icon-btn--sm"
                          onClick={() => setEditingVideo(v)}
                          aria-label={`Modifier ${v.titre}`}
                        >
                          <Icon name="edit" size={14} />
                        </button>
                        <button
                          type="button"
                          className="icon-btn icon-btn--sm icon-btn--danger"
                          onClick={() => onRemoveVideo(v.id)}
                          aria-label={`Supprimer ${v.titre}`}
                        >
                          <Icon name="trash" size={14} />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Aucune vidéo taguée pour cette chorégraphie.</p>
          )}

          {editing ? (
            <div className="video-source-buttons">
              <button type="button" className="btn btn--secondary" onClick={() => setShowChoose(true)}>
                <Icon name="folder" size={16} /> Choisir
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => setShowAddVideo(true)}>
                <Icon name="plus" size={16} /> Vidéo
              </button>
            </div>
          ) : (
            <p className="muted choregraphie-detail__video-hint">
              Passez en édition pour choisir, ajouter, modifier ou supprimer des vidéos.
            </p>
          )}
        </section>
      </div>

      {showChooseEleves && (
        <Modal title="Choisir des élèves" onClose={() => setShowChooseEleves(false)}>
          <div className="checkbox-list">
            {roster.map((el) => (
              <label key={el.id} className="checkbox-list__item">
                <input
                  type="checkbox"
                  checked={choregraphie.eleveIds.includes(el.id)}
                  onChange={() => toggleEleve(el.id)}
                />
                {el.prenom} {el.nom}
              </label>
            ))}
            {roster.length === 0 && <p className="muted">Aucun élève inscrit à ce cours.</p>}
          </div>
        </Modal>
      )}

      {showChoose && (
        <Modal title="Choisir des vidéos" onClose={() => setShowChoose(false)}>
          <div className="checkbox-list">
            {videosDuCours.map((v) => (
              <label key={v.id} className="checkbox-list__item">
                <input
                  type="checkbox"
                  checked={v.choregraphieId === choregraphie.id}
                  onChange={() => onToggleVideoTag(v.id)}
                />
                {v.titre}
              </label>
            ))}
            {videosDuCours.length === 0 && (
              <p className="muted">Aucune vidéo pour ce cours — ajoutez-en une.</p>
            )}
          </div>
        </Modal>
      )}

      {showAddVideo && (
        <AddVideoModal
          lockedChoregraphieId={choregraphie.id}
          onClose={() => setShowAddVideo(false)}
          onAdd={(donnees) => {
            onAddVideo(donnees)
            setShowAddVideo(false)
          }}
        />
      )}

      {editingVideo && (
        <EditVideoModal
          video={editingVideo}
          onClose={() => setEditingVideo(null)}
          onSave={(patch) => {
            onUpdateVideo(editingVideo.id, patch)
            setEditingVideo(null)
          }}
        />
      )}
    </div>
  )
}

function EditVideoModal({ video, onClose, onSave }) {
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
