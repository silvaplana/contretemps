import { useState } from 'react'
import * as messagesApi from '../../api/messages.js'
import { compterNonLus } from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'

// Écran 1/2 de la Messagerie (voir spec/SPEC.md 5.5) : liste des
// conversations. Cliquer une conversation ouvre ConversationThreadScreen
// (voir MessagerieScreen.jsx) — comme la liste de discussions de WhatsApp.
//
// Mode recherche façon WhatsApp (dès qu'on tape quelque chose dans la
// barre du haut) : 3 catégories, dans cet ordre — 1) discussions
// individuelles existantes dont l'autre personne correspond,
// 2) discussions de groupe existantes dont le nom correspond,
// 3) "Nouvelle discussion" — n'importe quel autre compte de l'école
// (admin/prof/élève, décision utilisateur : recherche globale pour tout
// le monde, pas seulement l'Admin) qui correspond et avec qui on n'a PAS
// déjà une conversation individuelle (sinon il apparaîtrait 2 fois : une
// fois en 1, une fois en 3). Cliquer un résultat de la catégorie 3 crée
// (ou récupère, si elle existe déjà malgré tout) le DM via l'API avant de
// l'ouvrir (voir messagesApi.creerOuObtenirDm).
export default function ConversationListScreen({
  conversations,
  setConversations,
  onSelect,
  compteId,
  ecoleId,
  admins,
  professeurs,
  eleves,
}) {
  const [recherche, setRecherche] = useState('')
  // Garde-fou contre un double-clic sur "Nouvelle discussion" pendant que
  // l'appel réseau est en cours (même principe qu'ailleurs dans l'appli,
  // voir AdminCours.jsx/AdminEleves.jsx).
  const [creationEnCours, setCreationEnCours] = useState(false)

  const requete = recherche.trim().toLowerCase()
  const enModeRecherche = requete !== ''

  async function ouvrirNouvelleDiscussion(compte) {
    if (creationEnCours) return
    setCreationEnCours(true)
    try {
      const conv = await messagesApi.creerOuObtenirDm(ecoleId, compteId, compte.id)
      setConversations((liste) => (liste.some((c) => c.id === conv.id) ? liste : [...liste, conv]))
      onSelect(conv.id)
    } finally {
      setCreationEnCours(false)
    }
  }

  if (!enModeRecherche) {
    return (
      <div className="conversation-list-screen">
        <BarreRecherche valeur={recherche} onChange={setRecherche} />
        {conversations.map((c) => (
          <LigneConversation key={c.id} conversation={c} onClick={() => onSelect(c.id)} />
        ))}
        {conversations.length === 0 && <p className="muted">Aucune conversation.</p>}
      </div>
    )
  }

  const discussionsIndividuelles = conversations.filter(
    (c) => c.type === 'individuelle' && c.nom.toLowerCase().includes(requete),
  )
  const discussionsGroupes = conversations.filter(
    (c) => c.type !== 'individuelle' && c.nom.toLowerCase().includes(requete),
  )
  // Déjà en DM avec moi (voir discussionsIndividuelles ci-dessus) — à
  // exclure des résultats "Nouvelle discussion", sinon la même personne
  // apparaîtrait 2 fois.
  const idsDejaEnDm = new Set(
    conversations
      .filter((c) => c.type === 'individuelle')
      .flatMap((c) => c.membres.map((m) => m.id)),
  )
  const nouveauxContacts = [...admins, ...professeurs, ...eleves].filter(
    (c) =>
      c.id !== compteId &&
      !idsDejaEnDm.has(c.id) &&
      `${c.prenom} ${c.nom}`.toLowerCase().includes(requete),
  )
  const aucunResultat =
    discussionsIndividuelles.length === 0 &&
    discussionsGroupes.length === 0 &&
    nouveauxContacts.length === 0

  return (
    <div className="conversation-list-screen">
      <BarreRecherche valeur={recherche} onChange={setRecherche} />
      {[...discussionsIndividuelles, ...discussionsGroupes].map((c) => (
        <LigneConversation key={c.id} conversation={c} onClick={() => onSelect(c.id)} />
      ))}
      {nouveauxContacts.map((compte) => (
        <LigneNouveauContact
          key={compte.id}
          compte={compte}
          disabled={creationEnCours}
          onClick={() => ouvrirNouvelleDiscussion(compte)}
        />
      ))}
      {aucunResultat && <p className="muted">Aucun résultat.</p>}
    </div>
  )
}

// Icône loupe hors recherche ; flèche de retour (efface la recherche,
// donc revient au mode par défaut ci-dessus) dès qu'on a tapé quelque
// chose — même bascule que WhatsApp.
function BarreRecherche({ valeur, onChange }) {
  const actif = valeur.trim() !== ''
  return (
    <div className="search-bar conversation-list__search">
      {actif ? (
        <button
          type="button"
          className="icon-btn icon-btn--sm"
          onClick={() => onChange('')}
          aria-label="Revenir aux conversations"
        >
          <Icon name="chevronLeft" size={18} />
        </button>
      ) : (
        <Icon name="search" size={18} />
      )}
      <input
        value={valeur}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Rechercher une discussion ou une personne"
      />
    </div>
  )
}

function LigneConversation({ conversation: c, onClick }) {
  const last = c.messages[c.messages.length - 1]
  const nonLus = compterNonLus(c)
  return (
    <button type="button" className="conversation-list__item" onClick={onClick}>
      <span className={`avatar avatar--sm ${c.type === 'groupe' ? 'avatar--groupe' : ''}`}>
        {c.type === 'groupe' ? <Icon name="users" size={16} /> : c.nom.slice(0, 2).toUpperCase()}
      </span>
      <span className="conversation-list__text">
        <strong>{c.nom}</strong>
        <span className="muted">{last?.contenu}</span>
      </span>
      {last?.envoyeParMail && <Icon name="mail" size={16} className="muted" />}
      {nonLus > 0 && <span className="conversation-list__badge">{nonLus}</span>}
    </button>
  )
}

// Résultat "Nouvelle discussion" (catégorie 3, voir plus haut) : pas
// encore de dernier message à montrer (la conversation n'existe peut-être
// même pas encore côté backend) — ce sous-titre fixe en tient lieu.
function LigneNouveauContact({ compte, onClick, disabled }) {
  return (
    <button type="button" className="conversation-list__item" onClick={onClick} disabled={disabled}>
      <span className="avatar avatar--sm">
        {`${compte.prenom[0] ?? ''}${compte.nom[0] ?? ''}`.toUpperCase()}
      </span>
      <span className="conversation-list__text">
        <strong>
          {compte.prenom} {compte.nom}
        </strong>
        <span className="muted">Nouvelle discussion</span>
      </span>
    </button>
  )
}
