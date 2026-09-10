import { useEffect, useState } from 'react'
import * as comptesApi from '../../api/comptes.js'
import * as conversationsApi from '../../api/conversations.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'

const TONE_PAR_TYPE = { admin: 'danger', professeur: 'success', eleve: 'neutral', cours: 'neutral' }

function libelleMembre(membre, { admins = [], professeurs, eleves, cours }) {
  // `label` vient du backend réel (nom/prénom déjà résolus, voir
  // api/conversations.js: versEcranAdmin) — sinon (maquette), on retombe
  // sur les listes déjà chargées par ailleurs.
  if (membre.label) return membre.label
  if (membre.type === 'admin') {
    const a = admins.find((x) => x.id === membre.id)
    return a ? `${a.prenom} ${a.nom}` : '?'
  }
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

// Une conversation automatique de cours (voir spec/SPEC.md §6.9 : "chaque
// cours a sa propre conversation de groupe automatique") n'a PAS de `nom`
// propre en base — c'est le cours qui la nomme implicitement. Sans ce
// repli, la colonne "Nom" reste vide (déjà vu : confondu avec une
// conversation "mal construite", alors que ses membres s'affichent bien).
function nomAffiche(g, { cours }) {
  if (g.nom) return g.nom
  const blocCours = g.membres.length === 1 ? g.membres.find((m) => m.type === 'cours') : null
  return blocCours ? libelleMembre(blocCours, { cours }) : '(Sans nom)'
}

// Une conversation "vide" (ni nom, ni membre, ni groupe WhatsApp) — le cas
// juste après avoir cliqué "+" (voir creerConversation) et rien touché
// encore : jamais montrée dans la liste comme une vraie conversation, et
// nettoyée automatiquement si on ressort de sa modale sans rien y avoir mis
// (voir fermerEdition), pour ne pas laisser de conversations fantômes.
function estVide(g) {
  return !g.nom && g.membres.length === 0 && g.whatsappStatut !== 'cree'
}

// Onglet Admin > Conversations (voir spec/SPEC.md §5.1.5 et §6.9). Une
// conversation se compose de blocs "Compte" (admin/professeur/élève
// individuel) et "Cours" (résout automatiquement tous ses élèves inscrits
// et son/ses professeur(s)).
//
// Création ET édition partagent la même modale (demande) : "+" crée tout
// de suite une conversation vide côté backend puis ouvre sa modale
// d'édition — pas de formulaire de création séparé, pour ne jamais avoir à
// maintenir deux fois la même logique nom/membres/WhatsApp.
//
// Groupe WhatsApp miroir (§6.9) : icône dans la liste + case à cocher —
// toujours avec confirmation avant le vrai appel, puisque la création
// n'est pas réversible depuis cet écran (pas de "détacher" pour
// l'instant), voir conversationsApi.creerGroupeWhatsapp — stub côté
// backend, pas encore branché sur un vrai client WhatsApp.
export default function AdminGroupes({ groupes, setGroupes, professeurs, eleves, cours, ecoleId }) {
  const [search, setSearch] = useState('')
  const [editId, setEditId] = useState(null)
  const [admins, setAdmins] = useState([])

  // Uniquement utile ici (voir AddMembreForm : "Ajouter un membre" >
  // Admin) — pas besoin de faire remonter ça jusqu'à App.jsx comme
  // eleves/professeurs/cours, qui servent à plusieurs écrans.
  useEffect(() => {
    comptesApi.listerAdmins(ecoleId).then(setAdmins)
  }, [ecoleId])

  const filtered = groupes.filter(
    (g) => !estVide(g) && nomAffiche(g, { cours }).toLowerCase().includes(search.toLowerCase()),
  )
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

  async function creerConversation() {
    const nouvelle = await conversationsApi.creerGroupe(ecoleId, '')
    setGroupes((list) => [...list, nouvelle])
    setEditId(nouvelle.id)
  }

  // Referme la modale — supprime la conversation si elle est ressortie
  // vide (voir estVide), pour ne jamais laisser une conversation fantôme
  // créée par erreur (clic sur "+" puis "Fermer" sans rien remplir).
  async function fermerEdition() {
    if (enEdition && estVide(enEdition)) {
      await conversationsApi.supprimer(enEdition.id)
      setGroupes((list) => list.filter((g) => g.id !== enEdition.id))
    }
    setEditId(null)
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
                <td className="data-table__name">{nomAffiche(g, { cours })}</td>
                <td>
                  <div className="badge-list">
                    {g.membres.map((m, i) => (
                      <Badge key={i} tone={TONE_PAR_TYPE[m.type]}>
                        {m.type === 'cours' && <Icon name="users" size={12} />}
                        {libelleMembre(m, { admins, professeurs, eleves, cours })}
                      </Badge>
                    ))}
                    {g.membres.length === 0 && <span className="muted">—</span>}
                  </div>
                </td>
                <td>
                  {g.whatsappStatut === 'cree' && (
                    <span title="Groupe WhatsApp lié">
                      <WhatsappBadge size={20} />
                    </span>
                  )}
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={() => setEditId(g.id)}
                      aria-label={`Modifier ${nomAffiche(g, { cours })}`}
                    >
                      <Icon name="edit" size={18} />
                    </button>
                    <button
                      type="button"
                      className="icon-btn icon-btn--danger"
                      onClick={() => removeGroupe(g.id)}
                      aria-label={`Supprimer ${nomAffiche(g, { cours })}`}
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

      <button type="button" className="fab" onClick={creerConversation} aria-label="Créer une conversation">
        <Icon name="plus" size={24} />
      </button>

      {enEdition && (
        <Modal
          title={estVide(enEdition) ? 'Nouvelle conversation' : `Modifier — ${nomAffiche(enEdition, { cours })}`}
          onClose={fermerEdition}
        >
          <label htmlFor="edit-groupe-nom">Nom</label>
          <input
            id="edit-groupe-nom"
            value={enEdition.nom ?? ''}
            // Placeholder plutôt que value quand `nom` est vide (conversation
            // automatique de cours, voir nomAffiche ci-dessus) : le champ a
            // l'air vide (c'est le cas en base), mais indique quel nom
            // s'affiche par défaut dans la liste — pas de perte d'info.
            placeholder={enEdition.nom ? undefined : nomAffiche(enEdition, { cours })}
            onChange={(e) => renameGroupe(enEdition.id, e.target.value)}
          />

          <label>Personnes</label>
          <div className="member-list">
            {enEdition.membres.map((m, i) => (
              <div key={i} className="member-list__row">
                <Badge tone={TONE_PAR_TYPE[m.type]}>{libelleMembre(m, { admins, professeurs, eleves, cours })}</Badge>
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
            admins={admins}
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
            <WhatsappBadge size={16} />
            {enEdition.whatsappStatut === 'cree' ? 'Groupe WhatsApp lié' : 'Créer un groupe WhatsApp lié'}
          </label>
        </Modal>
      )}
    </div>
  )
}

function AddMembreForm({ admins, professeurs, eleves, cours, onAdd }) {
  const [type, setType] = useState('cours')
  const [id, setId] = useState(cours[0]?.id ?? '')

  const OPTIONS_PAR_TYPE = { admin: admins, professeur: professeurs, eleve: eleves, cours }
  const options = OPTIONS_PAR_TYPE[type]

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
              setId(OPTIONS_PAR_TYPE[t][0]?.id ?? '')
            }}
          >
            {t === 'admin' ? 'Admin' : t === 'professeur' ? 'Prof' : t === 'eleve' ? 'Élève' : 'Cours'}
          </button>
        ))}
      </div>

      <div className="add-membre-form__row">
        <select value={id} onChange={(e) => setId(e.target.value)}>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {type === 'cours' ? o.nom : `${o.prenom} ${o.nom}`}
            </option>
          ))}
          {options.length === 0 && <option value="">Aucun</option>}
        </select>
        <button type="button" className="btn btn--secondary" disabled={!id} onClick={() => onAdd({ type, id })}>
          Ajouter
        </button>
      </div>
    </div>
  )
}
