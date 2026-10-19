import { useEffect, useRef, useState } from 'react'
import * as messagesApi from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'
import { useFermerAuClicExterieur } from '../../hooks/useFermerAuClicExterieur.js'
import { useFrappeEnCours, useSignalerFrappe } from '../../utils/frappeIndicateur.js'
import { envoyerAvecReprise, reessayer, useMessagesEnAttente } from '../../utils/messageOutbox.js'
import { libellePresence, usePresence, usePresenceListe } from '../../utils/presenceEnLigne.js'
import { PhotoPleinEcran, PiecesDuMessage, VideoPleinEcran } from './pieces.jsx'
import { TAILLE_MAX_FICHIER, TAILLE_MAX_VIDEO, preparerPhoto, tailleLisible } from './piecesOutils.js'

const STATUT_ICON = { envoye: 'check', recu: 'checkCheck', vu: 'checkCheck' }

// Coche(s) grises par défaut (voir Icon.jsx : stroke="currentColor",
// hérite donc du texte ambiant) ; "vu" (lu par le destinataire) reçoit
// EN PLUS cette classe pour passer en bleu façon WhatsApp — demande
// utilisateur du 2026-09-18, jusque-là "reçu" et "lu" avaient la même
// couleur, impossible à distinguer d'un coup d'œil (voir App.css).

// Sélection volontairement courte plutôt qu'un clavier emoji complet
// (pas de dépendance externe à charger pour ça) — quelques essentiels
// façon WhatsApp, plus une poignée liée à la danse (🩰💃🕺), cohérente
// avec le thème de l'appli.
const EMOJIS = [
  '😀', '😂', '🥰', '😍', '😉', '😎', '🙂', '😢',
  '😭', '😡', '😱', '🤔', '👍', '👎', '👏', '🙏',
  '💪', '🙌', '🤝', '👋', '❤️', '💔', '🎉', '✨',
  '🔥', '💯', '💃', '🕺', '🎶', '🎵', '🩰', '☀️',
  '🌙', '⭐', '🎂', '🎈',
]

// Entrée envoie SEULEMENT sur un appareil à pointeur "fin" (souris/pavé
// tactile, typiquement un ordinateur) — sur un écran tactile (Android,
// iOS...), le clavier virtuel n'a pas de vraie touche Maj à combiner
// avec Entrée pour un retour à la ligne : `shiftKey` y reste toujours
// faux, donc Entrée y envoyait le message à chaque fois (signalé). Sur
// ces appareils, Entrée insère juste une ligne (comportement natif de la
// textarea, rien à faire) — l'envoi se fait via le bouton.
const ENTREE_ENVOIE = window.matchMedia('(pointer: fine)').matches

// Liens cliquables (spec/modules/messagerie-instantanee.md §4.1) : https://,
// http:// et www., sans aperçu. La ponctuation qui suit un lien (« voir
// www.site.fr. ») reste du texte.
const LIEN = /(https?:\/\/[^\s<]+|www\.[^\s<]+)/gi
const PONCTUATION_FINALE = /[.,;:!?)»"']+$/

// Lien vers un fichier ou un dossier des Docs de la même école
// (`<adresse de l'école>/docs/<id>`) : ouvert dans l'appli, pas dans un
// nouvel onglet. Renvoie l'id, ou null pour un lien ordinaire.
function idDocs(lien) {
  try {
    const url = new URL(lien)
    if (url.origin !== window.location.origin) return null
    return url.pathname.match(/^\/docs\/(\d+)\/?$/)?.[1] ?? null
  } catch {
    return null
  }
}

function AvecLiens({ texte, desactives, onOuvrirDocs }) {
  const morceaux = []
  let dernier = 0
  for (const trouve of texte.matchAll(LIEN)) {
    const brut = trouve[0]
    const lien = brut.replace(PONCTUATION_FINALE, '')
    morceaux.push(texte.slice(dernier, trouve.index))
    const id = idDocs(lien)
    morceaux.push(
      id ? (
        <a
          key={trouve.index}
          href={lien}
          className="message-bubble__lien-docs"
          onClick={(e) => {
            e.preventDefault()
            if (!desactives) onOuvrirDocs?.(Number(id))
          }}
        >
          <Icon name="docs" size={18} /> Ouvrir dans Docs
        </a>
      ) : (
      <a
        key={trouve.index}
        href={lien.startsWith('www.') ? `https://${lien}` : lien}
        target="_blank"
        rel="noopener noreferrer"
        // En mode sélection, toucher la bulle la sélectionne au lieu d'ouvrir le lien.
        onClick={(e) => desactives && e.preventDefault()}
      >
        {lien}
      </a>
      ),
    )
    dernier = trouve.index + lien.length
  }
  morceaux.push(texte.slice(dernier))
  return morceaux
}

