import { useState } from 'react'
import { ROLE_LABEL } from '../../data/roles.js'
import Icon from '../../components/Icon.jsx'

// "Carte" de profil (voir ConversationListScreen.jsx : cliquer l'avatar
// d'une ligne l'ouvre) — inspirée d'une capture WhatsApp fournie par
// l'utilisateur (fiche d'un contact/groupe partagé) : avatar en grand,
// nom, et seulement 2 actions — "Message" (ouvre/crée la discussion) et
// "i" (bascule sur un 2e écran, plus détaillé — la liste des membres pour
// un groupe, voir InfosProfil ci-dessous).
//
// `cible` (voir MessagerieScreen.jsx) :
//   { type: 'conversation', conversation }  — discussion déjà existante
//   { type: 'contact', compte }             — pas encore de discussion
export default function ProfilContactScreen({ cible, compteId, onBack, onMessage, contacterEnCours }) {
  const [vueInfos, setVueInfos] = useState(false)
  const { nom, sousTitre, estGroupe, initiales, membres } = resoudreAffichage(cible, compteId)

  const avatar = (
    <span className={`avatar avatar--lg ${estGroupe ? 'avatar--groupe' : ''}`}>
      {estGroupe ? <Icon name="users" size={40} /> : initiales}
    </span>
  )

  if (vueInfos) {
    return (
      <div className="thread-screen">
        <EnTete titre="Infos" onBack={() => setVueInfos(false)} />
        <div className="profil-contact-screen__body">
          {avatar}
          <h2>{nom}</h2>
          {sousTitre && <p className="muted">{sousTitre}</p>}
          {membres && (
            <div className="profil-contact-screen__membres">
              <p className="conversation-list__section">
                {membres.length} membre{membres.length > 1 ? 's' : ''}
              </p>
              {membres.map((m) => (
                <div key={m.id} className="profil-contact-screen__membre">
                  <span className="avatar avatar--sm">
                    {`${m.prenom[0] ?? ''}${m.nom[0] ?? ''}`.toUpperCase()}
                  </span>
                  <span className="profil-contact-screen__membre-nom">
                    {m.prenom} {m.nom}
                  </span>
                  <span className="muted">{ROLE_LABEL[m.role] ?? m.role}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="thread-screen">
      <EnTete titre={nom} onBack={onBack} />
      <div className="profil-contact-screen__body">
        {avatar}
        <h2>{nom}</h2>
        {sousTitre && <p className="muted">{sousTitre}</p>}
        <div className="profil-contact-screen__actions">
          <button
            type="button"
            className="profil-contact-screen__action"
            onClick={onMessage}
            disabled={contacterEnCours}
          >
            <span className="icon-btn icon-btn--accent">
              <Icon name="messagerie" size={22} />
            </span>
            Message
          </button>
          <button type="button" className="profil-contact-screen__action" onClick={() => setVueInfos(true)}>
            <span className="icon-btn icon-btn--accent">
              <Icon name="info" size={22} />
            </span>
            Infos
          </button>
        </div>
      </div>
    </div>
  )
}

function EnTete({ titre, onBack }) {
  return (
    <div className="thread-screen__header">
      <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
        <Icon name="chevronLeft" size={20} />
      </button>
      <strong>{titre}</strong>
    </div>
  )
}

// Une conversation de groupe porte déjà tout (nom, membres résolus, voir
// api/messages.js) ; un contact brut (pas encore de discussion) n'a que
// nom/prénom/role — pas de liste de membres à afficher pour lui, il EST
// la personne.
function resoudreAffichage(cible, compteId) {
  if (cible.type === 'conversation') {
    const c = cible.conversation
    if (c.type === 'individuelle') {
      const autre = c.membres.find((m) => m.id !== compteId)
      return {
        nom: c.nom,
        sousTitre: autre ? ROLE_LABEL[autre.role] : undefined,
        estGroupe: false,
        initiales: c.nom.slice(0, 2).toUpperCase(),
        membres: null,
      }
    }
    return {
      nom: c.nom,
      sousTitre: undefined,
      estGroupe: true,
      initiales: null,
      membres: c.membres,
    }
  }
  const p = cible.compte
  return {
    nom: `${p.prenom} ${p.nom}`,
    sousTitre: ROLE_LABEL[p.role],
    estGroupe: false,
    initiales: `${p.prenom[0] ?? ''}${p.nom[0] ?? ''}`.toUpperCase(),
    membres: null,
  }
}
