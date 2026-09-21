import { useState } from 'react'
import * as conversationsApi from '../../api/conversations.js'
import * as messagesApi from '../../api/messages.js'
import AddMembreForm from '../../components/AddMembreForm.jsx'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { initialiserPresence } from '../../utils/presenceEnLigne.js'

const TONE_PAR_TYPE = { admin: 'danger', professeur: 'success', eleve: 'neutral', cours: 'neutral' }

function libelleMembre(membre, { admins, professeurs, eleves, cours }) {
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

// "Nouveau groupe" depuis Messagerie (menu 3 points, Admin seulement —
// voir App.jsx) — demande utilisateur du 2026-09-18. Contrairement à
// Admin > Messagerie (AdminGroupes.jsx : "+" crée tout de suite une
// conversation vide côté backend puis ouvre sa modale d'édition, chaque
// ajout de membre y persiste immédiatement, pas de bouton de validation),
// ici les membres restent EN LOCAL (staging) tant qu'on n'a pas cliqué
// "Créer le groupe" — un vrai bouton de validation finale, et rien n'est
// créé côté backend avant ce clic.
export default function NouveauGroupeModal({
  ecoleId,
  compteId,
  admins,
  professeurs,
  eleves,
  cours,
  onClose,
  onCree,
}) {
  const [nom, setNom] = useState('')
  const [membres, setMembres] = useState([]) // [{type, id}] — pas encore en base
  const [enCours, setEnCours] = useState(false)

  function ajouterMembre(membre) {
    if (membres.some((m) => m.type === membre.type && m.id === membre.id)) return
    setMembres((liste) => [...liste, membre])
  }

  function retirerMembre(index) {
    setMembres((liste) => liste.filter((_, i) => i !== index))
  }

  async function valider() {
    if (enCours || membres.length === 0 || !nom.trim()) return
    setEnCours(true)
    try {
      const conversation = await conversationsApi.creerGroupe(ecoleId, nom.trim())
      // Moi, le créateur, dois aussi être membre — sinon cette
      // conversation ne me serait plus jamais renvoyée par le backend au
      // prochain chargement (voir conversations.py: lister_du_compte),
      // même si je la vois tout de suite ici grâce à onCree ci-dessous.
      const estDejaMembre = membres.some((m) => m.type === 'admin' && m.id === compteId)
      const tousLesMembres = estDejaMembre ? membres : [...membres, { type: 'admin', id: compteId }]
      for (const membre of tousLesMembres) {
        await conversationsApi.ajouterMembre(conversation.id, membre)
      }
      // Reconstruit la conversation complète (forme Messagerie, voir
      // api/messages.js) plutôt que de l'assembler à la main ici — même
      // chemin que App.jsx quand un AUTRE membre est prévenu par SSE
      // (voir onConversationMaj), aucune divergence possible entre les
      // deux.
      const complete = await messagesApi.obtenirConversation(conversation.id, compteId, cours)
      initialiserPresence(complete.membres)
      onCree(complete)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Nouveau groupe"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={membres.length === 0 || !nom.trim() || enCours}
          onClick={valider}
        >
          Créer le groupe
        </button>
      }
    >
      <label htmlFor="nouveau-groupe-nom">Nom</label>
      <input
        id="nouveau-groupe-nom"
        value={nom}
        onChange={(e) => setNom(e.target.value)}
        placeholder="Nom du groupe"
      />

      <label>Personnes</label>
      <div className="member-list">
        {membres.map((m, i) => (
          <div key={`${m.type}-${m.id}`} className="member-list__row">
            <Badge tone={TONE_PAR_TYPE[m.type]}>{libelleMembre(m, { admins, professeurs, eleves, cours })}</Badge>
            <button type="button" className="icon-btn" onClick={() => retirerMembre(i)} aria-label="Retirer">
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
        {membres.length === 0 && <p className="muted">Aucun membre pour l'instant.</p>}
      </div>

      <AddMembreForm admins={admins} professeurs={professeurs} eleves={eleves} cours={cours} onAdd={ajouterMembre} />
    </Modal>
  )
}
