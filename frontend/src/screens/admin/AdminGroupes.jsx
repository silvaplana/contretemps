import { useEffect, useState } from 'react'
import * as comptesApi from '../../api/comptes.js'
import * as conversationsApi from '../../api/conversations.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'
import { correspond } from '../../utils/recherche.js'
import ConversationEditModal, { TONE_PAR_TYPE, estVide, libelleMembre, nomAffiche } from './ConversationEditModal.jsx'
import { useConversationEditor } from './useConversationEditor.js'

// Onglet Admin > Messagerie (voir spec/SPEC.md §5.1.5 et §6.9). Une
// conversation se compose de blocs "Compte" (admin/professeur/élève
// individuel) et "Cours" (résout automatiquement tous ses élèves inscrits
// et son/ses professeur(s)).
//
// Création ET édition partagent la même modale (demande) : "+" crée tout
// de suite une conversation vide côté backend puis ouvre sa modale
// d'édition — pas de formulaire de création séparé, pour ne jamais avoir à
// maintenir deux fois la même logique nom/membres/WhatsApp. Cette modale
// est aussi ouverte depuis Admin > Cours (voir AdminCours.jsx) sans
// quitter cet onglet-ci — voir ConversationEditModal.jsx et
// useConversationEditor.js, partagés entre les deux écrans.
//
// Groupe WhatsApp miroir (§6.9) : icône dans la liste + case à cocher —
// toujours avec confirmation avant le vrai appel, puisque la création
// n'est pas réversible depuis cet écran (pas de "détacher" pour
// l'instant), voir conversationsApi.creerGroupeWhatsapp — stub côté
// backend, pas encore branché sur un vrai client WhatsApp.
export default function AdminGroupes({ groupes, setGroupes, professeurs, eleves, cours, ecoleId }) {
  const [search, setSearch] = useState('')
  const [admins, setAdmins] = useState([])
  const { setEditId, enEdition, nouvelle, renameGroupe, addMembre, removeMembre, creerGroupeWhatsapp, fermerEdition } =
    useConversationEditor(groupes, setGroupes)

  // Uniquement utile ici (voir AddMembreForm : "Ajouter un membre" >
  // Admin) — pas besoin de faire remonter ça jusqu'à App.jsx comme
  // eleves/professeurs/cours, qui servent à plusieurs écrans.
  useEffect(() => {
    comptesApi.listerAdmins(ecoleId).then(setAdmins)
  }, [ecoleId])

  const filtered = groupes.filter((g) => !estVide(g) && correspond(nomAffiche(g, { cours }), search))

  async function removeGroupe(id) {
    if (!window.confirm('Supprimer cette conversation ?')) return
    await conversationsApi.supprimer(id)
    setGroupes((list) => list.filter((g) => g.id !== id))
  }

  async function creerConversation() {
    const conversation = await conversationsApi.creerGroupe(ecoleId, '')
    setGroupes((list) => [...list, conversation])
    setEditId(conversation.id, { nouvelle: true })
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

      {/* Précise ce que contient cet onglet (renommé "Messagerie", voir
          AdminScreen.jsx) — même vocabulaire/classe que l'en-tête
          "Discussions" du mode recherche de Messagerie, voir
          ConversationListScreen.jsx : uniquement les discussions de
          GROUPE, pas les DM (individuelles), qui ne passent jamais par
          cet écran. */}
      <p className="conversation-list__section">Discussions de groupe</p>

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
        <ConversationEditModal
          conversation={enEdition}
          nouvelle={nouvelle}
          admins={admins}
          professeurs={professeurs}
          eleves={eleves}
          cours={cours}
          onClose={fermerEdition}
          onRename={(nom) => renameGroupe(enEdition.id, nom)}
          onAddMembre={(membre) => addMembre(enEdition.id, membre)}
          onRemoveMembre={(membre, index) => removeMembre(enEdition.id, membre, index)}
          onCreerGroupeWhatsapp={() => creerGroupeWhatsapp(enEdition.id)}
        />
      )}
    </div>
  )
}
