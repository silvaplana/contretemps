import AddMembreForm from '../../components/AddMembreForm.jsx'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'

export const TONE_PAR_TYPE = { admin: 'danger', professeur: 'success', eleve: 'neutral', cours: 'neutral' }

export function libelleMembre(membre, { admins = [], professeurs, eleves, cours }) {
  // `label` vient du backend pour un membre "compte" (nom/prénom déjà
  // résolus, voir api/conversations.js: versEcranAdmin) — absent pour un
  // membre "cours" (juste un id), d'où le repli ci-dessous sur les listes
  // déjà chargées par ailleurs.
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
export function nomAffiche(g, { cours }) {
  if (g.nom) return g.nom
  const blocCours = g.membres.length === 1 ? g.membres.find((m) => m.type === 'cours') : null
  return blocCours ? libelleMembre(blocCours, { cours }) : '(Sans nom)'
}

// Une conversation "vide" (ni nom, ni membre, ni groupe WhatsApp) — le cas
// juste après avoir cliqué "+" (voir AdminGroupes.jsx: creerConversation)
// et rien touché encore : jamais montrée dans la liste comme une vraie
// conversation, et nettoyée automatiquement si on ressort de sa modale
// sans rien y avoir mis (voir useConversationEditor.js: fermerEdition),
// pour ne pas laisser de conversations fantômes.
export function estVide(g) {
  return !g.nom && g.membres.length === 0 && g.whatsappStatut !== 'cree'
}

// Modale d'édition d'une conversation de groupe — partagée par Admin >
// Messagerie (AdminGroupes.jsx : "+", ou l'icône crayon d'une ligne
// existante) ET Admin > Cours (AdminCours.jsx : case "Créer aussi la
// conversation de groupe" à la création d'un cours, demande utilisateur
// du 2026-09-21 — reste sur Admin > Cours, ne bascule plus sur Admin >
// Messagerie pour ça).
//
// `nouvelle` : titre "Nouvelle conversation" décidé par l'APPELANT (voir
// useConversationEditor.js: setEditId), pas déduit de `estVide(conversation)`
// — celle-ci se base sur les membres actuels, or Admin > Cours pré-ajoute le
// professeur du cours AVANT même que la modale s'ouvre (voir AdminCours.jsx:
// addCours) : `estVide` y vaudrait déjà `false` au premier rendu, et le
// titre afficherait à tort "Modifier — (Sans nom)" pour une conversation
// que l'utilisateur vient tout juste de créer.
export default function ConversationEditModal({
  conversation,
  nouvelle,
  admins,
  professeurs,
  eleves,
  cours,
  onClose,
  onRename,
  onAddMembre,
  onRemoveMembre,
  onCreerGroupeWhatsapp,
}) {
  return (
    <Modal
      title={nouvelle ? 'Nouvelle conversation' : `Modifier — ${nomAffiche(conversation, { cours })}`}
      onClose={onClose}
      footer={
        // Nom/membres/WhatsApp sont déjà enregistrés au fil de l'eau
        // (voir onRename/onAddMembre/onRemoveMembre/onCreerGroupeWhatsapp
        // ci-dessous) — ce bouton ne fait qu'acter la fin de l'édition et
        // fermer la modale, comme le ferait la croix ou un clic à
        // l'extérieur, mais avec une action explicite (demande du
        // 2026-09-21 : il manquait un "Valider" en bas, comme dans la
        // modale d'ajout de cours).
        <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
          Valider
        </button>
      }
    >
      <label htmlFor="edit-groupe-nom">Nom</label>
      <input
        id="edit-groupe-nom"
        value={conversation.nom ?? ''}
        // Placeholder plutôt que value quand `nom` est vide (conversation
        // automatique de cours, voir nomAffiche ci-dessus) : le champ a
        // l'air vide (c'est le cas en base), mais indique quel nom
        // s'affiche par défaut dans la liste — pas de perte d'info.
        placeholder={conversation.nom ? undefined : nomAffiche(conversation, { cours })}
        onChange={(e) => onRename(e.target.value)}
      />

      <label>Personnes</label>
      <div className="member-list">
        {conversation.membres.map((m, i) => (
          <div key={i} className="member-list__row">
            <Badge tone={TONE_PAR_TYPE[m.type]}>{libelleMembre(m, { admins, professeurs, eleves, cours })}</Badge>
            <button type="button" className="icon-btn" onClick={() => onRemoveMembre(m, i)} aria-label="Retirer">
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
        {conversation.membres.length === 0 && <p className="muted">Aucun membre pour l'instant.</p>}
      </div>
      <AddMembreForm admins={admins} professeurs={professeurs} eleves={eleves} cours={cours} onAdd={onAddMembre} />

      <label className="checkbox-inline">
        <input
          type="checkbox"
          checked={conversation.whatsappStatut === 'cree'}
          disabled={conversation.whatsappStatut === 'cree'}
          onChange={onCreerGroupeWhatsapp}
        />
        <WhatsappBadge size={16} />
        {conversation.whatsappStatut === 'cree' ? 'Groupe WhatsApp lié' : 'Créer un groupe WhatsApp lié'}
      </label>
    </Modal>
  )
}
