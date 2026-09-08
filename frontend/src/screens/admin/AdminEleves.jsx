import { useRef, useState } from 'react'
import Badge from '../../components/Badge.jsx'
import EditableText from '../../components/EditableText.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { paiementLabels } from '../../data/mockData.js'

const PAIEMENT_TONE = { en_cours: 'warning', paye: 'success' }

const DUREE_APPUI_LONG = 500 // ms

// Libellé affiché en titre de la popover "voir en entier / marquer en
// rouge" (appui long — voir ci-dessous), et texte complet par colonne pour
// cette même popover : utile quand une cellule est trop étroite pour tout
// montrer (ex. beaucoup de cours, adresse longue...).
const CHAMP_LABEL = {
  nom: 'Élève',
  cours: 'Cours suivis',
  paiement: 'Paiement',
  commentaire: 'Commentaire',
  naissance: 'Date de naissance',
  age: 'Âge',
  contacts: 'Contacts',
  telephone: 'Téléphone',
  email: 'Email',
  adresse: 'Adresse',
  sante: 'Santé',
  certificat: 'Certificat médical',
}

function valeurCellule(el, champ, cours) {
  switch (champ) {
    case 'nom':
      return `${el.prenom} ${el.nom}`
    case 'cours':
      return el.coursIds.map((cid) => cours.find((c) => c.id === cid)?.nom).filter(Boolean).join(', ')
    case 'paiement':
      return `${paiementLabels[el.statutPaiement]} — ${el.montantPaye}€ / ${el.montantTotalAnnee}€`
    case 'commentaire':
      return el.commentaireAdmin
    case 'naissance':
      return el.dateNaissance
    case 'age': {
      const age = calculerAge(el.dateNaissance)
      return age == null ? '' : `${age} ans`
    }
    case 'contacts':
      return el.contactsEleve
        .map((c) => `${c.prenom} ${c.nom} (${c.lien}) — ${c.telephone} — ${c.email}`)
        .join('\n')
    case 'telephone':
      return el.telephone
    case 'email':
      return el.email
    case 'adresse':
      return el.adresse
    case 'sante':
      return [
        el.allergies && `Allergies : ${el.allergies}`,
        el.traitementMedical && `Traitement : ${el.traitementMedical}`,
        el.informationsImportantes && `Infos : ${el.informationsImportantes}`,
      ]
        .filter(Boolean)
        .join('\n')
    case 'certificat':
      return el.certificatMedical ? 'Reçu' : 'Manquant'
    default:
      return ''
  }
}

// Âge calculé à la volée depuis la date de naissance (voir spec §6.4) —
// jamais stocké, recalculé à chaque affichage.
function calculerAge(dateNaissance) {
  if (!dateNaissance) return null
  const naissance = new Date(dateNaissance)
  const aujourdhui = new Date()
  let age = aujourdhui.getFullYear() - naissance.getFullYear()
  const pasEncoreAnniversaire =
    aujourdhui.getMonth() < naissance.getMonth() ||
    (aujourdhui.getMonth() === naissance.getMonth() && aujourdhui.getDate() < naissance.getDate())
  if (pasEncoreAnniversaire) age -= 1
  return age
}

