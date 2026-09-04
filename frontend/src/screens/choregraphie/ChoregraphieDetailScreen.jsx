import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'

// Écran 2/2 de Chorégraphie : le détail d'UNE chorégraphie, plein écran,
// avec une flèche de retour vers ChoregraphieListScreen — même principe que
// la Messagerie. Admin et Professeur peuvent modifier/supprimer (voir droits,
// spec/SPEC.md section 3).
export default function ChoregraphieDetailScreen({
  choregraphie,
  eleves,
  onBack,
  onUpdate,
  onRemoveVideo,
  onAddVideo,
  onRemove,
}) {
  return (
    <div className="screen choregraphie-detail-screen">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux chorégraphies">
          <Icon name="chevronLeft" size={22} />
        </button>
        <EditableText
          value={choregraphie.nom}
          onChange={(v) => onUpdate({ nom: v })}
        />
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
          <textarea
            className="modal-textarea"
            rows={2}
            value={choregraphie.costume}
            onChange={(e) => onUpdate({ costume: e.target.value })}
          />
        </section>

        <section>
          <h3>Horaire de répétition</h3>
          <EditableText
            value={choregraphie.horaireRepetition}
            onChange={(v) => onUpdate({ horaireRepetition: v })}
          />
        </section>

        <section>
          <h3>Liens vidéos</h3>
          <ul className="link-list">
            {choregraphie.videos.map((v, i) => (
              <li key={i}>
                <Icon name="play" size={14} />
                <a href={v.url} onClick={(e) => e.preventDefault()}>
                  {v.titre}
                </a>
                <button
                  type="button"
                  className="icon-btn icon-btn--sm"
                  onClick={() => onRemoveVideo(i)}
                  aria-label="Retirer ce lien"
                >
                  <Icon name="x" size={14} />
                </button>
              </li>
            ))}
          </ul>
          <AddLienForm onAdd={onAddVideo} />
        </section>
      </div>
    </div>
  )
}

function AddLienForm({ onAdd }) {
  const [titre, setTitre] = useState('')
  return (
    <div className="add-membre-form__row">
      <input
        value={titre}
        placeholder="Titre du lien vidéo"
        onChange={(e) => setTitre(e.target.value)}
      />
      <button
        type="button"
        className="btn btn--secondary"
        disabled={!titre}
        onClick={() => {
          onAdd(titre)
          setTitre('')
        }}
      >
        Ajouter
      </button>
    </div>
  )
}
