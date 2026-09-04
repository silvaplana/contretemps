import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

// Onglet Admin > Professeurs (voir spec/SPEC.md 5.1.2 et images/admin-profs.png).
export default function AdminProfesseurs({ professeurs, setProfesseurs, cours }) {
  const [search, setSearch] = useState('')
  const [coursEditId, setCoursEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState(null)

  const filtered = professeurs.filter((p) =>
    `${p.prenom} ${p.nom}`.toLowerCase().includes(search.toLowerCase()),
  )

  function update(id, patch) {
    setProfesseurs((list) => list.map((p) => (p.id === id ? { ...p, ...patch } : p)))
  }

  function toggleCours(profId, coursId) {
    setProfesseurs((list) =>
      list.map((p) => {
        if (p.id !== profId) return p
        const has = p.coursIds.includes(coursId)
        return {
          ...p,
          coursIds: has ? p.coursIds.filter((id) => id !== coursId) : [...p.coursIds, coursId],
        }
      }),
    )
  }

  function remove(id) {
    if (window.confirm('Supprimer ce professeur ?')) {
      setProfesseurs((list) => list.filter((p) => p.id !== id))
    }
  }

  const coursEnEdition = professeurs.find((p) => p.id === coursEditId)
  const enEdition = professeurs.find((p) => p.id === editId)

  return (
    <div className="admin-panel">
      <div className="search-bar">
        <Icon name="search" size={18} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher un professeur"
        />
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Prénom</th>
              <th>Cours enseignés</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr key={p.id}>
                <td className="data-table__name">{p.nom}</td>
                <td>{p.prenom}</td>
                <td>
                  <button
                    type="button"
                    className="badge-list badge-list--button"
                    onClick={() => setCoursEditId(p.id)}
                  >
                    {p.coursIds.length === 0 && <span className="muted">—</span>}
                    {p.coursIds.map((cid) => (
                      <Badge key={cid}>{cours.find((c) => c.id === cid)?.nom}</Badge>
                    ))}
                  </button>
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={() => setEditId(p.id)}
                      aria-label={`Modifier ${p.prenom}`}
                    >
                      <Icon name="edit" size={18} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger"
                      onClick={() => remove(p.id)}
                      aria-label={`Supprimer ${p.prenom}`}
                    >
                      <Icon name="trash" size={18} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter un professeur">
        <Icon name="plus" size={24} />
      </button>

      {coursEnEdition && (
        <Modal title={`Cours de ${coursEnEdition.prenom}`} onClose={() => setCoursEditId(null)}>
          <div className="checkbox-list">
            {cours.map((c) => (
              <label key={c.id} className="checkbox-list__item">
                <input
                  type="checkbox"
                  checked={coursEnEdition.coursIds.includes(c.id)}
                  onChange={() => toggleCours(coursEnEdition.id, c.id)}
                />
                {c.nom}
              </label>
            ))}
          </div>
        </Modal>
      )}

      {showAdd && (
        <ProfModal
          title="Ajouter un professeur"
          submitLabel="Ajouter"
          onClose={() => setShowAdd(false)}
          onSubmit={(donnees) =>
            setProfesseurs((list) => [...list, { id: crypto.randomUUID(), coursIds: [], ...donnees }])
          }
        />
      )}

      {enEdition && (
        <ProfModal
          title={`Modifier — ${enEdition.prenom} ${enEdition.nom}`}
          submitLabel="Enregistrer"
          initial={enEdition}
          onClose={() => setEditId(null)}
          onSubmit={(donnees) => update(enEdition.id, donnees)}
        />
      )}
    </div>
  )
}

// Formulaire (Prénom, Nom, Email) réutilisé pour l'ajout et la modification.
function ProfModal({ title, submitLabel, initial, onClose, onSubmit }) {
  const [nom, setNom] = useState(initial?.nom ?? '')
  const [prenom, setPrenom] = useState(initial?.prenom ?? '')
  const [email, setEmail] = useState(initial?.email ?? '')

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom || !prenom}
          onClick={() => {
            onSubmit({ nom, prenom, email })
            onClose()
          }}
        >
          {submitLabel}
        </button>
      }
    >
      <label htmlFor="prof-prenom">Prénom</label>
      <input id="prof-prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
      <label htmlFor="prof-nom">Nom</label>
      <input id="prof-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <label htmlFor="prof-email">Email</label>
      <input id="prof-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
    </Modal>
  )
}
