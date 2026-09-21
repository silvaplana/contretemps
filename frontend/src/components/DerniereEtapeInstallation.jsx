import { useState } from 'react'
import * as installation from '../api/installation.js'
import Modal from './Modal.jsx'

// "Dernière étape" : page rouverte dans Chrome depuis Samsung Internet par
// "Ouvrir dans Chrome" (voir api/installation.js : ouvrirDansChrome, qui
// ajoute ?installer=1). Chrome interdit toute installation sans un appui de
// l'utilisateur : on la ramène à UN appui, avant même la connexion
// (demande du 2026-09-21).
export default function DerniereEtapeInstallation() {
  const mode = installation.useModeInstallation()
  const [ouverte, setOuverte] = useState(installation.arriveePourInstaller)
  const [installee, setInstallee] = useState(false)

  function fermer() {
    installation.oublierArriveePourInstaller()
    setOuverte(false)
  }

  async function installer() {
    if ((await installation.installer()) === 'accepted') setInstallee(true)
  }

  if (!ouverte) return null
  // Déjà installée (ou ouverte dans l'appli elle-même) : plus rien à faire.
  if (installation.estInstallee()) return null

  if (installee) {
    return (
      <Modal title="Contretemps est installé" onClose={fermer}>
        <p>Retrouvez son icône sur l’écran d’accueil et dans la liste de vos applications.</p>
        <button type="button" className="btn btn--primary btn--block" onClick={fermer}>
          Fermer
        </button>
      </Modal>
    )
  }

  return (
    <Modal title="Dernière étape : installer Contretemps" onClose={fermer}>
      {mode === 'bouton' ? (
        <>
          <p>Un appui, et Contretemps devient une vraie application sur votre téléphone.</p>
          <button type="button" className="btn btn--primary btn--block" onClick={installer}>
            Installer
          </button>
        </>
      ) : (
        <p>
          Touchez <strong>⋮</strong> en haut à droite de Chrome, puis <strong>« Installer l’application »</strong>.
          <span className="muted"> Un bouton Installer apparaîtra ici dès que Chrome le permet.</span>
        </p>
      )}
      <button type="button" className="btn btn--link" onClick={fermer}>
        Plus tard
      </button>
    </Modal>
  )
}
