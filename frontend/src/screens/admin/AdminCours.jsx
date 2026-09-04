import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

const MAX_BADGES = 2

// Onglet Admin > Cours (voir spec/SPEC.md 5.1.3 et images/admin-cours.png).
// "Élèves inscrits" est dérivé de eleves[].coursIds (relation portée côté
// élève, voir schéma section 6) : lecture seule ici, ça se modifie depuis
// l'onglet Élèves.
export default function AdminCours({ cours, setCours, professeurs, eleves }) {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  const filtered = cours.filter((c) => c.nom.toLowerCase().includes(search.toLowerCase()))

  function update(id, patch) {
    setCours((list) => list.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  }

  function updateHoraire(id, value) {
    const [jour, plage = ''] = value.split(' ')
    const [heureDebut, heureFin] = plage.split('-')
    update(id, {
      jour: jour || '',
      heureDebut: heureDebut || '',
      heureFin: heureFin || '',
    })
  }

  function remove(id) {
    if (window.confirm('Supprimer ce cours ?')) {
      setCours((list) => list.filter((c) => c.id !== id))
    }
  }

  function elevesDuCours(coursId) {
    return eleves.filter((el) => el.coursIds.includes(coursId))
  }

  return (
    <div className="admin-panel">
      <div className="search-bar">
        <Icon name="search" size={18} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher un cours"
        />
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Cours</th>
              <th>Horaire</th>
              <th>Prof</th>
              <th>Élèves</th>
              <th aria-label="Supprimer" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => {
              const inscrits = elevesDuCours(c.id)
              return (
                <tr key={c.id}>
                  <td className="data-table__name">
                    <EditableText value={c.nom} onChange={(v) => update(c.id, { nom: v })} />
                  </td>
                  <td>
                    <EditableText
                      value={`${c.jour} ${c.heureDebut}-${c.heureFin}`}
                      onChange={(v) => updateHoraire(c.id, v)}
                    />
                  </td>
                  <td>
                    <select
                      className="select-plain"
                      value={c.professeurId}
                      onChange={(e) => update(c.id, { professeurId: e.target.value })}
                    >
                      {professeurs.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.prenom} {p.nom.charAt(0)}.
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <div className="badge-list">
                      {inscrits.slice(0, MAX_BADGES).map((el) => (
                        <Badge key={el.id}>{el.prenom}</Badge>
                      ))}
                      {inscrits.length > MAX_BADGES && (
                        <Badge tone="neutral">+{inscrits.length - MAX_BADGES}</Badge>
                      )}
                      {inscrits.length === 0 && <span className="muted">—</span>}
                    </div>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger"
                      onClick={() => remove(c.id)}
                      aria-label={`Supprimer ${c.nom}`}
                    >
                      <Icon name="trash" size={18} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter un cours">
        <Icon name="plus" size={24} />
      </button>

      {showAdd && (
        <AddCoursModal
          professeurs={professeurs}
          onClose={() => setShowAdd(false)}
          onAdd={(cours_) => setCours((list) => [...list, cours_])}
        />
      )}
    </div>
  )
}

function AddCoursModal({ professeurs, onClose, onAdd }) {
  const [nom, setNom] = useState('')
  const [jour, setJour] = useState('Mercredi')
  const [heureDebut, setHeureDebut] = useState('')
  const [heureFin, setHeureFin] = useState('')
  const [salle, setSalle] = useState('')
  const [professeurId, setProfesseurId] = useState(professeurs[0]?.id ?? '')

  return (
    <Modal
      title="Ajouter un cours"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom}
          onClick={() => {
            onAdd({
              id: crypto.randomUUID(),
              nom,
              jour,
              heureDebut,
              heureFin,
              salle,
              professeurId,
            })
            onClose()
          }}
        >
          Ajouter
        </button>
      }
    >
      <label htmlFor="add-cours-nom">Nom du cours</label>
      <input id="add-cours-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <label htmlFor="add-cours-jour">Jour</label>
      <input id="add-cours-jour" value={jour} onChange={(e) => setJour(e.target.value)} />
      <label htmlFor="add-cours-debut">Heure de début</label>
      <input
        id="add-cours-debut"
        value={heureDebut}
        placeholder="17h00"
        onChange={(e) => setHeureDebut(e.target.value)}
      />
      <label htmlFor="add-cours-fin">Heure de fin</label>
      <input
        id="add-cours-fin"
        value={heureFin}
        placeholder="18h30"
        onChange={(e) => setHeureFin(e.target.value)}
      />
      <label htmlFor="add-cours-salle">Salle</label>
      <input id="add-cours-salle" value={salle} onChange={(e) => setSalle(e.target.value)} />
      <label htmlFor="add-cours-prof">Professeur</label>
      <select
        id="add-cours-prof"
        value={professeurId}
        onChange={(e) => setProfesseurId(e.target.value)}
      >
        {professeurs.map((p) => (
          <option key={p.id} value={p.id}>
            {p.prenom} {p.nom}
          </option>
        ))}
      </select>
    </Modal>
  )
}
