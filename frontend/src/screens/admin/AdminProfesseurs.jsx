import { useState } from 'react'
import * as profsApi from '../../api/profs.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

const MAX_BADGES = 2

// Onglet Admin > Professeurs (voir spec/SPEC.md §5.1.3 et §5.7). Le bouton
// calculatrice par ligne ouvre le relevé d'heures du professeur (n'importe
// lequel, l'admin peut tous les consulter).
//
// Données métier via api/profs.js (voir api/README.md) — `professeurs`/
// `setProfesseurs` viennent de App.jsx, mis à jour ici après chaque appel
// réussi (même principe que AdminEleves.jsx).
export default function AdminProfesseurs({ professeurs, setProfesseurs, cours, ecoleId, onOpenHeures }) {
  const [search, setSearch] = useState('')
  const [coursEditId, setCoursEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState(null)

  const filtered = professeurs.filter((p) =>
    `${p.prenom} ${p.nom}`.toLowerCase().includes(search.toLowerCase()),
  )

  function remplacer(profMisAJour) {
    setProfesseurs((list) => list.map((p) => (p.id === profMisAJour.id ? profMisAJour : p)))
  }

  async function update(id, patch) {
    remplacer(await profsApi.modifier(id, patch))
  }

  async function toggleCours(profId, coursId) {
    remplacer(await profsApi.basculerCours(profId, coursId))
  }

  async function remove(id) {
    if (!window.confirm('Supprimer ce professeur ?')) return
    await profsApi.supprimer(id)
    setProfesseurs((list) => list.filter((p) => p.id !== id))
  }

  async function addProf(donnees) {
    const nouveau = await profsApi.creer(ecoleId, donnees)
    // Voir AdminEleves.jsx : updater idempotent, StrictMode (dev) peut
    // l'appliquer 2 fois de suite sur son propre résultat.
    setProfesseurs((list) => (list.some((p) => p.id === nouveau.id) ? list : [...list, nouveau]))
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
                    {p.coursIds.slice(0, MAX_BADGES).map((cid) => (
                      <Badge key={cid}>{cours.find((c) => c.id === cid)?.nom}</Badge>
                    ))}
                    {p.coursIds.length > MAX_BADGES && (
                      <Badge tone="neutral">+{p.coursIds.length - MAX_BADGES}</Badge>
                    )}
                  </button>
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={() => onOpenHeures(p.id)}
                      aria-label={`Heures de ${p.prenom}`}
                    >
                      <Icon name="calculator" size={18} />
                    </button>
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
          onSubmit={addProf}
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
  // Garde-fou contre un double-appel (voir AdminEleves.jsx) : l'appel est
  // async désormais.
  const [enCours, setEnCours] = useState(false)

  async function valider() {
    if (enCours) return
    setEnCours(true)
    await onSubmit({ nom, prenom, email })
    onClose()
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!nom || !prenom || enCours}
          onClick={valider}
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
