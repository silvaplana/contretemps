import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'

// Écran 2/2 de Chorégraphie : le détail d'UNE chorégraphie, plein écran,
// avec une flèche de retour vers ChoregraphieListScreen — même principe que
// la Messagerie. Consultation par défaut ; le bouton stylo (à côté de la
// poubelle) bascule en mode édition pour Admin/Professeur (voir droits,
// spec/SPEC.md section 3).
export default function ChoregraphieDetailScreen({ choregraphie, eleves, videos, onBack, onUpdate, onRemove }) {
  const [editing, setEditing] = useState(false)

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
              return el ? <Badge key={id}>{el.prenom}</Badge> : null
            })}
          </div>
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
            <ul className="link-list">
              {videos.map((v) => (
                <li key={v.id}>
                  <Icon name="play" size={14} />
                  <span>{v.titre}</span>
                  <span className="muted">{v.duree}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Aucune vidéo taguée pour cette chorégraphie.</p>
          )}
          <p className="muted choregraphie-detail__video-hint">
            Les vidéos se filment et se taguent depuis l'onglet Vidéo.
          </p>
        </section>
      </div>
    </div>
  )
}
