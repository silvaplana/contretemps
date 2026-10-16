import { useEffect, useState } from 'react'
import { ajouterProduit } from '../../api/assistant.js'
import { documentsApi } from '../../api/documents.js'
import Assistant from './Assistant.jsx'
import { docsBranche, ecrireStockage, lireStockage, ouvrirDansDocs } from './assistantGlobal.js'
import './documents.css'

// L'assistant de toute l'appli (Seb, 16 octobre) : un seul chat, ouvert par
// le bouton de l'en-tête, utilisable dans tous les onglets, avec la même
// conversation partout. Dans Docs, il voit en plus le dossier ouvert et la
// sélection, et ses cartes « Faire » passent par l'explorateur. Un fichier
// de l'appli garde son propre chat, qui part de zéro (AppFile.jsx).
//
// Ouvert ou fermé, et la hauteur du panneau sur ordinateur : gardés sur
// l'appareil, l'appli rouvre le chat comme on l'avait laissé.

const CLE_HAUTEUR = 'contretemps.assistant.hauteur'
const ECRAN_BUREAU = '(min-width: 900px) and (hover: hover) and (pointer: fine)'

function hauteurDeDepart() {
  const h = Number(lireStockage(CLE_HAUTEUR))
  if (h >= 160) return Math.min(h, Math.round(window.innerHeight * 0.85))
  return Math.round(window.innerHeight * 0.45)
}

function useBureau() {
  const [bureau, setBureau] = useState(() => window.matchMedia?.(ECRAN_BUREAU).matches ?? false)
  useEffect(() => {
    const mq = window.matchMedia?.(ECRAN_BUREAU)
    if (!mq) return undefined
    const suivre = (e) => setBureau(e.matches)
    mq.addEventListener('change', suivre)
    return () => mq.removeEventListener('change', suivre)
  }, [])
  return bureau
}

const ONGLETS = {
  presence: 'Présence', heures: 'Heures', choregraphie: 'Chorégraphies', messagerie: 'Messagerie',
  admin: 'Administration', profil: 'Profil', supervision: 'Supervision', docs: 'Docs',
}

export default function AssistantGlobal({ etat, onglet, onNavigate }) {
  const bureau = useBureau()
  const [hauteur, setHauteur] = useState(hauteurDeDepart)
  const [message, setMessage] = useState('')

  // Sur ordinateur, le chat occupe le bas de l'écran : les boutons +
  // (et les messages) des écrans remontent d'autant pour ne pas cacher ses
  // boutons (Seb, 16 octobre). Sur téléphone, il couvre tout l'écran.
  useEffect(() => {
    const racine = document.documentElement.style
    racine.setProperty('--chat-hauteur', `${etat.monte && etat.ouvert && bureau ? hauteur : 0}px`)
    return () => racine.removeProperty('--chat-hauteur')
  }, [etat.monte, etat.ouvert, bureau, hauteur])

  if (!etat.monte) return null

  // Hors de Docs, les cartes passent directement par les routes du module.
  async function faire(carte) {
    const docs = docsBranche()
    if (docs) return docs.faire(carte)
    const api = documentsApi(etat.orgId)
    if (carte.kind === 'creer_dossier') await api.createFolder(carte.espace, carte.dossier_parent_id, carte.nom)
    else if (carte.kind === 'creer_fichier_texte') {
      await api.upload(carte.espace, carte.dossier_parent_id, new File([carte.contenu], carte.nom, { type: 'text/plain' }))
    } else if (carte.kind === 'deplacer') await api.move(carte.element_id, carte.espace, carte.dossier_destination_id)
    else if (carte.kind === 'renommer') await api.rename(carte.element_id, carte.nouveau_nom)
    else if (carte.kind === 'ajouter_fichier') await ajouterProduit(etat.orgId, carte.jeton, carte.espace, carte.dossier_parent_id)
    else if (carte.kind === 'creer_fichier_appli') {
      const f = await api.createApp(carte.espace, carte.dossier_parent_id, carte.nature, carte.nom)
      ouvrirDansDocs({ id: f.id, name: f.name, kind: 'app', family: carte.nature, space: carte.espace, parent_id: carte.dossier_parent_id })
      onNavigate('docs')
    }
    setMessage(`Fait : ${carte.libelle}`)
    setTimeout(() => setMessage(''), 3000)
  }

  // Lu au moment d'envoyer : le dossier ouvert dans Docs, ou l'onglet.
  function contexte() {
    const docs = docsBranche()
    if (onglet === 'docs' && docs) return docs.contexte()
    return { onglet: ONGLETS[onglet] ?? onglet }
  }

  function redimensionner(e) {
    e.preventDefault()
    const depart = e.clientY
    const hauteurDepart = hauteur
    let derniere = hauteurDepart
    const bouger = (ev) => {
      derniere = Math.max(160, Math.min(Math.round(window.innerHeight * 0.85), hauteurDepart + depart - ev.clientY))
      setHauteur(derniere)
    }
    const lacher = () => {
      window.removeEventListener('pointermove', bouger)
      window.removeEventListener('pointerup', lacher)
      ecrireStockage(CLE_HAUTEUR, String(derniere))
    }
    window.addEventListener('pointermove', bouger)
    window.addEventListener('pointerup', lacher)
  }

  return (
    // Sur téléphone, l'écran est trop petit pour l'onglet et la
    // conversation : l'assistant prend tout l'écran (Seb, 16 octobre).
    <div
      className={`dx dx-chat-global dx-chat-bas${bureau ? '' : ' dx-chat-bas--plein'}`}
      style={{ height: bureau ? hauteur : undefined, display: etat.ouvert ? undefined : 'none' }}
    >
      {bureau && (
        <div
          className="dx-chat-poignee"
          role="separator"
          aria-orientation="horizontal"
          aria-label="Régler la hauteur de l’assistant"
          onPointerDown={redimensionner}
        />
      )}
      <Assistant
        orgId={etat.orgId}
        coutSaisonInitial={etat.coutSaison}
        contexte={contexte}
        memoire={`appli:${etat.orgId}`}
        onClose={etat.fermer}
        onFaire={faire}
      />
      {message && <div className="dx-toast" role="status">{message}</div>}
    </div>
  )
}
