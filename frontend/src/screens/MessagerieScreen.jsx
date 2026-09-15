import { useState } from 'react'
import * as messagesApi from '../api/messages.js'
import ConversationListScreen from './messagerie/ConversationListScreen.jsx'
import ConversationThreadScreen from './messagerie/ConversationThreadScreen.jsx'
import ProfilContactScreen from './messagerie/ProfilContactScreen.jsx'

// Écran Messagerie (Admin, Professeur, Élève — voir spec/SPEC.md 5.5).
// 3 écrans distincts, comme WhatsApp, jamais 2 affichés en même temps :
// - la liste des conversations (état par défaut) ;
// - (clic sur le TEXTE d'une ligne) le fil d'une conversation en plein
//   écran, avec une flèche de retour ;
// - (clic sur l'AVATAR d'une ligne) la "carte" du profil correspondant
//   (voir ProfilContactScreen.jsx), avec ses 2 actions Message/Infos.
//
// La carte de profil peut elle-même en empiler une autre : depuis la
// fiche "Infos" d'un groupe (Admin/Professeur seulement, voir
// ProfilContactScreen.jsx), cliquer l'icône d'un membre ouvre SA fiche
// "Infos" par-dessus — d'où `profilStack` (pas un simple `profilCible`) :
// chaque frame retient sa propre cible ET si elle était en carte ou en
// infos, pour qu'un retour arrière restaure exactement l'état précédent
// (ex. retour d'un membre → liste des membres du groupe, pas sa carte).
export default function MessagerieScreen({
  conversations,
  setConversations,
  compteId,
  viewerRole,
  ecoleId,
  admins,
  professeurs,
  eleves,
  cours,
}) {
  const [selectedId, setSelectedId] = useState(null)
  const [profilStack, setProfilStack] = useState([]) // [{ cible, vueInfos, directInfo }]
  // Garde-fou contre un double-clic sur "Message" (carte de profil) ou
  // sur une ligne "Nouvelle discussion" pendant que la création du DM est
  // en cours (même principe qu'ailleurs, voir AdminCours.jsx/AdminEleves.jsx).
  const [creationEnCours, setCreationEnCours] = useState(false)

  const selected = conversations.find((c) => c.id === selectedId)
  const frame = profilStack[profilStack.length - 1] ?? null

  // `directInfo` (voir onMembreClick plus bas) : ce frame a été empilé en
  // sautant directement sur sa fiche Infos, sans jamais passer par sa
  // carte — pas de "retour vers sa carte" pour lui, donc "Retour" depuis
  // ses infos doit DÉPILER (retour au frame précédent, déjà dans le bon
  // état) plutôt que de basculer vueInfos à false (ce qui révélerait une
  // carte qu'on n'a jamais montrée).
  function empilerProfil(cible, { vueInfos = false, directInfo = false } = {}) {
    setProfilStack((pile) => [...pile, { cible, vueInfos, directInfo }])
  }

  function depilerProfil() {
    setProfilStack((pile) => pile.slice(0, -1))
  }

  function afficherInfosDuHaut(vueInfos) {
    setProfilStack((pile) => {
      if (pile.length === 0) return pile
      const copie = [...pile]
      copie[copie.length - 1] = { ...copie[copie.length - 1], vueInfos }
      return copie
    })
  }

  // Crée (ou récupère si elle existe déjà) le DM avec ce compte puis
  // l'ouvre — partagé entre le clic sur une ligne "Nouvelle discussion"
  // ET le bouton "Message" de la carte de profil pour un `type: 'contact'`
  // (voir ProfilContactScreen.jsx), pour ne jamais dupliquer cette logique.
  async function ouvrirAvecContact(compte) {
    if (creationEnCours) return
    setCreationEnCours(true)
    try {
      const conv = await messagesApi.creerOuObtenirDm(ecoleId, compteId, compte.id)
      setConversations((liste) => (liste.some((c) => c.id === conv.id) ? liste : [...liste, conv]))
      setProfilStack([])
      setSelectedId(conv.id)
    } finally {
      setCreationEnCours(false)
    }
  }

  if (selected) {
    return (
      <ConversationThreadScreen
        conversation={selected}
        onBack={() => setSelectedId(null)}
        setConversations={setConversations}
        compteId={compteId}
      />
    )
  }

  if (frame) {
    return (
      <ProfilContactScreen
        cible={frame.cible}
        vueInfos={frame.vueInfos}
        compteId={compteId}
        viewerRole={viewerRole}
        eleves={eleves}
        cours={cours}
        onBackCarte={depilerProfil}
        onShowInfos={() => afficherInfosDuHaut(true)}
        onHideInfos={frame.directInfo ? depilerProfil : () => afficherInfosDuHaut(false)}
        // Membre d'un groupe cliqué (voir ProfilContactScreen.jsx) : on
        // empile directement SA fiche Infos, pas sa carte — l'intention
        // affichée ("voir sa fiche info") saute l'étape carte (voir
        // `directInfo` ci-dessus pour le retour arrière correspondant).
        onMembreClick={(membre) =>
          empilerProfil({ type: 'contact', compte: membre }, { vueInfos: true, directInfo: true })
        }
        contacterEnCours={creationEnCours}
        onMessage={() => {
          if (frame.cible.type === 'conversation') {
            setSelectedId(frame.cible.conversation.id)
            setProfilStack([])
          } else {
            ouvrirAvecContact(frame.cible.compte)
          }
        }}
      />
    )
  }

  return (
    <ConversationListScreen
      conversations={conversations}
      onOpenConversation={setSelectedId}
      onOpenContact={ouvrirAvecContact}
      onAvatarClick={(cible) => empilerProfil(cible)}
      compteId={compteId}
      admins={admins}
      professeurs={professeurs}
      eleves={eleves}
      contactActionEnCours={creationEnCours}
    />
  )
}
