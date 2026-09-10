import { useState } from 'react'
import * as conversationsApi from '../../api/conversations.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'

const TONE_PAR_TYPE = { admin: 'danger', professeur: 'success', eleve: 'neutral', cours: 'neutral' }

function libelleMembre(membre, { professeurs, eleves, cours }) {
  // `label` vient du backend réel (nom/prénom déjà résolus, voir
  // api/conversations.js: versEcranAdmin) — sinon (maquette), on retombe
  // sur les listes déjà chargées par ailleurs.
  if (membre.label) return membre.label
  if (membre.type === 'admin') return 'Direction'
  if (membre.type === 'professeur') {
    const p = professeurs.find((x) => x.id === membre.id)
    return p ? `${p.prenom} ${p.nom}` : '?'
  }
  if (membre.type === 'eleve') {
    const el = eleves.find((x) => x.id === membre.id)
    return el ? `${el.prenom} ${el.nom}` : '?'
  }
  const c = cours.find((x) => x.id === membre.id)
  return c ? c.nom : '?'
}

// Onglet Admin > Conversations (voir spec/SPEC.md §5.1.5 et §6.9). Une
// conversation se compose de blocs "Compte" (admin/professeur/élève
// individuel) et "Cours" (résout automatiquement tous ses élèves inscrits
// et son/ses professeur(s)).
//
// Groupe WhatsApp miroir (§6.9) : icône dans la liste + case à cocher à la
// création et à l'édition — toujours avec confirmation avant le vrai appel,
// puisque la création n'est pas réversible depuis cet écran (pas de "退
// détacher" pour l'instant, voir conversationsApi.creerGroupeWhatsapp —
// stub côté backend, pas encore branché sur un vrai client WhatsApp).
export default function AdminGroupes({ groupes, setGroupes, professeurs, eleves, cours, ecoleId }) {
  const [search, setSearch] = useState('')
  const [editId, setEditId] = useState(null)
  const [showAdd, setShowAdd] = useState(false)

  const filtered = groupes.filter((g) => g.nom.toLowerCase().includes(search.toLowerCase()))
  const enEdition = groupes.find((g) => g.id === editId)

  function remplacer(id, patch) {
    setGroupes((list) => list.map((g) => (g.id === id ? { ...g, ...patch } : g)))
  }

  async function renameGroupe(id, nom) {
    remplacer(id, { nom }) // optimiste : l'input ne doit pas attendre le réseau
    await conversationsApi.renommer(id, nom)
  }

  async function removeMembre(groupeId, membre, index) {
    remplacer(groupeId, {
      membres: groupes.find((g) => g.id === groupeId).membres.filter((_, i) => i !== index),
    })
    await conversationsApi.retirerMembre(groupeId, membre, index)
  }

  async function addMembre(groupeId, membre) {
    const nouvelle = await conversationsApi.ajouterMembre(groupeId, membre)
    remplacer(groupeId, { membres: [...groupes.find((g) => g.id === groupeId).membres, nouvelle ?? membre] })
  }

  async function removeGroupe(id) {
    if (!window.confirm('Supprimer cette conversation ?')) return
    await conversationsApi.supprimer(id)
    setGroupes((list) => list.filter((g) => g.id !== id))
  }

  async function creerGroupeWhatsapp(id) {
    if (
      !window.confirm(
        'Créer un groupe WhatsApp lié à cette conversation ? Cette action ne peut pas être annulée depuis cet écran.',
      )
    ) {
      return
    }
    const miroir = await conversationsApi.creerGroupeWhatsapp(id)
    remplacer(id, { whatsappStatut: miroir.whatsappStatut, whatsappGroupeId: miroir.whatsappGroupeId })
  }

  return (
    <div className="admin-panel">
      <div className="search-bar">
        <Icon name="search" size={18} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher une conversation"
        />
      </div>

      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Nom</th>
              <th>Personnes</th>
              <th aria-label="Groupe WhatsApp lié" />
              <th aria-label="Supprimer" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((g) => (
              <tr key={g.id}>
                <td className="data-table__name">{g.nom}</td>
                <td>
                  <div className="badge-list">
                    {g.membres.map((m, i) => (
                      <Badge key={i} tone={TONE_PAR_TYPE[m.type]}>
                        {m.type === 'cours' && <Icon name="users" size={12} />}
                        {libelleMembre(m, { professeurs, eleves, cours })}
                      </Badge>
                    ))}
                    {g.membres.length === 0 && <span className="muted">—</span>}
                  </div>
                </td>
                <td>
                  {g.whatsappStatut === 'cree' && (
                    <span className="whatsapp-statut" title="Groupe WhatsApp lié">
                      <Icon name="whatsapp" size={18} />
                    </span>
                  )}
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={() => setEditId(g.id)}
                      aria-label={`Modifier ${g.nom}`}
                    >
                      <Icon name="edit" size={18} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger"
                      onClick={() => removeGroupe(g.id)}
                      aria-label={`Supprimer ${g.nom}`}
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

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Créer une conversation">
        <Icon name="plus" size={24} />
      </button>

      {enEdition && (
        <Modal title={`Modifier — ${enEdition.nom}`} onClose={() => setEditId(null)}>
          <label htmlFor="edit-groupe-nom">Nom</label>
          <input
            id="edit-groupe-nom"
            value={enEdition.nom}
            onChange={(e) => renameGroupe(enEdition.id, e.target.value)}
          />

          <label>Personnes</label>
          <div className="member-list">
            {enEdition.membres.map((m, i) => (
              <div key={i} className="member-list__row">
                <Badge tone={TONE_PAR_TYPE[m.type]}>{libelleMembre(m, { professeurs, eleves, cours })}</Badge>
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => removeMembre(enEdition.id, m, i)}
                  aria-label="Retirer"
                >
                  <Icon name="x" size={16} />
                </button>
              </div>
            ))}
            {enEdition.membres.length === 0 && <p className="muted">Aucun membre pour l'instant.</p>}
          </div>
          <AddMembreForm
            professeurs={professeurs}
            eleves={eleves}
            cours={cours}
            onAdd={(membre) => addMembre(enEdition.id, membre)}
          />

          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={enEdition.whatsappStatut === 'cree'}
              disabled={enEdition.whatsappStatut === 'cree'}
              onChange={() => creerGroupeWhatsapp(enEdition.id)}
            />
            <Icon name="whatsapp" size={16} />
            {enEdition.whatsappStatut === 'cree' ? 'Groupe WhatsApp lié' : 'Créer un groupe WhatsApp lié'}
          </label>
        </Modal>
      )}

      {showAdd && (
        <Modal title="Créer une conversation" onClose={() => setShowAdd(false)}>
          <NewGroupeForm
            onCreate={async (nom, avecWhatsapp) => {
              const nouvelle = await conversationsApi.creerGroupe(ecoleId, nom)
              let miroir = nouvelle
              if (avecWhatsapp) {
                miroir = await conversationsApi.creerGroupeWhatsapp(nouvelle.id)
              }
              setGroupes((list) => [...list, { ...nouvelle, ...miroir }])
              setShowAdd(false)
            }}
          />
        </Modal>
      )}
    </div>
  )
}

function NewGroupeForm({ onCreate }) {
  const [nom, setNom] = useState('')
  const [avecWhatsapp, setAvecWhatsapp] = useState(false)

  function creer() {
    if (
      avecWhatsapp &&
      !window.confirm('Créer aussi un groupe WhatsApp lié à cette nouvelle conversation ?')
    ) {
      return
    }
    onCreate(nom, avecWhatsapp)
  }

  return (
    <>
      <label htmlFor="new-groupe-nom">Nom</label>
      <input id="new-groupe-nom" value={nom} onChange={(e) => setNom(e.target.value)} />

      <label className="checkbox-inline">
        <input type="checkbox" checked={avecWhatsapp} onChange={(e) => setAvecWhatsapp(e.target.checked)} />
        <Icon name="whatsapp" size={16} />
        Créer aussi un groupe WhatsApp lié
      </label>

      <button type="button" className="btn btn--primary btn--block" disabled={!nom} onClick={creer}>
        Créer
      </button>
    </>
  )
}

function AddMembreForm({ professeurs, eleves, cours, onAdd }) {
  const [type, setType] = useState('cours')
  const [id, setId] = useState(cours[0]?.id ?? '')

  const options =
    type === 'professeur' ? professeurs : type === 'eleve' ? eleves : type === 'cours' ? cours : null

  return (
    <div className="add-membre-form">
      <p className="add-membre-form__title">Ajouter un membre</p>
      <div className="segmented segmented--sm">
        {['admin', 'professeur', 'eleve', 'cours'].map((t) => (
          <button
            key={t}
            type="button"
            className={`segmented__option ${type === t ? 'is-active' : ''}`}
            onClick={() => {
              setType(t)
              if (t === 'professeur') setId(professeurs[0]?.id ?? '')
              if (t === 'eleve') setId(eleves[0]?.id ?? '')
              if (t === 'cours') setId(cours[0]?.id ?? '')
            }}
          >
            {t === 'admin' ? 'Admin' : t === 'professeur' ? 'Prof' : t === 'eleve' ? 'Élève' : 'Cours'}
          </button>
        ))}
      </div>

      {type === 'admin' ? (
        // ⚠️ Limitation connue (pré-existante) : id "admin1" en dur — il
        // n'existe pas encore d'écran pour choisir parmi plusieurs comptes
        // admin réels de l'école (une seule direction gérée pour l'instant,
        // voir spec/SPEC.md §8). À corriger le jour où le multi-admin est
        // géré côté backend/IHM — même limitation que le sélecteur de
        // profil famille en mode réel (voir App.jsx: activeUser).
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => onAdd({ type: 'admin', id: 'admin1', label: 'Direction' })}
        >
          Ajouter "Direction"
        </button>
      ) : (
        <div className="add-membre-form__row">
          <select value={id} onChange={(e) => setId(e.target.value)}>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {type === 'professeur' || type === 'eleve' ? `${o.prenom} ${o.nom}` : o.nom}
              </option>
            ))}
          </select>
          <button type="button" className="btn btn--secondary" onClick={() => onAdd({ type, id })}>
            Ajouter
          </button>
        </div>
      )}
    </div>
  )
}
