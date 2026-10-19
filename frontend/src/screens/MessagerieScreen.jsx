import { useState } from 'react'
import * as messagesApi from '../api/messages.js'
import Icon from '../components/Icon.jsx'
import { envoyerAvecReprise } from '../utils/messageOutbox.js'
import { initialiserPresence } from '../utils/presenceEnLigne.js'
import ConversationListScreen from './messagerie/ConversationListScreen.jsx'
import ConversationThreadScreen from './messagerie/ConversationThreadScreen.jsx'
import EnvoyerAScreen from './messagerie/EnvoyerAScreen.jsx'
import NouveauGroupeModal from './messagerie/NouveauGroupeModal.jsx'
import NouvelleDiscussionScreen from './messagerie/NouvelleDiscussionScreen.jsx'
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
  // « Nouveau groupe » (admins) et lecture seule d'une ancienne saison :
  // décidés par App.jsx.
  peutCreerGroupe,
  lectureSeule,
  // Texte partagé depuis une autre appli (spec §4.7, voir App.jsx) : ouvre
  // « Envoyer à… » ; `onPartageTraite` l'oublie une fois envoyé ou annulé.
  partage,
  onPartageTraite,
  onOuvrirDocs,
}) {
  const [selectedId, setSelectedId] = useState(null)
  // Écran « Nouvelle discussion », ouvert par le bouton + de la liste
  // (spec/modules/messagerie-instantanee.md §2). « Nouveau groupe » s'ouvre
  // depuis cet écran (§2.5 : plus dans le menu ⋯ de l'en-tête).
  const [nouvelleDiscussion, setNouvelleDiscussion] = useState(false)
  const [nouveauGroupeOuvert, setNouveauGroupeOuvert] = useState(false)
  const [profilStack, setProfilStack] = useState([]) // [{ cible, vueInfos, directInfo }]
  // Garde-fou contre un double-clic sur "Message" (carte de profil) ou
  // sur une ligne "Nouvelle discussion" pendant que la création du DM est
  // en cours (même principe qu'ailleurs, voir AdminCours.jsx/AdminEleves.jsx).
  const [creationEnCours, setCreationEnCours] = useState(false)
  // « Envoyer à… » (spec §4.2 Transférer) : { messages: [{ contenu, pieces, apercu }], transfere }.
  const [transfert, setTransfert] = useState(null)
  const envoiA =
    transfert ?? (partage && !lectureSeule ? { messages: [{ contenu: partage, pieces: [] }], transfere: false } : null)

  function fermerEnvoiA() {
    if (transfert) setTransfert(null)
    else onPartageTraite?.()
  }

  // Envoie chaque texte dans chaque discussion choisie, en créant au besoin
  // la discussion à deux avec un contact. Une seule destination : on
  // l'ouvre, comme WhatsApp.
  async function envoyerA({ conversationIds, contacts }) {
    const { messages, transfere } = envoiA
    fermerEnvoiA()
    const ids = [...conversationIds]
    for (const compte of contacts) {
      const conv = await messagesApi.creerOuObtenirDm(ecoleId, compteId, compte.id)
      initialiserPresence(conv.membres)
      setConversations((liste) => (liste.some((c) => c.id === conv.id) ? liste : [...liste, conv]))
      ids.push(conv.id)
    }
    for (const id of ids) {
      for (const { contenu, pieces } of messages) envoyerAvecReprise(id, compteId, contenu, 'app', { transfere, pieces })
    }
    setProfilStack([])
    setNouvelleDiscussion(false)
    setSelectedId(ids.length === 1 ? ids[0] : null)
  }

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
      // Présence (voir utils/presenceEnLigne.js) : cette conversation n'a
      // pas forcément déjà été vue par listerAvecMessages (voir App.jsx)
      // — ex. tout premier DM avec ce contact.
      initialiserPresence(conv.membres)
      setConversations((liste) => (liste.some((c) => c.id === conv.id) ? liste : [...liste, conv]))
      setProfilStack([])
      // Retour arrière depuis la discussion : la liste, pas cet écran (§2.3).
      setNouvelleDiscussion(false)
      setSelectedId(conv.id)
    } finally {
      setCreationEnCours(false)
    }
  }

  // Un seul `return` : la modale "Nouveau groupe" ci-dessous s'affiche
  // PAR-DESSUS l'écran Nouvelle discussion, et le bouton + par-dessus la
  // liste.
  let corps
  if (selected) {
    corps = (
      <ConversationThreadScreen
        conversation={selected}
        onBack={() => setSelectedId(null)}
        setConversations={setConversations}
        compteId={compteId}
        peutModerer={peutCreerGroupe}
        lectureSeule={lectureSeule}
        onTransferer={(messages) => setTransfert({ messages, transfere: true })}
        onOuvrirDocs={onOuvrirDocs}
      />
    )
  } else if (frame) {
    corps = (
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
  } else if (nouvelleDiscussion) {
    corps = (
      <NouvelleDiscussionScreen
        compteId={compteId}
        admins={admins}
        professeurs={professeurs}
        eleves={eleves}
        cours={cours}
        peutCreerGroupe={peutCreerGroupe}
        onBack={() => setNouvelleDiscussion(false)}
        onNouveauGroupe={() => setNouveauGroupeOuvert(true)}
        onOpenContact={ouvrirAvecContact}
        onAvatarClick={(compte) => empilerProfil({ type: 'contact', compte })}
        contactActionEnCours={creationEnCours}
      />
    )
  } else {
    corps = (
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

  const surLaListe = !selected && !frame && !nouvelleDiscussion

  return (
    <>
      {corps}
      {envoiA && (
        <EnvoyerAScreen
          apercu={envoiA.messages.map((m) => m.apercu ?? m.contenu).join('\n')}
          conversations={conversations}
          compteId={compteId}
          admins={admins}
          professeurs={professeurs}
          eleves={eleves}
          onBack={fermerEnvoiA}
          onEnvoyer={envoyerA}
        />
      )}
      {surLaListe && !lectureSeule && (
        <button type="button" className="fab" onClick={() => setNouvelleDiscussion(true)} aria-label="Nouvelle discussion">
          <Icon name="plus" size={28} />
        </button>
      )}
      {nouveauGroupeOuvert && (
        <NouveauGroupeModal
          ecoleId={ecoleId}
          compteId={compteId}
          admins={admins}
          professeurs={professeurs}
          eleves={eleves}
          cours={cours}
          onClose={() => setNouveauGroupeOuvert(false)}
          onCree={(conversation) => {
            setConversations((liste) =>
              liste.some((c) => c.id === conversation.id) ? liste : [...liste, conversation],
            )
            setNouveauGroupeOuvert(false)
            setNouvelleDiscussion(false)
            // Ouvre directement son fil — confirmation visuelle immédiate
            // que le groupe existe bien (voir demande utilisateur :
            // "doit s'afficher chez moi le créateur").
            setProfilStack([])
            setSelectedId(conversation.id)
          }}
        />
      )}
    </>
  )
}
