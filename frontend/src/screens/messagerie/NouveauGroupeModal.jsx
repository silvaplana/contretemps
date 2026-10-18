import { useState } from 'react'
import * as conversationsApi from '../../api/conversations.js'
import * as messagesApi from '../../api/messages.js'
import Badge from '../../components/Badge.jsx'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { initialiserPresence } from '../../utils/presenceEnLigne.js'
import ChoixMembresScreen from './ChoixMembresScreen.jsx'
import { personnesDuGroupe } from './personnes.js'
import QuiEstDansLeGroupeScreen from './QuiEstDansLeGroupeScreen.jsx'

const TONE_PAR_TYPE = { admin: 'danger', professeur: 'success', eleve: 'neutral', cours: 'neutral' }

// Sélecteur de « Ajouter un membre » (spec/modules/messagerie-instantanee.md
// §3.4-3.5) : « Tous » ajoute tout le monde d'un coup, les autres ouvrent
// le choix multiple (ChoixMembresScreen.jsx).
const SEGMENTS = [
  ['tous', 'Tous'],
  ['admin', 'Admin'],
  ['professeur', 'Prof'],
  ['eleve', 'Élève'],
  ['cours', 'Cours'],
]
const CHOISIR = {
  admin: 'Choisir des admins',
  professeur: 'Choisir des profs',
  eleve: 'Choisir des élèves',
  cours: 'Choisir des cours',
}

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
//
// Depuis le 18 octobre (spec/modules/messagerie-instantanee.md §3) :
// ouverte par « Nouveau groupe » de l'écran Nouvelle discussion ; choix
// multiple par écran plein, « Tous », et l'œil « Qui est dans le groupe ? »
// qui met tout le monde à plat.
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
  const [segment, setSegment] = useState('tous')
  // Écran plein par-dessus la fenêtre : 'qui' (l'œil) ou un type à choisir.
  const [ecran, setEcran] = useState(null)

  const OPTIONS_PAR_TYPE = { admin: admins, professeur: professeurs, eleve: eleves, cours }
  const personnes = personnesDuGroupe(membres, { admins, professeurs, eleves, cours, compteId })
  // Le créateur, toujours ajouté, ne compte pas tant qu'il n'y a personne.
  const nbTouches = membres.length === 0 ? 0 : personnes.length

  // « Tous » (§3.4) : chaque personne ajoutée une par une, sans doublon,
  // pour pouvoir en retirer ensuite. Photo du moment, pas un lien.
  function ajouterToutLeMonde() {
    setMembres((liste) => {
      const dejaLa = new Set(liste.filter((m) => m.type !== 'cours').map((m) => m.id))
      const ajouts = []
      for (const [type, comptes] of [
        ['admin', admins],
        ['professeur', professeurs],
        ['eleve', eleves],
      ]) {
        for (const c of comptes) {
          if (dejaLa.has(c.id)) continue
          dejaLa.add(c.id)
          ajouts.push({ type, id: c.id })
        }
      }
      return [...liste, ...ajouts]
    })
  }

  // Retour du choix multiple (§3.5) : la sélection remplace les membres de
  // ce type ; ceux qui restent gardent leur place.
  function validerChoix(type, ids) {
    const garde = new Set(ids)
    setMembres((liste) => {
      const restants = liste.filter((m) => m.type !== type || garde.has(m.id))
      const presents = new Set(restants.filter((m) => m.type === type).map((m) => m.id))
      return [...restants, ...ids.filter((id) => !presents.has(id)).map((id) => ({ type, id }))]
    })
    setEcran(null)
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

  if (ecran === 'qui') {
    return <QuiEstDansLeGroupeScreen personnes={personnes} onBack={() => setEcran(null)} />
  }
  if (ecran) {
    return (
      <ChoixMembresScreen
        type={ecran}
        options={OPTIONS_PAR_TYPE[ecran]}
        dejaChoisis={membres.filter((m) => m.type === ecran).map((m) => m.id)}
        onValider={(ids) => validerChoix(ecran, ids)}
        onBack={() => setEcran(null)}
      />
    )
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

      <div className="nouveau-groupe__personnes">
        <label>Personnes</label>
        <button
          type="button"
          className="nouveau-groupe__oeil"
          disabled={membres.length === 0}
          onClick={() => setEcran('qui')}
          aria-label="Qui est dans le groupe ?"
          title="Qui est dans le groupe ?"
        >
          <Icon name="eye" size={20} /> {nbTouches}
        </button>
      </div>
      <div className="member-list">
        {membres.map((m) => (
          <div key={`${m.type}-${m.id}`} className="member-list__row">
            <Badge tone={TONE_PAR_TYPE[m.type]}>{libelleMembre(m, { admins, professeurs, eleves, cours })}</Badge>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setMembres((liste) => liste.filter((x) => x !== m))}
              aria-label="Retirer"
            >
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
        {membres.length === 0 && <p className="muted">Aucun membre pour l'instant.</p>}
      </div>

      <div className="add-membre-form">
        <p className="add-membre-form__title">Ajouter un membre</p>
        <div className="segmented segmented--sm">
          {SEGMENTS.map(([t, libelle]) => (
            <button
              key={t}
              type="button"
              className={`segmented__option ${segment === t ? 'is-active' : ''}`}
              onClick={() => {
                setSegment(t)
                if (t !== 'tous') setEcran(t)
              }}
            >
              {libelle}
            </button>
          ))}
        </div>
        {segment === 'tous' ? (
          <button type="button" className="btn btn--secondary btn--block" onClick={ajouterToutLeMonde}>
            Ajouter tout le monde
          </button>
        ) : (
          <button type="button" className="btn btn--secondary btn--block" onClick={() => setEcran(segment)}>
            {CHOISIR[segment]}
          </button>
        )}
      </div>
    </Modal>
  )
}