// Onglet Admin > Élèves (voir spec/SPEC.md §5.1.2 et §6.4). Les champs les
// moins consultés au quotidien (contacts, santé) sont regroupés dans une
// modale par ligne plutôt qu'en colonnes, pour garder le tableau lisible.
export default function AdminEleves({ eleves, setEleves, cours }) {
  const [search, setSearch] = useState('')
  const [coursEditId, setCoursEditId] = useState(null)
  const [commentEditId, setCommentEditId] = useState(null)
  const [paiementEditId, setPaiementEditId] = useState(null)
  const [contactsEditId, setContactsEditId] = useState(null)
  const [santeEditId, setSanteEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [showImport, setShowImport] = useState(false)
  // Appui long sur une cellule (voir spec — trop petite pour tout montrer
  // parfois) : ouvre une popover avec la valeur complète + la possibilité
  // de marquer cette cellule, ou toute la ligne, en rouge.
  const [pressed, setPressed] = useState(null) // { eleveId, champ }
  const minuteurRef = useRef(null)
  const ignorerProchainClicRef = useRef(false)

  function demarrerAppuiLong(eleveId, champ) {
    clearTimeout(minuteurRef.current)
    minuteurRef.current = setTimeout(() => {
      ignorerProchainClicRef.current = true
      setPressed({ eleveId, champ })
    }, DUREE_APPUI_LONG)
  }
  function annulerAppuiLong() {
    clearTimeout(minuteurRef.current)
  }
  // En capture (avant le onClick du bouton/lien à l'intérieur de la
  // cellule) : avale le clic qui suit un appui long, sinon la popover qui
  // vient de s'ouvrir se ferme aussitôt (le clic tombe sur son overlay).
  function avalerClicSiAppuiLong(e) {
    if (ignorerProchainClicRef.current) {
      e.preventDefault()
      e.stopPropagation()
      ignorerProchainClicRef.current = false
    }
  }

  function celluleProps(eleveId, champ) {
    return {
      onPointerDown: () => demarrerAppuiLong(eleveId, champ),
      onPointerUp: annulerAppuiLong,
      onPointerLeave: annulerAppuiLong,
      onPointerCancel: annulerAppuiLong,
      onContextMenu: (e) => e.preventDefault(),
      onClickCapture: avalerClicSiAppuiLong,
    }
  }

  function toggleCelluleRouge(eleveId, champ) {
    setEleves((list) =>
      list.map((el) => {
        if (el.id !== eleveId) return el
        const actuelles = el.cellulesRouges ?? []
        const deja = actuelles.includes(champ)
        return {
          ...el,
          cellulesRouges: deja ? actuelles.filter((c) => c !== champ) : [...actuelles, champ],
        }
      }),
    )
  }

  function toggleLigneRouge(eleveId) {
    setEleves((list) =>
      list.map((el) => (el.id === eleveId ? { ...el, ligneRouge: !el.ligneRouge } : el)),
    )
  }

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
        contactsEleve: [],
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

  // Plusieurs contacts possibles par élève (voir spec §6.4) — remplace
  // l'ancien champ "urgence" unique, insuffisant dès que les 2 parents ont
  // des coordonnées séparées.
  function addContact(eleveId) {
    setEleves((list) =>
      list.map((el) =>
        el.id === eleveId
          ? {
              ...el,
              contactsEleve: [
                ...el.contactsEleve,
                { nom: el.nom, prenom: '', lien: '', telephone: '', email: '' },
              ],
            }
          : el,
      ),
    )
  }

  function updateContact(eleveId, index, patch) {
    setEleves((list) =>
      list.map((el) =>
        el.id === eleveId
          ? {
              ...el,
              contactsEleve: el.contactsEleve.map((c, i) => (i === index ? { ...c, ...patch } : c)),
            }
          : el,
      ),
    )
  }

  function removeContact(eleveId, index) {
    setEleves((list) =>
      list.map((el) =>
        el.id === eleveId
          ? { ...el, contactsEleve: el.contactsEleve.filter((_, i) => i !== index) }
          : el,
      ),
    )
  }

  const coursEnEdition = eleves.find((el) => el.id === coursEditId)
  const commentEnEdition = eleves.find((el) => el.id === commentEditId)
  const paiementEnEdition = eleves.find((el) => el.id === paiementEditId)
  const contactsEnEdition = eleves.find((el) => el.id === contactsEditId)
  const santeEnEdition = eleves.find((el) => el.id === santeEditId)
  const eleveAppuye = pressed ? eleves.find((el) => el.id === pressed.eleveId) : null

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
              <th>Âge</th>
              <th>Contacts</th>
              <th>Téléphone</th>
              <th>Email</th>
              <th>Adresse</th>
              <th>Santé</th>
              <th>Certificat médical</th>
              <th aria-label="Supprimer" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((el) => {
              const cellulesRouges = el.cellulesRouges ?? []
              function classeCellule(champ) {
                return cellulesRouges.includes(champ) ? 'is-cellule-rouge' : ''
              }
              return (
                <tr key={el.id} className={el.ligneRouge ? 'is-ligne-rouge' : ''}>
                  <td className={`data-table__name ${classeCellule('nom')}`} {...celluleProps(el.id, 'nom')}>
                    <EditableText
                      value={`${el.prenom} ${el.nom}`}
                      onChange={(v) => {
                        const [prenom, ...rest] = v.split(' ')
                        update(el.id, { prenom, nom: rest.join(' ') })
                      }}
                    />
                  </td>
                  <td className={classeCellule('cours')} {...celluleProps(el.id, 'cours')}>
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
                  <td className={classeCellule('paiement')} {...celluleProps(el.id, 'paiement')}>
                    <button
                      type="button"
                      className={`select-pill select-pill--${PAIEMENT_TONE[el.statutPaiement]}`}
                      onClick={() => setPaiementEditId(el.id)}
                    >
                      {paiementLabels[el.statutPaiement]} — {el.montantPaye}€/{el.montantTotalAnnee}€
                    </button>
                  </td>
                  <td className={classeCellule('commentaire')} {...celluleProps(el.id, 'commentaire')}>
                    <button
                      type="button"
                      className="cell-comment"
                      onClick={() => setCommentEditId(el.id)}
                    >
                      {el.commentaireAdmin || <span className="muted">—</span>}
                    </button>
                  </td>
                  <td className={classeCellule('naissance')} {...celluleProps(el.id, 'naissance')}>
                    <EditableText
                      type="date"
                      value={el.dateNaissance}
                      onChange={(v) => update(el.id, { dateNaissance: v })}
                    />
                  </td>
                  <td className={classeCellule('age')} {...celluleProps(el.id, 'age')}>
                    {calculerAge(el.dateNaissance) ?? <span className="muted">—</span>}
                  </td>
                  <td className={classeCellule('contacts')} {...celluleProps(el.id, 'contacts')}>
                    <button
                      type="button"
                      className="cell-comment"
                      onClick={() => setContactsEditId(el.id)}
                    >
                      {el.contactsEleve.length === 0 ? (
                        <span className="muted">—</span>
                      ) : el.contactsEleve.length === 1 ? (
                        `${el.contactsEleve[0].prenom} ${el.contactsEleve[0].nom} (${el.contactsEleve[0].lien})`
                      ) : (
                        `${el.contactsEleve.length} contacts`
                      )}
                    </button>
                  </td>
                  <td className={classeCellule('telephone')} {...celluleProps(el.id, 'telephone')}>
                    <EditableText
                      value={el.telephone}
                      onChange={(v) => update(el.id, { telephone: v })}
                    />
                  </td>
                  <td className={classeCellule('email')} {...celluleProps(el.id, 'email')}>
                    <EditableText value={el.email} onChange={(v) => update(el.id, { email: v })} />
                  </td>
                  <td className={classeCellule('adresse')} {...celluleProps(el.id, 'adresse')}>
                    <EditableText
                      value={el.adresse}
                      onChange={(v) => update(el.id, { adresse: v })}
                    />
                  </td>
                  <td className={classeCellule('sante')} {...celluleProps(el.id, 'sante')}>
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
                  <td className={classeCellule('certificat')} {...celluleProps(el.id, 'certificat')}>
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
              )
            })}
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

      {contactsEnEdition && (
        <Modal
          title={`Contacts — ${contactsEnEdition.prenom}`}
          onClose={() => setContactsEditId(null)}
        >
          <p className="muted">
            Plusieurs contacts possibles (ex. mère et père séparément, chacun avec son propre
            téléphone/email).
          </p>
          <div className="contacts-eleve-list">
            {contactsEnEdition.contactsEleve.map((c, i) => (
              <div key={i} className="contacts-eleve-list__item">
                <div className="contacts-eleve-list__row">
                  <input
                    className="field-input"
                    placeholder="Prénom"
                    value={c.prenom}
                    onChange={(e) => updateContact(contactsEnEdition.id, i, { prenom: e.target.value })}
                  />
                  <input
                    className="field-input"
                    placeholder="Nom"
                    value={c.nom}
                    onChange={(e) => updateContact(contactsEnEdition.id, i, { nom: e.target.value })}
                  />
                  <button
                    type="button"
                    className="icon-btn icon-btn--danger"
                    onClick={() => removeContact(contactsEnEdition.id, i)}
                    aria-label="Retirer ce contact"
                  >
                    <Icon name="x" size={16} />
                  </button>
                </div>
                <input
                  className="field-input"
                  placeholder="Lien (ex. Mère, Père...)"
                  value={c.lien}
                  onChange={(e) => updateContact(contactsEnEdition.id, i, { lien: e.target.value })}
                />
                <input
                  className="field-input"
                  placeholder="Téléphone"
                  value={c.telephone}
                  onChange={(e) => updateContact(contactsEnEdition.id, i, { telephone: e.target.value })}
                />
                <input
                  className="field-input"
                  type="email"
                  placeholder="Email"
                  value={c.email}
                  onChange={(e) => updateContact(contactsEnEdition.id, i, { email: e.target.value })}
                />
              </div>
            ))}
            {contactsEnEdition.contactsEleve.length === 0 && (
              <p className="muted">Aucun contact pour l'instant.</p>
            )}
          </div>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => addContact(contactsEnEdition.id)}
          >
            <Icon name="plus" size={16} /> Ajouter un contact
          </button>
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

      {eleveAppuye && (
        <Modal title={CHAMP_LABEL[pressed.champ]} onClose={() => setPressed(null)}>
          <p className="muted">{eleveAppuye.prenom} {eleveAppuye.nom}</p>
          <p className="cellule-popover__valeur">
            {valeurCellule(eleveAppuye, pressed.champ, cours) || <span className="muted">(vide)</span>}
          </p>
          <div className="cellule-popover__actions">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => {
                toggleCelluleRouge(eleveAppuye.id, pressed.champ)
                setPressed(null)
              }}
            >
              {(eleveAppuye.cellulesRouges ?? []).includes(pressed.champ)
                ? 'Retirer le rouge de cette cellule'
                : 'Marquer cette cellule en rouge'}
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => {
                toggleLigneRouge(eleveAppuye.id)
                setPressed(null)
              }}
            >
              {eleveAppuye.ligneRouge ? 'Retirer le rouge de la ligne' : 'Marquer toute la ligne en rouge'}
            </button>
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
