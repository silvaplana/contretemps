import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { paiementLabels } from '../../data/mockData.js'

const PAIEMENT_TONE = { a_jour: 'success', en_attente: 'warning', retard: 'danger' }

// Onglet Admin > Élèves (voir spec/SPEC.md 5.1.1 et images/admin-eleves.png).
// Tableau à 10 colonnes, chaque cellule éditable au clic.
export default function AdminEleves({ eleves, setEleves, cours }) {
  const [search, setSearch] = useState('')
  const [coursEditId, setCoursEditId] = useState(null)
  const [commentEditId, setCommentEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  const filtered = eleves.filter((el) =>
    `${el.prenom} ${el.nom}`.toLowerCase().includes(search.toLowerCase()),
  )

  function update(id, patch) {
    setEleves((list) => list.map((el) => (el.id === id ? { ...el, ...patch } : el)))
  }

  function toggleCours(eleveId, coursId) {
    setEleves((list) =>
      list.map((el) => {
        if (el.id !== eleveId) return el
        const has = el.coursIds.includes(coursId)
        return {
          ...el,
          coursIds: has ? el.coursIds.filter((id) => id !== coursId) : [...el.coursIds, coursId],
        }
      }),
    )
  }

  function remove(id) {
    if (window.confirm('Supprimer cet élève ?')) {
      setEleves((list) => list.filter((el) => el.id !== id))
    }
  }

  function addEleve(nom, prenom) {
    setEleves((list) => [
      ...list,
      {
        id: crypto.randomUUID(),
        nom,
        prenom,
        coursIds: [],
        statutPaiement: 'en_attente',
        commentaire: '',
        dateNaissance: '',
        parent: '',
        telephone: '',
        email: '',
        adresse: '',
        certificatMedical: false,
      },
    ])
  }

  const coursEnEdition = eleves.find((el) => el.id === coursEditId)
  const commentEnEdition = eleves.find((el) => el.id === commentEditId)

  return (
    <div className="admin-panel">
      <div className="search-bar">
        <Icon name="search" size={18} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher un élève par nom"
        />
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Élève</th>
              <th>Cours suivis</th>
              <th>Statut paiement</th>
              <th>Commentaire</th>
              <th>Date de naissance</th>
              <th>Parent / contact</th>
              <th>Téléphone</th>
              <th>Email</th>
              <th>Adresse</th>
              <th>Certificat médical</th>
              <th aria-label="Supprimer" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((el) => (
              <tr key={el.id}>
                <td className="data-table__name">
                  <EditableText
                    value={`${el.prenom} ${el.nom}`}
                    onChange={(v) => {
                      const [prenom, ...rest] = v.split(' ')
                      update(el.id, { prenom, nom: rest.join(' ') })
                    }}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className="badge-list badge-list--button"
                    onClick={() => setCoursEditId(el.id)}
                  >
                    {el.coursIds.length === 0 && <span className="muted">—</span>}
                    {el.coursIds.map((cid) => (
                      <Badge key={cid}>{cours.find((c) => c.id === cid)?.nom}</Badge>
                    ))}
                  </button>
                </td>
                <td>
                  <select
                    className={`select-pill select-pill--${PAIEMENT_TONE[el.statutPaiement]}`}
                    value={el.statutPaiement}
                    onChange={(e) => update(el.id, { statutPaiement: e.target.value })}
                  >
                    {Object.entries(paiementLabels).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <button
                    type="button"
                    className="cell-comment"
                    onClick={() => setCommentEditId(el.id)}
                  >
                    {el.commentaire || <span className="muted">—</span>}
                  </button>
                </td>
                <td>
                  <EditableText
                    type="date"
                    value={el.dateNaissance}
                    onChange={(v) => update(el.id, { dateNaissance: v })}
                  />
                </td>
                <td>
                  <EditableText
                    value={el.parent}
                    onChange={(v) => update(el.id, { parent: v })}
                  />
                </td>
                <td>
                  <EditableText
                    value={el.telephone}
                    onChange={(v) => update(el.id, { telephone: v })}
                  />
                </td>
                <td>
                  <EditableText value={el.email} onChange={(v) => update(el.id, { email: v })} />
                </td>
                <td>
                  <EditableText
                    value={el.adresse}
                    onChange={(v) => update(el.id, { adresse: v })}
                  />
                </td>
                <td>
                  <button
                    type="button"
                    className={`toggle-chip ${el.certificatMedical ? 'is-on' : ''}`}
                    onClick={() => update(el.id, { certificatMedical: !el.certificatMedical })}
                  >
                    {el.certificatMedical ? 'Reçu' : 'Manquant'}
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    className="icon-btn icon-btn--danger"
                    onClick={() => remove(el.id)}
                    aria-label={`Supprimer ${el.prenom}`}
                  >
                    <Icon name="trash" size={18} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter un élève">
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

      {commentEnEdition && (
        <Modal title={`Commentaire — ${commentEnEdition.prenom}`} onClose={() => setCommentEditId(null)}>
          <textarea
            className="modal-textarea"
            rows={6}
            value={commentEnEdition.commentaire}
            onChange={(e) => update(commentEnEdition.id, { commentaire: e.target.value })}
            placeholder="Allergie, information médicale, remarque..."
          />
        </Modal>
      )}

      {showAdd && (
        <AddEleveModal onClose={() => setShowAdd(false)} onAdd={addEleve} />
      )}
    </div>
  )
}

function AddEleveModal({ onClose, onAdd }) {
  const [nom, setNom] = useState('')
  const [prenom, setPrenom] = useState('')

  return (
    <Modal
      title="Ajouter un élève"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom || !prenom}
          onClick={() => {
            onAdd(nom, prenom)
            onClose()
          }}
        >
          Ajouter
        </button>
      }
    >
      <label htmlFor="add-prenom">Prénom</label>
      <input id="add-prenom" value={prenom} onChange={(e) => setPrenom(e.target.value)} />
      <label htmlFor="add-nom">Nom</label>
      <input id="add-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
    </Modal>
  )
}
