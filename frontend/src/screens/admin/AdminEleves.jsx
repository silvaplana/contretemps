import { useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { paiementLabels } from '../../data/mockData.js'

const PAIEMENT_TONE = { en_cours: 'warning', paye: 'success' }

// Onglet Admin > Élèves (voir spec/SPEC.md §5.1.2 et §6.4). Les champs les
// moins consultés au quotidien (urgence, santé) sont regroupés dans une
// modale par ligne plutôt qu'en colonnes, pour garder le tableau lisible.
export default function AdminEleves({ eleves, setEleves, cours }) {
  const [search, setSearch] = useState('')
  const [coursEditId, setCoursEditId] = useState(null)
  const [commentEditId, setCommentEditId] = useState(null)
  const [paiementEditId, setPaiementEditId] = useState(null)
  const [urgenceEditId, setUrgenceEditId] = useState(null)
  const [santeEditId, setSanteEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showImport, setShowImport] = useState(false)

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
        statutPaiement: 'en_cours',
        montantTotalAnnee: 0,
        montantPaye: 0,
        commentaireAdmin: '',
        dateNaissance: '',
        urgenceNom: '',
        urgencePrenom: '',
        urgenceLien: '',
        telephone: '',
        email: '',
        adresse: '',
        allergies: '',
        traitementMedical: '',
        informationsImportantes: '',
        certificatMedical: false,
      },
    ])
  }

  const coursEnEdition = eleves.find((el) => el.id === coursEditId)
  const commentEnEdition = eleves.find((el) => el.id === commentEditId)
  const paiementEnEdition = eleves.find((el) => el.id === paiementEditId)
  const urgenceEnEdition = eleves.find((el) => el.id === urgenceEditId)
  const santeEnEdition = eleves.find((el) => el.id === santeEditId)

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
        <table className="data-table data-table--eleves">
          <thead>
            <tr>
              <th>Élève</th>
              <th>Cours suivis</th>
              <th>Paiement</th>
              <th>Commentaire</th>
              <th>Date de naissance</th>
              <th>Urgence</th>
              <th>Téléphone</th>
              <th>Email</th>
              <th>Adresse</th>
              <th>Santé</th>
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
                  <button
                    type="button"
                    className={`select-pill select-pill--${PAIEMENT_TONE[el.statutPaiement]}`}
                    onClick={() => setPaiementEditId(el.id)}
                  >
                    {paiementLabels[el.statutPaiement]} — {el.montantPaye}€/{el.montantTotalAnnee}€
                  </button>
                </td>
                <td>
                  <button
                    type="button"
                    className="cell-comment"
                    onClick={() => setCommentEditId(el.id)}
                  >
                    {el.commentaireAdmin || <span className="muted">—</span>}
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
                  <button
                    type="button"
                    className="cell-comment"
                    onClick={() => setUrgenceEditId(el.id)}
                  >
                    {el.urgenceNom ? (
                      `${el.urgencePrenom} ${el.urgenceNom} (${el.urgenceLien})`
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </button>
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
                    className="cell-comment"
                    onClick={() => setSanteEditId(el.id)}
                  >
                    {el.allergies || el.traitementMedical || el.informationsImportantes ? (
                      'Voir'
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </button>
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

      <button
        type="button"
        className="fab--secondary"
        onClick={() => setShowImport(true)}
        aria-label="Importer des élèves"
      >
        <Icon name="folder" size={20} />
      </button>
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
            value={commentEnEdition.commentaireAdmin}
            onChange={(e) => update(commentEnEdition.id, { commentaireAdmin: e.target.value })}
            placeholder="Remarque interne, réservée à l'admin."
          />
        </Modal>
      )}

      {paiementEnEdition && (
        <Modal title={`Paiement — ${paiementEnEdition.prenom}`} onClose={() => setPaiementEditId(null)}>
          <div className="form-fields">
            <label htmlFor="paiement-statut">Statut</label>
            <select
              id="paiement-statut"
              className="field-input"
              value={paiementEnEdition.statutPaiement}
              onChange={(e) => update(paiementEnEdition.id, { statutPaiement: e.target.value })}
            >
              {Object.entries(paiementLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <label htmlFor="paiement-total">Montant total de l’année (€)</label>
            <input
              id="paiement-total"
              type="number"
              className="field-input"
              value={paiementEnEdition.montantTotalAnnee}
              onChange={(e) =>
                update(paiementEnEdition.id, { montantTotalAnnee: Number(e.target.value) })
              }
            />
            <label htmlFor="paiement-paye">Montant payé (€)</label>
            <input
              id="paiement-paye"
              type="number"
              className="field-input"
              value={paiementEnEdition.montantPaye}
              onChange={(e) => update(paiementEnEdition.id, { montantPaye: Number(e.target.value) })}
            />
          </div>
        </Modal>
      )}

      {urgenceEnEdition && (
        <Modal
          title={`Contact d’urgence — ${urgenceEnEdition.prenom}`}
          onClose={() => setUrgenceEditId(null)}
        >
          <div className="form-fields">
            <label htmlFor="urgence-prenom">Prénom</label>
            <input
              id="urgence-prenom"
              className="field-input"
              value={urgenceEnEdition.urgencePrenom}
              onChange={(e) => update(urgenceEnEdition.id, { urgencePrenom: e.target.value })}
            />
            <label htmlFor="urgence-nom">Nom</label>
            <input
              id="urgence-nom"
              className="field-input"
              value={urgenceEnEdition.urgenceNom}
              onChange={(e) => update(urgenceEnEdition.id, { urgenceNom: e.target.value })}
            />
            <label htmlFor="urgence-lien">Lien (ex. Mère, Père...)</label>
            <input
              id="urgence-lien"
              className="field-input"
              value={urgenceEnEdition.urgenceLien}
              onChange={(e) => update(urgenceEnEdition.id, { urgenceLien: e.target.value })}
            />
          </div>
        </Modal>
      )}

      {santeEnEdition && (
        <Modal title={`Santé — ${santeEnEdition.prenom}`} onClose={() => setSanteEditId(null)}>
          <div className="form-fields">
            <label htmlFor="sante-allergies">Allergies</label>
            <textarea
              id="sante-allergies"
              className="modal-textarea"
              rows={2}
              value={santeEnEdition.allergies}
              onChange={(e) => update(santeEnEdition.id, { allergies: e.target.value })}
            />
            <label htmlFor="sante-traitement">Traitement médical</label>
            <textarea
              id="sante-traitement"
              className="modal-textarea"
              rows={2}
              value={santeEnEdition.traitementMedical}
              onChange={(e) => update(santeEnEdition.id, { traitementMedical: e.target.value })}
            />
            <label htmlFor="sante-infos">Informations importantes</label>
            <textarea
              id="sante-infos"
              className="modal-textarea"
              rows={2}
              value={santeEnEdition.informationsImportantes}
              onChange={(e) =>
                update(santeEnEdition.id, { informationsImportantes: e.target.value })
              }
            />
          </div>
        </Modal>
      )}

      {showAdd && <AddEleveModal onClose={() => setShowAdd(false)} onAdd={addEleve} />}

      {showImport && <ImportElevesModal onClose={() => setShowImport(false)} />}
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

// Emplacement d'un futur import en masse — pas encore branché (ni lecture
// de fichier Excel/CSV, ni connexion Google Drive), juste l'endroit dans
// l'IHM où ça viendra.
function ImportElevesModal({ onClose }) {
  const [source, setSource] = useState(null)

  return (
    <Modal title="Importer des élèves" onClose={onClose}>
      <p className="muted">Importer plusieurs élèves d'un coup depuis un fichier ou Google Drive.</p>
      <div className="video-source-buttons">
        <button
          type="button"
          className="btn btn--secondary video-source-buttons__btn"
          onClick={() => setSource('fichier')}
        >
          <Icon name="folder" size={18} />
          Fichier Excel / CSV
        </button>
        <button
          type="button"
          className="btn btn--secondary video-source-buttons__btn"
          onClick={() => setSource('drive')}
        >
          <Icon name="folder" size={18} />
          Google Drive
        </button>
      </div>
      {source && (
        <p className="muted">
          <Icon name="check" size={14} />{' '}
          {source === 'fichier' ? 'Import de fichier' : 'Connexion à Google Drive'} — bientôt disponible.
        </p>
      )}
    </Modal>
  )
}