// Modifier : pendant 15 minutes après l'envoi, comme WhatsApp et le serveur
// (backend/src/messagerie/messages.py: EDIT_WINDOW). Les dates du serveur
// sont en UTC sans fuseau.
const DELAI_MODIFICATION_MS = 15 * 60 * 1000
function encoreModifiable(m) {
  if (!m.envoyeLe) return false
  const envoye = new Date(/Z|[+-]\d\d:\d\d$/.test(m.envoyeLe) ? m.envoyeLe : `${m.envoyeLe}Z`)
  return Date.now() - envoye.getTime() < DELAI_MODIFICATION_MS
}

const SUPPRIME = 'Ce message a été supprimé'
const DELAI_ANNULER_MS = 10_000

// Écran 2/2 de la Messagerie : le fil d'UNE conversation, plein écran, avec
// une flèche de retour vers ConversationListScreen (voir MessagerieScreen.jsx)
// — comme l'écran de discussion de WhatsApp. Coches de statut façon WhatsApp ;
// le choix messagerie/mail/whatsapp se fait à l'envoi (voir send ci-dessous),
// et l'icône dans la bulle n'est qu'un indicatif de ce choix a posteriori
// (voir spec/SPEC.md 5.5).
//
// WhatsApp : le canal 'whatsapp' (voir backend/src/messagerie/messages.py)
// n'est qu'un MARQUEUR d'intention — la case cochée reste visible après
// coup (badge sur la bulle), mais aucun message ne part réellement sur
// WhatsApp pour l'instant (Baileys pas branché, voir spec/SPEC.md §6.9/§8).
export default function ConversationThreadScreen({
  conversation,
  onBack,
  setConversations,
  compteId,
  // Un admin peut supprimer n'importe quel message d'un groupe (§4.2).
  peutModerer,
  lectureSeule,
  // « Transférer » : ouvre « Envoyer à… » (voir MessagerieScreen.jsx).
  onTransferer,
  // Toucher un lien vers les Docs (voir idDocs).
  onOuvrirDocs,
}) {
  const [draft, setDraft] = useState('')
  const messagesRef = useRef(null)
  // Bulles "en cours"/"échec" (voir utils/messageOutbox.js) — filtrées
  // des messages dont le `client_id` est déjà arrivé côté serveur (SSE
  // ou réponse directe), pour ne jamais l'afficher 2 fois pendant la
  // toute petite fenêtre où les deux peuvent se chevaucher.
  const enAttenteBrut = useMessagesEnAttente(conversation.id)
  const enAttente = enAttenteBrut.filter(
    (m) => !conversation.messages.some((cm) => cm.clientId === m.clientId),
  )
  // Présence (voir utils/presenceEnLigne.js) — un seul "l'autre" en DM,
  // potentiellement plusieurs en groupe (voir usePresenceListe et
  // sousTitre plus bas).
  const autreMembre =
    conversation.type === 'individuelle' ? conversation.membres.find((m) => m.id !== compteId) : null
  const presence = usePresence(autreMembre?.id ?? null)
  const autresMembresGroupe =
    conversation.type === 'groupe' ? conversation.membres.filter((m) => m.id !== compteId) : []
  const presencesGroupe = usePresenceListe(autresMembresGroupe.map((m) => m.id))
  const membresEnLigne = autresMembresGroupe.filter((_, i) => presencesGroupe[i]?.enLigne)
  // "En train d'écrire" (voir utils/frappeIndicateur.js) — reçu (l'autre
  // écrit) et signalé (moi j'écris) sont 2 choses distinctes.
  const frappeEnCours = useFrappeEnCours(conversation.id)
  const frappeur = frappeEnCours
    ? conversation.membres.find((m) => m.id === frappeEnCours.compteId)
    : null
  const signalerFrappe = useSignalerFrappe(conversation.id, compteId)
  const textareaRef = useRef(null)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const emojiSelectorRef = useRef(null)
  useFermerAuClicExterieur(emojiSelectorRef, emojiOpen, () => setEmojiOpen(false))

  // "Autres moyens d'envoi" (mail/WhatsApp) : une seule icône dans le
  // bandeau (demandé — les 2 icônes séparées ne pouvaient pas être
  // resserrées davantage, voir commits précédents), qui ouvre une petite
  // liste au clic plutôt que de les afficher en permanence.
  // Actions sur un message (spec §4.2) : appui long (clic droit, ou ⋯ au
  // survol sur ordinateur) sélectionne une bulle et remplace l'en-tête par
  // la barre d'actions ; toucher d'autres bulles les ajoute ou les retire.
  const [selection, setSelection] = useState([]) // ids des messages
  const enSelection = selection.length > 0
  const appuiLong = useRef({ timer: null, declenche: false })
  const [reponseA, setReponseA] = useState(null) // message auquel on répond
  const [enModification, setEnModification] = useState(null) // message modifié
  // Supprimer : la bulle passe tout de suite à « supprimé », l'envoi au
  // serveur attend 10 s pour laisser « Annuler » (spec §6.0 bis).
  const [aSupprimer, setASupprimer] = useState(null) // { ids, timer }
  const aSupprimerRef = useRef(null)
  const [bandeau, setBandeau] = useState(null) // petit message en bas (« Copié »)
  const [clignote, setClignote] = useState(null) // id du message rappelé par une réponse
  // Photos et fichiers à envoyer avec le prochain message (spec §4.3).
  const [aJoindre, setAJoindre] = useState([]) // [{ cle, fichier, nom, kind, apercu }]
  const fichierRef = useRef(null)
  const photoRef = useRef(null)
  const [photoOuverte, setPhotoOuverte] = useState(null)

  const [canalOpen, setCanalOpen] = useState(false)
  const canalSelectorRef = useRef(null)
  useFermerAuClicExterieur(canalSelectorRef, canalOpen, () => setCanalOpen(false))

  // Hauteur qui suit le contenu, façon WhatsApp (une ligne par défaut,
  // grandit jusqu'à un plafond CSS, voir .conversation-thread__input
  // textarea : au-delà, ça défile plutôt que de continuer à grandir).
  function ajusterHauteur(el) {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  // Insère au niveau du curseur (pas juste à la fin) — sinon cliquer un
  // emoji après avoir replacé le curseur au milieu du texte l'enverrait
  // toujours à la fin, contre-intuitif.
  function insererEmoji(emoji) {
    const el = textareaRef.current
    const debut = el?.selectionStart ?? draft.length
    const fin = el?.selectionEnd ?? draft.length
    const nouveauDraft = draft.slice(0, debut) + emoji + draft.slice(fin)
    setDraft(nouveauDraft)
    setEmojiOpen(false)
    // Après le prochain rendu (la textarea doit d'abord recevoir la
    // nouvelle valeur) : redonne le focus et replace le curseur juste
    // après l'emoji, plutôt que de le laisser sauter à la fin.
    requestAnimationFrame(() => {
      if (!el) return
      el.focus()
      const position = debut + emoji.length
      el.setSelectionRange(position, position)
      ajusterHauteur(el)
    })
  }

  // Redescend en bas de la liste — à l'ouverture du fil (sinon on
  // atterrit en haut, sur les plus vieux messages) ET à chaque nouveau
  // message (envoyé par moi OU reçu en direct via SSE, voir App.jsx) —
  // sans ça, un message qui arrive pendant que le fil est déjà ouvert
  // peut s'afficher hors de l'écran, plus bas que ce qu'on voit
  // (signalé). Toujours instantané (pas de défilement animé) : sur un
  // gros fil, un scroll animé depuis le haut serait lent et brouillon.
  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [conversation.id, conversation.messages.length, enAttente.length])

  // Ouvrir ce fil = les avoir vus pour de vrai (façon WhatsApp, voir
  // api/messages.js: marquerLus) — distinct de "reçu" (marqué dès la
  // liste, voir api/messages.js: listerAvecMessages). Redéclenché aussi
  // quand `messages.length` grandit (pas seulement à l'ouverture du
  // fil) : un message qui arrive EN DIRECT (SSE, voir App.jsx) pendant
  // que ce fil est déjà affiché doit lui aussi passer "lu" tout de suite
  // — sans ça, il resterait affiché "reçu" jusqu'à la prochaine ouverture
  // du fil.
  //
  // Contrairement à avant : met AUSSI à jour `luParMoi` en local, tout de
  // suite (pas seulement côté serveur) — sert au badge de non-lus (voir
  // ConversationListScreen.jsx/BottomNav.jsx) : sans ça, le badge ne
  // retomberait à zéro qu'au prochain rechargement complet, pas à
  // l'ouverture du fil (signalé). Se limite aux messages VRAIMENT non lus
  // (`nonLus`) : évite de re-PUT en boucle des messages déjà "lu" à
  // chaque fois que ce fil se réaffiche (ex. un nouveau message dans une
  // AUTRE conversation ne fait pas grandir `messages.length` ici, mais un
  // nouveau rendu de ce composant sans changement de dépendance ne
  // redéclenche pas l'effet non plus — la garde reste utile si jamais).
  useEffect(() => {
    const nonLus = conversation.messages.filter((m) => !m.estMoi && !m.luParMoi)
    if (nonLus.length === 0) return
    messagesApi.marquerLus(nonLus, compteId)
    setConversations((liste) =>
      liste.map((c) =>
        c.id !== conversation.id
          ? c
          : { ...c, messages: c.messages.map((m) => (nonLus.includes(m) ? { ...m, luParMoi: true } : m)) },
      ),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id, conversation.messages.length])

  // Envoi par la messagerie de l'appli — mail et WhatsApp ne sont pas de
  // vrais canaux d'envoi pour l'instant (voir le menu "Autres moyens
  // d'envoi" plus bas, qui n'appelle plus cette fonction du tout).
  async function ajouterFichiers(liste, commePhotos) {
    const prets = []
    for (const fichier of liste) {
      if (fichier.type.startsWith('video/')) {
        // Compressée au moment de l'envoi (voir utils/messageOutbox.js).
        if (fichier.size > TAILLE_MAX_VIDEO) {
          window.alert(`« ${fichier.name} » est trop grosse : 100 Mo au maximum.`)
          continue
        }
        prets.push({ fichier, nom: fichier.name, kind: 'video', apercu: null, cle: crypto.randomUUID() })
        continue
      }
      const piece =
        commePhotos || fichier.type.startsWith('image/')
          ? await preparerPhoto(fichier)
          : { fichier, nom: fichier.name, kind: 'file', apercu: null }
      if (piece.fichier.size > TAILLE_MAX_FICHIER) {
        window.alert(`« ${fichier.name} » est trop gros : 25 Mo au maximum.`)
        continue
      }
      prets.push({ ...piece, cle: crypto.randomUUID() })
    }
    setAJoindre((a) => [...a, ...prets])
  }

  function send() {
    if (!draft.trim() && aJoindre.length === 0) return
    const contenu = draft.trim()
    setDraft('')
    if (enModification) {
      const message = enModification
      setEnModification(null)
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
      if (contenu !== message.contenu) {
        messagesApi
          .modifierMessage(message.id, contenu)
          .then(remplacerMessage)
          .catch(() => window.alert('Ce message ne peut plus être modifié.'))
      }
      return
    }
    const options = reponseA ? { reponseA: reponseA.id } : {}
    setReponseA(null)
    const fichiers = aJoindre.map(({ fichier, nom, kind, apercu }) => ({ fichier, nom, kind, apercu }))
    setAJoindre([])
    // Revient à 1 ligne après l'envoi — sinon la textarea, agrandie
    // manuellement (voir ajusterHauteur), garde sa hauteur même une fois
    // vide.
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    // Bulle "en cours" affichée tout de suite (voir useMessagesEnAttente
    // plus haut) — le texte ne disparaît plus jamais de l'écran, même si
    // l'envoi échoue (bug signalé). L'insertion du message CONFIRMÉ dans
    // la conversation se fait ailleurs (voir App.jsx: useMessagesEnvoyes),
    // pas ici — ça marche pareil qu'on reste sur cet écran ou pas.
    envoyerAvecReprise(conversation.id, compteId, contenu, 'app', options, fichiers)
  }

  function remplacerMessage(brut) {
    const maj = messagesApi.versMessageEcran(brut, compteId, conversation.membres)
    setConversations((liste) =>
      liste.map((c) =>
        c.id !== conversation.id ? c : { ...c, messages: c.messages.map((m) => (m.id === maj.id ? maj : m)) },
      ),
    )
  }

  function montrerBandeau(texte) {
    setBandeau(texte)
    setTimeout(() => setBandeau((b) => (b === texte ? null : b)), 2500)
  }

  // --- Sélection et barre d'actions (spec §4.2) ---
  const supprimeLocalement = (m) => m.supprime || aSupprimer?.ids.includes(m.id)
  const selectionnes = conversation.messages.filter((m) => selection.includes(m.id))

  function selectionner(id) {
    setSelection((s) => (s.includes(id) ? s : [...s, id]))
  }
  function basculerSelection(id) {
    setSelection((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  }
  function proprietesBulle(m) {
    if (supprimeLocalement(m)) return {}
    const annulerAppui = () => clearTimeout(appuiLong.current.timer)
    return {
      onPointerDown: (e) => {
        if (e.pointerType === 'mouse') return // souris : clic droit ou ⋯
        appuiLong.current.declenche = false
        appuiLong.current.timer = setTimeout(() => {
          appuiLong.current.declenche = true
          selectionner(m.id)
          navigator.vibrate?.(30)
        }, 500)
      },
      onPointerUp: annulerAppui,
      onPointerCancel: annulerAppui,
      onPointerLeave: annulerAppui,
      onContextMenu: (e) => {
        e.preventDefault()
        selectionner(m.id)
      },
      onClick: () => {
        if (appuiLong.current.declenche) {
          appuiLong.current.declenche = false
          return
        }
        if (enSelection) basculerSelection(m.id)
      },
    }
  }

  const peutRepondre = !lectureSeule && selectionnes.length === 1
  const peutModifier =
    !lectureSeule && selectionnes.length === 1 && selectionnes[0].estMoi && encoreModifiable(selectionnes[0])
  const peutSupprimer =
    !lectureSeule &&
    selectionnes.length > 0 &&
    selectionnes.every((m) => m.estMoi || (peutModerer && conversation.type === 'groupe'))

  function repondre() {
    setEnModification(null)
    setReponseA(selectionnes[0])
    setSelection([])
    textareaRef.current?.focus()
  }

  function copier() {
    navigator.clipboard?.writeText(selectionnes.map((m) => m.contenu).join('\n'))
    setSelection([])
    montrerBandeau('Copié')
  }

  // Le message part avec ses photos et fichiers (spec §4.2).
  function transferer() {
    const messages = selectionnes.map((m) => ({
      contenu: m.contenu,
      pieces: m.pieces.map((p) => p.id),
      apercu: messagesApi.apercuMessage(m),
    }))
    setSelection([])
    onTransferer(messages)
  }

  function modifier() {
    const m = selectionnes[0]
    setSelection([])
    setReponseA(null)
    setEnModification(m)
    setDraft(m.contenu)
    requestAnimationFrame(() => {
      const el = textareaRef.current
      if (!el) return
      el.focus()
      ajusterHauteur(el)
    })
  }

  function envoyerSuppressions(ids) {
    for (const id of ids) messagesApi.supprimerMessage(id).then(remplacerMessage).catch(() => {})
  }

  function supprimer() {
    const ids = [...selection]
    setSelection([])
    // Une suppression déjà en attente part tout de suite (une seule à la fois).
    if (aSupprimerRef.current) {
      clearTimeout(aSupprimerRef.current.timer)
      envoyerSuppressions(aSupprimerRef.current.ids)
    }
    const timer = setTimeout(() => {
      envoyerSuppressions(ids)
      aSupprimerRef.current = null
      setASupprimer(null)
    }, DELAI_ANNULER_MS)
    aSupprimerRef.current = { ids, timer }
    setASupprimer(aSupprimerRef.current)
  }

  function annulerSuppression() {
    clearTimeout(aSupprimerRef.current?.timer)
    aSupprimerRef.current = null
    setASupprimer(null)
  }

  // Quitter le fil pendant les 10 s : la suppression part quand même.
  useEffect(
    () => () => {
      if (!aSupprimerRef.current) return
      clearTimeout(aSupprimerRef.current.timer)
      envoyerSuppressions(aSupprimerRef.current.ids)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  // Toucher le rappel d'une réponse : défile jusqu'au message d'origine.
  function allerAuMessage(id) {
    document.getElementById(`message-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setClignote(id)
    setTimeout(() => setClignote((c) => (c === id ? null : c)), 1500)
  }

  function auteurDe(m) {
    return m.estMoi ? 'Vous' : m.auteur
  }

  // "X écrit..." (DM : un seul autre membre possible, pas la peine de le
  // nommer) / "X écrit..." (groupe : plusieurs personnes possibles, voir
  // messagerie/frappe.py — un seul frappeur affiché à la fois, le plus
  // récent, ça reste très rare d'en avoir 2 en même temps dans ce contexte).
  const sousTitre = frappeur
    ? conversation.type === 'groupe'
      ? `${frappeur.prenom} écrit...`
      : 'écrit...'
    : conversation.type === 'groupe'
      ? (membresEnLigne.length === 0
          ? 'Groupe'
          : membresEnLigne.length === 1
            ? `${membresEnLigne[0].prenom} en ligne`
            : `${membresEnLigne.length} en ligne`)
      : (libellePresence(presence) ?? 'Conversation')

  return (
    <div className="thread-screen">
      {enSelection ? (
        <div className="thread-screen__header barre-actions">
          <button type="button" className="icon-btn" onClick={() => setSelection([])} aria-label="Annuler la sélection">
            <Icon name="chevronLeft" size={22} />
          </button>
          <strong className="barre-actions__nombre">{selection.length}</strong>
          {peutRepondre && (
            <button type="button" className="barre-actions__btn" onClick={repondre}>
              <Icon name="reply" size={22} />
              <span>Répondre</span>
            </button>
          )}
          <button type="button" className="barre-actions__btn" onClick={copier}>
            <Icon name="copy" size={22} />
            <span>Copier</span>
          </button>
          {!lectureSeule && (
            <button type="button" className="barre-actions__btn" onClick={transferer}>
              <Icon name="forward" size={22} />
              <span>Transférer</span>
            </button>
          )}
          {peutModifier && (
            <button type="button" className="barre-actions__btn" onClick={modifier}>
              <Icon name="edit" size={22} />
              <span>Modifier</span>
            </button>
          )}
          {peutSupprimer && (
            <button type="button" className="barre-actions__btn" onClick={supprimer}>
              <Icon name="trash" size={22} />
              <span>Supprimer</span>
            </button>
          )}
        </div>
      ) : (
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux conversations">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className={`avatar avatar--sm ${conversation.type === 'groupe' ? 'avatar--groupe' : ''}`}>
          {conversation.type === 'groupe' ? (
            <Icon name="users" size={16} />
          ) : (
            conversation.nom.slice(0, 2).toUpperCase()
          )}
          {presence?.enLigne && <span className="avatar__dot-en-ligne" />}
        </span>
        <span className="thread-screen__header-text">
          <strong>{conversation.nom}</strong>
          <span className={frappeur ? 'thread-screen__frappe' : 'muted'}>{sousTitre}</span>
        </span>
      </div>
      )}

      <div className="conversation-thread__messages" ref={messagesRef}>
        {conversation.messages.map((m) => {
          const supprime = supprimeLocalement(m)
          const original = m.reponseA ? conversation.messages.find((o) => o.id === m.reponseA) : null
          return (
          <div
            key={m.id}
            id={`message-${m.id}`}
            className={`message-row ${m.estMoi ? 'message-row--moi' : ''} ${
              selection.includes(m.id) ? 'message-row--choisi' : ''
            } ${clignote === m.id ? 'message-row--clignote' : ''}`}
            {...proprietesBulle(m)}
          >
            <div className="message-bubble">
              {!supprime && !enSelection && (
                <button
                  type="button"
                  className="message-bubble__plus"
                  onClick={(e) => {
                    e.stopPropagation()
                    selectionner(m.id)
                  }}
                  aria-label="Actions sur ce message"
                >
                  <Icon name="moreHorizontal" size={18} />
                </button>
              )}
              {!m.estMoi && conversation.type === 'groupe' && (
                <span className="message-bubble__auteur">{m.auteur}</span>
              )}
              {m.transfere && !supprime && (
                <span className="message-bubble__transfere">
                  <Icon name="forward" size={14} /> Transféré
                </span>
              )}
              {original && !supprime && (
                <button
                  type="button"
                  className="message-bubble__citation"
                  onClick={(e) => {
                    if (enSelection) return
                    e.stopPropagation()
                    allerAuMessage(original.id)
                  }}
                >
                  <strong>{auteurDe(original)}</strong>
                  <span>{supprimeLocalement(original) ? SUPPRIME : original.contenu}</span>
                </button>
              )}
              {/* white-space: pre-wrap (voir App.css) : un message écrit
                  sur plusieurs lignes (voir la textarea ci-dessous) doit
                  aussi s'afficher sur plusieurs lignes, pas être aplati
                  en un seul paragraphe comme le ferait un <p> normal. */}
              {!supprime && (
                <PiecesDuMessage pieces={m.pieces} onOuvrirPhoto={setPhotoOuverte} desactivees={enSelection} />
              )}
              {supprime ? (
                <p className="message-bubble__contenu message-bubble__contenu--supprime">{SUPPRIME}</p>
              ) : (
                m.contenu && <p className="message-bubble__contenu">
                  <AvecLiens texte={m.contenu} desactives={enSelection} onOuvrirDocs={onOuvrirDocs} />
                </p>
              )}
              <span className="message-bubble__meta">
                {m.modifie && !supprime && 'modifié '}
                {m.heure}
                {m.estMoi && (
                  <Icon
                    name={STATUT_ICON[m.statut]}
                    size={16}
                    // Trait plus épais que les autres icônes de l'appli
                    // (voir Icon.jsx : 1.8 par défaut) — signalé trop
                    // fines/peu visibles comparées à WhatsApp.
                    strokeWidth={2.5}
                    className={m.statut === 'vu' ? 'message-bubble__coche--lu' : ''}
                  />
                )}
                {m.envoyeParMail && <Icon name="mail" size={14} />}
                {m.envoyeParWhatsapp && <WhatsappBadge size={14} />}
              </span>
            </div>
          </div>
          )
        })}
        {/* Bulles "en cours d'envoi"/"échec" (voir utils/messageOutbox.js)
            — un message tapé reste toujours visible à l'écran, jamais
            perdu en silence (bug signalé). Tap sur une bulle en échec :
            réessaie. */}
        {enAttente.map((m) => (
          <div key={m.clientId} className="message-row message-row--moi">
            <button
              type="button"
              className={`message-bubble message-bubble--attente ${
                m.etat === 'echec' ? 'message-bubble--echec' : ''
              }`}
              disabled={m.etat !== 'echec'}
              onClick={() => reessayer(m.clientId)}
            >
              {(m.fichiers?.length > 0 || m.options?.pieces?.length > 0) && (
                <span className="message-bubble__envoi-pieces">
                  {m.fichiers?.map((f, i) =>
                    f.apercu ? (
                      <img key={i} src={f.apercu} alt="" />
                    ) : (
                      <span key={i}>
                        {f.kind === 'video' ? '🎬' : '📎'} {f.nom}
                      </span>
                    ),
                  )}
                  {m.etat !== 'echec' && m.etape === 'compression' && <span>Préparation de la vidéo…</span>}
                  {m.etat !== 'echec' && m.fichiers?.length > 0 && (
                    <span className="barre-progression">
                      <span style={{ width: `${Math.round(m.progression * 100)}%` }} />
                    </span>
                  )}
                </span>
              )}
              {m.contenu && <p className="message-bubble__contenu">{m.contenu}</p>}
              <span className="message-bubble__meta">
                {m.etat === 'echec' ? (
                  <>
                    <Icon name="x" size={14} /> Échec — toucher pour réessayer
                  </>
                ) : (
                  <Icon name="clock" size={14} />
                )}
              </span>
            </button>
          </div>
        ))}
      </div>

      {aSupprimer && (
        <div className="thread-bandeau">
          <span>
            {aSupprimer.ids.length > 1 ? `${aSupprimer.ids.length} messages supprimés` : 'Message supprimé'}
          </span>
          <button type="button" className="thread-bandeau__action" onClick={annulerSuppression}>
            Annuler
          </button>
        </div>
      )}
      {bandeau && !aSupprimer && (
        <div className="thread-bandeau">
          <span>{bandeau}</span>
        </div>
      )}
      {(reponseA || enModification) && (
        <div className="thread-rappel">
          <Icon name={reponseA ? 'reply' : 'edit'} size={20} />
          <span className="thread-rappel__texte">
            <strong>{reponseA ? auteurDe(reponseA) : 'Modifier le message'}</strong>
            <span>{(reponseA ?? enModification).contenu}</span>
          </span>
          <button
            type="button"
            className="icon-btn"
            aria-label={reponseA ? 'Ne plus répondre' : 'Annuler la modification'}
            onClick={() => {
              if (enModification) {
                setDraft('')
                if (textareaRef.current) textareaRef.current.style.height = 'auto'
              }
              setReponseA(null)
              setEnModification(null)
            }}
          >
            <Icon name="x" size={20} />
          </button>
        </div>
      )}
      {aJoindre.length > 0 && (
        <div className="thread-a-joindre">
          {aJoindre.map((p) => (
            <span key={p.cle} className="thread-a-joindre__piece">
              {p.apercu ? (
                <img src={p.apercu} alt="" />
              ) : (
                <span className="thread-a-joindre__nom">
                  {p.kind === 'video' ? '🎬' : '📎'} {p.nom}
                </span>
              )}
              <button
                type="button"
                className="thread-a-joindre__retirer"
                aria-label={`Retirer ${p.nom}`}
                onClick={() => setAJoindre((a) => a.filter((x) => x.cle !== p.cle))}
              >
                <Icon name="x" size={16} />
              </button>
              {!p.apercu && <span className="thread-a-joindre__taille">{tailleLisible(p.fichier.size)}</span>}
            </span>
          ))}
        </div>
      )}
      <input
        ref={fichierRef}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          ajouterFichiers([...e.target.files], false)
          e.target.value = ''
        }}
      />
      <input
        ref={photoRef}
        type="file"
        accept="image/*,video/*"
        multiple
        hidden
        onChange={(e) => {
          ajouterFichiers([...e.target.files], true)
          e.target.value = ''
        }}
      />
      {photoOuverte?.kind === 'video' && <VideoPleinEcran piece={photoOuverte} onFermer={() => setPhotoOuverte(null)} />}
      {photoOuverte && photoOuverte.kind !== 'video' && (
        <PhotoPleinEcran piece={photoOuverte} onFermer={() => setPhotoOuverte(null)} />
      )}
      <div className="conversation-thread__input">
        {emojiOpen && (
          <div className="emoji-picker" ref={emojiSelectorRef}>
            {EMOJIS.map((emoji) => (
              <button type="button" key={emoji} onClick={() => insererEmoji(emoji)}>
                {emoji}
              </button>
            ))}
          </div>
        )}
        {/* Bandeau (bordure/fond/arrondi posés ici, plus sur la textarea,
            voir App.css) — l'emoji à gauche et mail/WhatsApp à droite
            sont dedans ; le bouton d'envoi principal, lui, est HORS du
            bandeau, à l'extrême droite (demande — nouvelle approche). */}
        <div className="conversation-thread__pill">
          <button
            type="button"
            className="icon-btn"
            onClick={() => setEmojiOpen((o) => !o)}
            aria-label="Insérer un emoji"
          >
            🙂
          </button>
          <textarea
            ref={textareaRef}
            value={draft}
            placeholder="Message"
            rows={1}
            onChange={(e) => {
              setDraft(e.target.value)
              ajusterHauteur(e.target)
              if (e.target.value.trim()) signalerFrappe()
            }}
            // Entrée seule -> envoie ; Maj+Entrée -> retour à la ligne —
            // mais SEULEMENT sur un appareil à pointeur fin (voir
            // ENTREE_ENVOIE) : sur écran tactile, Entrée reste toujours un
            // retour à la ligne (comportement natif), l'envoi se fait par
            // le bouton. `isComposing` : une touche Entrée qui valide une
            // saisie assistée (japonais/chinois...) ne doit pas envoyer le
            // message par accident.
            onKeyDown={(e) => {
              if (ENTREE_ENVOIE && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault()
                send()
              }
            }}
          />
          {!enModification && !lectureSeule && (
            <>
              <button type="button" className="icon-btn" onClick={() => fichierRef.current?.click()} aria-label="Joindre un fichier">
                <Icon name="paperclip" size={20} />
              </button>
              <button type="button" className="icon-btn" onClick={() => photoRef.current?.click()} aria-label="Joindre une photo ou une vidéo">
                <Icon name="camera" size={20} />
              </button>
            </>
          )}
          <div className="conversation-thread__pill-envoi" ref={canalSelectorRef}>
            <button
              type="button"
              className="icon-btn icon-btn--mail"
              onClick={() => setCanalOpen((o) => !o)}
              aria-label="Autres moyens d'envoi (mail, WhatsApp)"
            >
              <Icon name="moreHorizontal" size={18} />
            </button>
            {canalOpen && (
              <div className="dropdown-menu canal-picker">
                {/* Ni mail ni WhatsApp ne sont de vrais canaux d'envoi
                    pour l'instant (voir messages.py: Messages.envoyer —
                    juste un marqueur d'intention, aucune vraie
                    infrastructure d'envoi) — demande utilisateur du
                    2026-09-21 : le dire clairement plutôt que de laisser
                    croire à un envoi réel. */}
                <button
                  type="button"
                  onClick={() => {
                    setCanalOpen(false)
                    window.alert('Fonctionnalité en cours de développement')
                  }}
                >
                  <Icon name="mail" size={16} /> Par mail
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCanalOpen(false)
                    window.alert('Fonctionnalité en cours de développement')
                  }}
                >
                  <WhatsappBadge size={16} /> Par WhatsApp
                </button>
              </div>
            )}
          </div>
        </div>
        <button
          type="button"
          className="icon-btn icon-btn--accent"
          onClick={() => send()}
          aria-label={enModification ? 'Modifier' : 'Envoyer par la messagerie'}
        >
          <Icon name={enModification ? 'check' : 'send'} size={18} />
        </button>
      </div>
    </div>
  )
}
