import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import VideoThumb from '../../components/VideoThumb.jsx'
import AjouterVideo from '../video/AjouterVideo.jsx'
import EditVideoModal from '../video/EditVideoModal.jsx'
import ChoixElevesPanel from './ChoixElevesPanel.jsx'

// Écran 2/2 de Chorégraphie : le détail d'UNE chorégraphie, plein écran,
// avec une flèche de retour vers ChoregraphieListScreen — même principe que
// la Messagerie. Consultation par défaut ; le bouton stylo (à côté de la
// poubelle) bascule en mode édition pour qui peut gérer la chorégraphie
// (admin, ou professeur de son cours — spec §5.3).
//
// Vidéos (plus d'onglet Vidéo, refonte du 2026-10-03) : tout le monde peut
// en ajouter une ; la modifier est réservé à qui gère la chorégraphie ; la
// supprimer aussi, plus celui qui l'a ajoutée.
export default function ChoregraphieDetailScreen({
  choregraphie,
  cours,
  coursGerables,
  tousLesCours,
  eleves,
  ecoleId,
  utilisateurId,
  peutModifier,
  erreur,
  onBack,
  onUpdate,
  onRemove,
  creerVideo,
  onAddVideo,
  onUpdateVideo,
  onRemoveVideo,
  onMonterVideo,
}) {
  // Toujours en lecture pour qui ne gère pas la chorégraphie, même si
  // `editing` restait vrai d'une bascule de profil famille précédente.
  const [editingVoulu, setEditing] = useState(false)
  const editing = editingVoulu && peutModifier
  const [editingVideo, setEditingVideo] = useState(null)
  const [showChooseEleves, setShowChooseEleves] = useState(false)

  const videos = choregraphie.videos

  function retirerEleve(id) {
    onUpdate({ eleveIds: choregraphie.eleveIds.filter((x) => x !== id) })
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

        {peutModifier && (
          <>
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
          </>
        )}
      </div>

      <div className="choregraphie-detail">
        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        <section>
          <h3>Cours</h3>
          {editing ? (
            <select
              className="field-input"
              aria-label="Cours de la chorégraphie"
              value={choregraphie.coursId}
              onChange={(e) => onUpdate({ coursId: Number(e.target.value) })}
            >
              {/* Le cours actuel d'abord, puis ceux que l'on peut gérer. */}
              {[cours, ...coursGerables.filter((c) => c.id !== cours?.id)].filter(Boolean).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                </option>
              ))}
            </select>
          ) : (
            <p>{cours?.nom || <span className="muted">—</span>}</p>
          )}
        </section>

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
                    onClick={() => retirerEleve(id)}
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
                  <VideoThumb video={v} />
                  <div className="video-card__body">
                    <div>
                      <strong>{v.titre}</strong>
                      {v.description && <p>{v.description}</p>}
                    </div>
                    <div className="row-actions">
                      {editing && videos[0].id !== v.id && (
                        <button
                          type="button"
                          className="icon-btn icon-btn--sm"
                          onClick={() => onMonterVideo(v.id)}
                          aria-label={`Monter ${v.titre}`}
                        >
                          <Icon name="chevronLeft" size={14} className="icone--vers-le-haut" />
                        </button>
                      )}
                      {peutModifier && (
                        <button
                          type="button"
                          className="icon-btn icon-btn--sm"
                          onClick={() => setEditingVideo(v)}
                          aria-label={`Modifier ${v.titre}`}
                        >
                          <Icon name="edit" size={14} />
                        </button>
                      )}
                      {/* Celui qui a ajouté la vidéo peut toujours la retirer. */}
                      {(peutModifier || v.auteurId === utilisateurId) && (
                        <button
                          type="button"
                          className="icon-btn icon-btn--sm icon-btn--danger"
                          onClick={() => onRemoveVideo(v.id)}
                          aria-label={`Supprimer ${v.titre}`}
                        >
                          <Icon name="trash" size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Aucune vidéo pour cette chorégraphie.</p>
          )}

          {/* Ajouter une vidéo : ouvert à tous (spec §5.3). */}
          <AjouterVideo ecoleId={ecoleId} creerVideo={creerVideo} onAdded={onAddVideo} />
        </section>
      </div>

      {showChooseEleves && (
        <ChoixElevesPanel
          eleves={eleves}
          cours={tousLesCours}
          coursInitial={choregraphie.coursId}
          choisis={choregraphie.eleveIds}
          onValider={(ids) => {
            onUpdate({ eleveIds: ids })
            setShowChooseEleves(false)
          }}
          onClose={() => setShowChooseEleves(false)}
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
