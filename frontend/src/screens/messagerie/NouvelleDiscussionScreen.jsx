import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { normaliserRecherche } from '../../utils/recherche.js'
import { estStaff, initiales, tousLesComptes, trierParNom } from './personnes.js'

const ROLE_LIBELLE = { admin: 'Admin', professeur: 'Professeur' }

// Sous-titre d'un contact (spec §2.3) : son rôle, ou les cours d'un élève.
function sousTitre(compte, cours) {
  if (ROLE_LIBELLE[compte.role]) return ROLE_LIBELLE[compte.role]
  const noms = cours.filter((c) => compte.coursIds?.includes(c.id)).map((c) => c.nom)
  return noms.length > 0 ? noms.join(', ') : 'Élève'
}

// Écran « Nouvelle discussion », ouvert par le bouton + de la liste des
// conversations (spec/modules/messagerie-instantanee.md §2), sur le modèle
// de « Sélectionner un contact » de WhatsApp : « Nouveau groupe » (admins),
// puis tous les membres de l'école par ordre alphabétique. Toucher le nom
// ouvre (ou crée) la discussion à deux, toucher l'avatar ouvre la carte.
export default function NouvelleDiscussionScreen({
  compteId,
  admins,
  professeurs,
  eleves,
  cours,
  peutCreerGroupe,
  onBack,
  onNouveauGroupe,
  onOpenContact,
  onAvatarClick,
  contactActionEnCours,
}) {
  const [recherche, setRecherche] = useState(null) // null : loupe fermée

  const contacts = trierParNom(tousLesComptes(admins, professeurs, eleves).filter((c) => c.id !== compteId))
  const requete = normaliserRecherche((recherche ?? '').trim())
  const visibles = requete
    ? contacts.filter((c) => normaliserRecherche(`${c.prenom} ${c.nom}`).includes(requete))
    : contacts

  return (
    <div className="thread-screen">
      <div className="thread-screen__header">
        {recherche === null ? (
          <>
            <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux conversations">
              <Icon name="chevronLeft" size={22} />
            </button>
            <span className="thread-screen__header-text nouvelle-discussion__titre">
              <strong>Nouvelle discussion</strong>
              <span className="muted">
                {contacts.length} contact{contacts.length > 1 ? 's' : ''}
              </span>
            </span>
            <button type="button" className="icon-btn" onClick={() => setRecherche('')} aria-label="Rechercher">
              <Icon name="search" size={22} />
            </button>
          </>
        ) : (
          <>
            <button type="button" className="icon-btn" onClick={() => setRecherche(null)} aria-label="Fermer la recherche">
              <Icon name="chevronLeft" size={22} />
            </button>
            <input
              className="nouvelle-discussion__recherche"
              autoFocus
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              placeholder="Rechercher un contact"
            />
          </>
        )}
      </div>

      <div className="conversation-list-screen">
        {peutCreerGroupe && !requete && (
          <div className="conversation-list__item">
            <button type="button" className="conversation-list__content nouvelle-discussion__action" onClick={onNouveauGroupe}>
              <span className="avatar nouvelle-discussion__rond">
                <Icon name="users" size={22} />
              </span>
              <strong>Nouveau groupe</strong>
            </button>
          </div>
        )}

        <p className="conversation-list__section">Contacts</p>
        {visibles.map((compte) => (
          <div key={compte.id} className="conversation-list__item nouvelle-discussion__ligne">
            <button
              type="button"
              className={`avatar nouvelle-discussion__rond conversation-list__avatar-btn ${estStaff(compte.role) ? 'avatar--staff' : ''}`}
              onClick={() => onAvatarClick(compte)}
              aria-label={`Profil de ${compte.prenom} ${compte.nom}`}
            >
              {initiales(compte)}
            </button>
            <button
              type="button"
              className="conversation-list__content"
              disabled={contactActionEnCours}
              onClick={() => onOpenContact(compte)}
            >
              <span className="conversation-list__text">
                <strong>
                  {compte.prenom} {compte.nom}
                </strong>
                <span className="muted">{sousTitre(compte, cours)}</span>
              </span>
            </button>
          </div>
        ))}
        {visibles.length === 0 && <p className="muted">Aucun contact ne correspond.</p>}
      </div>
    </div>
  )
}
