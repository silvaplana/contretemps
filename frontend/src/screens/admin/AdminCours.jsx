import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

const MAX_BADGES = 2

// Onglet Admin > Cours (voir spec/SPEC.md 5.1.3 et images/admin-cours.png).
// "Élèves inscrits" est dérivé de eleves[].coursIds (relation portée côté
// élève, voir schéma section 6) : lecture seule ici, ça se modifie depuis
// l'onglet Élèves. Les autres champs se modifient via la modale (icône
// stylo) plutôt qu'en ligne : ça couvre aussi la Salle, absente du tableau.
export default function AdminCours({ cours, setCours, professeurs, eleves }) {
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState(null)

  const filtered = cours.filter((c) => c.nom.toLowerCase().includes(search.toLowerCase()))
  const enEdition = cours.find((c) => c.id === editId)

  function update(id, patch) {
    setCours((list) => list.map((c) => (c.id === id ? { ...c, ...patch } : c)))
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
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => {
              const inscrits = elevesDuCours(c.id)
              const prof = professeurs.find((p) => p.id === c.professeurId)
              return (
                <tr key={c.id}>
                  <td className="data-table__name">{c.nom}</td>
                  <td>
                    {c.jour} {c.heureDebut}-{c.heureFin}
                  </td>
                  <td>{prof ? `${prof.prenom} ${prof.nom.charAt(0)}.` : <span className="muted">—</span>}</td>
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
                    <div className="row-actions">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setEditId(c.id)}
                        aria-label={`Modifier ${c.nom}`}
                      >
                        <Icon name="edit" size={18} />
                      </button>
                      <button
                        type="button"
                        className="icon-btn icon-btn--danger"
                        onClick={() => remove(c.id)}
                        aria-label={`Supprimer ${c.nom}`}
                      >
                        <Icon name="trash" size={18} />
                      </button>
                    </div>
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
        <CoursModal
          title="Ajouter un cours"
          submitLabel="Ajouter"
          professeurs={professeurs}
          onClose={() => setShowAdd(false)}
          onSubmit={(donnees) => setCours((list) => [...list, { id: crypto.randomUUID(), ...donnees }])}
        />
      )}

      {enEdition && (
        <CoursModal
          title={`Modifier — ${enEdition.nom}`}
          submitLabel="Enregistrer"
          initial={enEdition}
          professeurs={professeurs}
          onClose={() => setEditId(null)}
          onSubmit={(donnees) => update(enEdition.id, donnees)}
        />
      )}
    </div>
  )
}

// Formulaire complet (Nom, Jour, Horaire, Salle, Professeur) réutilisé pour
// l'ajout et la modification — `initial` pré-remplit les champs en édition.
function CoursModal({ title, submitLabel, initial, professeurs, onClose, onSubmit }) {
  const [nom, setNom] = useState(initial?.nom ?? '')
  const [jour, setJour] = useState(initial?.jour ?? 'Mercredi')
  const [heureDebut, setHeureDebut] = useState(initial?.heureDebut ?? '')
  const [heureFin, setHeureFin] = useState(initial?.heureFin ?? '')
  const [salle, setSalle] = useState(initial?.salle ?? '')
  const [professeurId, setProfesseurId] = useState(initial?.professeurId ?? professeurs[0]?.id ?? '')

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom}
          onClick={() => {
            onSubmit({ nom, jour, heureDebut, heureFin, salle, professeurId })
            onClose()
          }}
        >
          {submitLabel}
        </button>
      }
    >
      <label htmlFor="cours-nom">Nom du cours</label>
      <input id="cours-nom" value={nom} onChange={(e) => setNom(e.target.value)} />
      <label htmlFor="cours-jour">Jour</label>
      <input id="cours-jour" value={jour} onChange={(e) => setJour(e.target.value)} />
      <label htmlFor="cours-debut">Heure de début</label>
      <input
        id="cours-debut"
        value={heureDebut}
        placeholder="17h00"
        onChange={(e) => setHeureDebut(e.target.value)}
      />
      <label htmlFor="cours-fin">Heure de fin</label>
      <input
        id="cours-fin"
        value={heureFin}
        placeholder="18h30"
        onChange={(e) => setHeureFin(e.target.value)}
      />
      <label htmlFor="cours-salle">Salle</label>
      <input id="cours-salle" value={salle} onChange={(e) => setSalle(e.target.value)} />
      <label htmlFor="cours-prof">Professeur</label>
      <select id="cours-prof" value={professeurId} onChange={(e) => setProfesseurId(e.target.value)}>
        {professeurs.map((p) => (
          <option key={p.id} value={p.id}>
            {p.prenom} {p.nom}
          </option>
        ))}
      </select>
    </Modal>
  )
}
