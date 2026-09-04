import { useState } from 'react'
import Badge from '../components/Badge.jsx'
import EditableText from '../components/EditableText.jsx'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'

// Écran Chorégraphie (Admin, Professeur, Parent — voir spec/SPEC.md 5.3 et
// images/choregraphie.png). Liste haute défilante + détail bas. Admin et
// Professeur peuvent ajouter/modifier/supprimer (voir droits, section 3).
export default function ChoregraphieScreen({ cours, list, setList, eleves }) {
  const [selectedId, setSelectedId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  // Si l'id sélectionné n'appartient pas (ou plus) à la liste courante
  // (changement de cours, suppression...), on retombe sur le premier élément
  // — dérivé au rendu plutôt que synchronisé par effet.
  const selected = list.find((ch) => ch.id === selectedId) ?? list[0] ?? null

  function update(id, patch) {
    setList((byC) => ({
      ...byC,
      [cours.id]: byC[cours.id].map((ch) => (ch.id === id ? { ...ch, ...patch } : ch)),
    }))
  }

  function removeVideo(id, index) {
    update(id, { videos: selected.videos.filter((_, i) => i !== index) })
  }

  function addVideo(id, titre) {
    update(id, { videos: [...selected.videos, { titre, url: '#' }] })
  }

  function removeChoregraphie(id) {
    if (!window.confirm('Supprimer cette chorégraphie ?')) return
    setList((byC) => ({ ...byC, [cours.id]: byC[cours.id].filter((ch) => ch.id !== id) }))
    setSelectedId(null)
  }

  return (
    <div className="screen">
      <div className="choregraphie-list">
        {list.map((ch) => (
          <button
            key={ch.id}
            type="button"
            className={`choregraphie-list__item ${ch.id === selectedId ? 'is-active' : ''}`}
            onClick={() => setSelectedId(ch.id)}
          >
            <span className="choregraphie-list__icon">
              <Icon name="music" size={18} />
            </span>
            <span>
              <strong>{ch.nom}</strong>
              <span className="muted"> {ch.eleveIds.length} élèves</span>
            </span>
          </button>
        ))}
        <button type="button" className="choregraphie-list__add" onClick={() => setShowAdd(true)}>
          <Icon name="plus" size={18} /> Nouvelle chorégraphie
        </button>
      </div>

      {selected ? (
        <div className="choregraphie-detail">
          <div className="choregraphie-detail__header">
            <EditableText value={selected.nom} onChange={(v) => update(selected.id, { nom: v })} />
            <button
              type="button"
              className="icon-btn icon-btn--danger"
              onClick={() => removeChoregraphie(selected.id)}
              aria-label="Supprimer la chorégraphie"
            >
              <Icon name="trash" size={18} />
            </button>
          </div>

          <section>
            <h3>
              <Icon name="users" size={16} /> Élèves
            </h3>
            <div className="badge-list">
              {selected.eleveIds.map((id) => {
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
              value={selected.costume}
              onChange={(e) => update(selected.id, { costume: e.target.value })}
            />
          </section>

          <section>
            <h3>Horaire de répétition</h3>
            <EditableText
              value={selected.horaireRepetition}
              onChange={(v) => update(selected.id, { horaireRepetition: v })}
            />
          </section>

          <section>
            <h3>Liens vidéos</h3>
            <ul className="link-list">
              {selected.videos.map((v, i) => (
                <li key={i}>
                  <Icon name="play" size={14} />
                  <a href={v.url} onClick={(e) => e.preventDefault()}>
                    {v.titre}
                  </a>
                  <button
                    type="button"
                    className="icon-btn icon-btn--sm"
                    onClick={() => removeVideo(selected.id, i)}
                    aria-label="Retirer ce lien"
                  >
                    <Icon name="x" size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <AddLienForm onAdd={(titre) => addVideo(selected.id, titre)} />
          </section>
        </div>
      ) : (
        <p className="muted" style={{ padding: '0 16px' }}>
          Aucune chorégraphie pour ce cours.
        </p>
      )}

      {showAdd && (
        <Modal title="Nouvelle chorégraphie" onClose={() => setShowAdd(false)}>
          <NewChoregraphieForm
            onCreate={(nom) => {
              const nouvelle = {
                id: crypto.randomUUID(),
                nom,
                eleveIds: [],
                costume: '',
                horaireRepetition: '',
                videos: [],
              }
              setList((byC) => ({ ...byC, [cours.id]: [...(byC[cours.id] ?? []), nouvelle] }))
              setSelectedId(nouvelle.id)
              setShowAdd(false)
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function NewChoregraphieForm({ onCreate }) {
  const [nom, setNom] = useState('')
  return (
    <>
      <label htmlFor="new-choregraphie-nom">Nom</label>
      <input id="new-choregraphie-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <button
        type="button"
        className="btn btn--primary btn--block"
        disabled={!nom}
        onClick={() => onCreate(nom)}
      >
        Créer
      </button>
    </>
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
