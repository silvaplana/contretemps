import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { normaliserRecherche } from '../../utils/recherche.js'
import { tousLesComptes, trierParNom } from './personnes.js'

// « Envoyer à… » (spec/modules/messagerie-instantanee.md §4.2 et §4.7) :
// commun à « Transférer » et au partage depuis une autre appli. Les
// discussions existantes, puis les contacts sans discussion à deux ; une
// case par ligne, « Envoyer (N) » toujours visible en bas.
// `onEnvoyer({ conversationIds, contacts })` reçoit la sélection.
export default function EnvoyerAScreen({ apercu, conversations, compteId, admins, professeurs, eleves, onBack, onEnvoyer }) {
  const [choisies, setChoisies] = useState(() => new Set()) // clés 'c<id>' (discussion) ou 'p<id>' (contact)
  const [recherche, setRecherche] = useState('')

  const avecDiscussion = new Set(
    conversations
      .filter((c) => c.type === 'individuelle')
      .flatMap((c) => c.membres.filter((m) => m.id !== compteId).map((m) => m.id)),
  )
  const contacts = trierParNom(
    tousLesComptes(admins, professeurs, eleves).filter((c) => c.id !== compteId && !avecDiscussion.has(c.id)),
  )
  const requete = normaliserRecherche(recherche.trim())
  const correspond = (nom) => !requete || normaliserRecherche(nom).includes(requete)
  const discussionsVisibles = conversations.filter((c) => correspond(c.nom ?? ''))
  const contactsVisibles = contacts.filter((c) => correspond(`${c.prenom} ${c.nom}`))

  function basculer(cle) {
    setChoisies((s) => {
      const copie = new Set(s)
      if (copie.has(cle)) copie.delete(cle)
      else copie.add(cle)
      return copie
    })
  }

  function envoyer() {
    onEnvoyer({
      conversationIds: conversations.filter((c) => choisies.has(`c${c.id}`)).map((c) => c.id),
      contacts: contacts.filter((c) => choisies.has(`p${c.id}`)),
    })
  }

  return (
    <div className="ecran-dessus">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Annuler">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className="thread-screen__header-text">
          <strong>Envoyer à…</strong>
          <span className="muted">{choisies.size} sélectionné{choisies.size > 1 ? 's' : ''}</span>
        </span>
      </div>

      <div className="ecran-dessus__liste">
        {apercu && <p className="envoyer-a__apercu">{apercu}</p>}
        <div className="search-bar choix-membres__recherche">
          <Icon name="search" size={18} />
          <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher" />
        </div>

        {discussionsVisibles.length > 0 && <p className="conversation-list__section">Discussions</p>}
        {discussionsVisibles.map((c) => (
          <label key={`c${c.id}`} className="choix-membres__ligne">
            <input type="checkbox" checked={choisies.has(`c${c.id}`)} onChange={() => basculer(`c${c.id}`)} />
            <span>{c.nom}</span>
          </label>
        ))}

        {contactsVisibles.length > 0 && <p className="conversation-list__section">Contacts</p>}
        {contactsVisibles.map((c) => (
          <label key={`p${c.id}`} className="choix-membres__ligne">
            <input type="checkbox" checked={choisies.has(`p${c.id}`)} onChange={() => basculer(`p${c.id}`)} />
            <span>
              {c.prenom} {c.nom}
            </span>
          </label>
        ))}
        {discussionsVisibles.length === 0 && contactsVisibles.length === 0 && <p className="muted">Aucun résultat.</p>}
      </div>

      <div className="ecran-dessus__pied">
        <button type="button" className="btn btn--primary btn--block" disabled={choisies.size === 0} onClick={envoyer}>
          Envoyer ({choisies.size})
        </button>
      </div>
    </div>
  )
}
