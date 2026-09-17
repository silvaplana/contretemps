import { useState } from 'react'
import { compterNonLus } from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'
import { normaliserRecherche } from '../../utils/recherche.js'

// Avatar Admin/Professeur dans une couleur distincte de celui d'un élève
// (décision utilisateur explicite, voir .avatar--staff dans App.css) —
// repris aussi par ProfilContactScreen.jsx.
function estStaff(role) {
  return role === 'admin' || role === 'professeur'
}

// Écran 1/2 de la Messagerie (voir spec/SPEC.md 5.5) : liste des
// conversations. Cliquer le TEXTE d'une ligne ouvre ConversationThreadScreen
// (voir MessagerieScreen.jsx) — comme la liste de discussions de WhatsApp.
// Cliquer l'AVATAR ouvre plutôt la "carte" du profil (voir
// ProfilContactScreen.jsx, `onAvatarClick`) — 2 zones de clic distinctes
// sur la même ligne, décision utilisateur explicite.
//
// Mode recherche façon WhatsApp (dès qu'on tape quelque chose dans la
// barre du haut) : 2 sections avec en-tête ("Discussions" puis
// "Contacts", même vocabulaire que la capture WhatsApp fournie par
// l'utilisateur), 3 catégories au total — 1) discussions individuelles
// existantes dont l'autre personne correspond, 2) discussions de groupe
// existantes dont le nom correspond (1 et 2 sous "Discussions"),
// 3) "Nouvelle discussion" sous "Contacts" — n'importe quel autre compte
// de l'école (admin/prof/élève, décision utilisateur : recherche globale
// pour tout le monde, pas seulement l'Admin) qui correspond et avec qui
// on n'a PAS déjà une conversation individuelle (sinon il apparaîtrait
// 2 fois : une fois en 1, une fois en 3). Cliquer le texte d'un résultat
// de la catégorie 3 crée (ou récupère, si elle existe déjà malgré tout)
// le DM (voir MessagerieScreen.jsx : onOpenContact) ; cliquer son avatar
// ouvre sa carte de profil comme pour les autres, SANS créer le DM tout
// de suite (voir ProfilContactScreen.jsx : le bouton "Message" s'en
// charge, seulement si on le demande vraiment).
export default function ConversationListScreen({
  conversations,
  onOpenConversation,
  onOpenContact,
  onAvatarClick,
  compteId,
  admins,
  professeurs,
  eleves,
  contactActionEnCours,
}) {
  const [recherche, setRecherche] = useState('')

  const requete = normaliserRecherche(recherche.trim())
  const enModeRecherche = requete !== ''

  if (!enModeRecherche) {
    return (
      <div className="conversation-list-screen">
        <BarreRecherche valeur={recherche} onChange={setRecherche} />
        {conversations.map((c) => (
          <LigneConversation
            key={c.id}
            conversation={c}
            compteId={compteId}
            onOpen={() => onOpenConversation(c.id)}
            onAvatarClick={() => onAvatarClick({ type: 'conversation', conversation: c })}
          />
        ))}
        {conversations.length === 0 && <p className="muted">Aucune conversation.</p>}
      </div>
    )
  }

  const discussionsIndividuelles = conversations.filter(
    (c) => c.type === 'individuelle' && normaliserRecherche(c.nom).includes(requete),
  )
  const discussionsGroupes = conversations.filter(
    (c) => c.type !== 'individuelle' && normaliserRecherche(c.nom).includes(requete),
  )
  // Déjà en DM avec moi (voir discussionsIndividuelles ci-dessus) — à
  // exclure des résultats "Nouvelle discussion", sinon la même personne
  // apparaîtrait 2 fois.
  const idsDejaEnDm = new Set(
    conversations
      .filter((c) => c.type === 'individuelle')
      .flatMap((c) => c.membres.map((m) => m.id)),
  )
  // `role` forcé explicitement : contrairement aux admins (déjà porté par
  // le backend, voir comptesApi.listerAdmins), ni professeurs.js ni
  // eleves.js n'exposent ce champ (pas besoin jusqu'ici) — la carte de
  // profil (voir ProfilContactScreen.jsx) en a besoin pour son sous-titre.
  const tousLesComptes = [
    ...admins.map((c) => ({ ...c, role: c.role ?? 'admin' })),
    ...professeurs.map((c) => ({ ...c, role: 'professeur' })),
    ...eleves.map((c) => ({ ...c, role: 'eleve' })),
  ]
  const nouveauxContacts = tousLesComptes.filter(
    (c) =>
      c.id !== compteId &&
      !idsDejaEnDm.has(c.id) &&
      normaliserRecherche(`${c.prenom} ${c.nom}`).includes(requete),
  )
  const aucunResultat =
    discussionsIndividuelles.length === 0 &&
    discussionsGroupes.length === 0 &&
    nouveauxContacts.length === 0

  const discussions = [...discussionsIndividuelles, ...discussionsGroupes]

  return (
    <div className="conversation-list-screen">
      <BarreRecherche valeur={recherche} onChange={setRecherche} />
      {/* En-têtes "Discussions"/"Contacts" façon WhatsApp — précisent si
          le résultat est une conversation déjà existante ou une personne
          pas encore contactée (voir LigneNouveauContact : cliquer son
          texte en crée une). Un en-tête seulement si sa catégorie a des
          résultats. */}
      {discussions.length > 0 && (
        <>
          <p className="conversation-list__section">Discussions</p>
          {discussions.map((c) => (
            <LigneConversation
              key={c.id}
              conversation={c}
              compteId={compteId}
              onOpen={() => onOpenConversation(c.id)}
              onAvatarClick={() => onAvatarClick({ type: 'conversation', conversation: c })}
            />
          ))}
        </>
      )}
      {nouveauxContacts.length > 0 && (
        <>
          <p className="conversation-list__section">Contacts</p>
          {nouveauxContacts.map((compte) => (
            <LigneNouveauContact
              key={compte.id}
              compte={compte}
              disabled={contactActionEnCours}
              onOpen={() => onOpenContact(compte)}
              onAvatarClick={() => onAvatarClick({ type: 'contact', compte })}
            />
          ))}
        </>
      )}
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

// Avatar et "reste de la ligne" sont 2 boutons indépendants côte à côte
// (pas un seul gros bouton comme avant) : l'avatar ouvre la carte de
// profil, le reste ouvre/crée la discussion — voir le commentaire en tête
// de fichier.
function LigneConversation({ conversation: c, compteId, onOpen, onAvatarClick }) {
  const last = c.messages[c.messages.length - 1]
  const nonLus = compterNonLus(c)
  // Rôle de l'AUTRE personne, pour la couleur d'avatar (voir estStaff) —
  // sans objet pour un groupe (.avatar--groupe prime de toute façon).
  const autre = c.type === 'individuelle' ? c.membres.find((m) => m.id !== compteId) : null
  const classeAvatar =
    c.type === 'groupe' ? 'avatar--groupe' : estStaff(autre?.role) ? 'avatar--staff' : ''
  return (
    <div className="conversation-list__item">
      <button
        type="button"
        className={`avatar avatar--sm conversation-list__avatar-btn ${classeAvatar}`}
        onClick={onAvatarClick}
        aria-label={`Profil de ${c.nom}`}
      >
        {c.type === 'groupe' ? <Icon name="users" size={16} /> : c.nom.slice(0, 2).toUpperCase()}
      </button>
      <button type="button" className="conversation-list__content" onClick={onOpen}>
        <span className="conversation-list__text">
          <strong>{c.nom}</strong>
          <span className="muted">{last?.contenu}</span>
        </span>
        {last?.envoyeParMail && <Icon name="mail" size={16} className="muted" />}
        {nonLus > 0 && <span className="conversation-list__badge">{nonLus}</span>}
      </button>
    </div>
  )
}

// Résultat "Nouvelle discussion" (catégorie 3, voir plus haut) : pas
// encore de dernier message à montrer (la conversation n'existe peut-être
// même pas encore côté backend) — ce sous-titre fixe en tient lieu.
function LigneNouveauContact({ compte, onOpen, onAvatarClick, disabled }) {
  return (
    <div className="conversation-list__item">
      <button
        type="button"
        className={`avatar avatar--sm conversation-list__avatar-btn ${estStaff(compte.role) ? 'avatar--staff' : ''}`}
        onClick={onAvatarClick}
        aria-label={`Profil de ${compte.prenom} ${compte.nom}`}
      >
        {`${compte.prenom[0] ?? ''}${compte.nom[0] ?? ''}`.toUpperCase()}
      </button>
      <button type="button" className="conversation-list__content" onClick={onOpen} disabled={disabled}>
        <span className="conversation-list__text">
          <strong>
            {compte.prenom} {compte.nom}
          </strong>
          <span className="muted">Nouvelle discussion</span>
        </span>
      </button>
    </div>
  )
}
