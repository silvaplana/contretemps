import { useState } from 'react'
import * as installation from '../api/installation.js'
import Icon from './Icon.jsx'

// Invitation à installer Contretemps comme une appli (voir
// api/installation.js). N'apparaît pas si l'appli est déjà installée, ou
// si le navigateur ne permet rien.
// - variante "encart" (écran de connexion) : "Plus tard" la masque 7 jours ;
// - variante "ligne" (Profil) : toujours là tant que ce n'est pas fait.
export default function InvitationInstallation({ variante = 'encart' }) {
  const mode = installation.useModeInstallation()
  const [masquee, setMasquee] = useState(() => variante === 'encart' && installation.reporteRecemment())
  const [instructionsOuvertes, setInstructionsOuvertes] = useState(variante === 'encart')

  if (!mode || masquee) return null

  const instructions =
    mode === 'ios-ouvrir-safari' ? (
      <p className="invitation-installation__texte">
        Pour installer l’application, ouvrez d’abord cette page dans <strong>Safari</strong> (menu ⋯ ou
        « Ouvrir dans le navigateur »).
      </p>
    ) : mode === 'ios' ? (
      <p className="invitation-installation__texte">
        Touchez <Icon name="partager" size={16} /> <strong>Partager</strong> en bas de Safari, puis{' '}
        <strong>« Sur l’écran d’accueil »</strong>.
      </p>
    ) : mode === 'mac-safari' ? (
      <p className="invitation-installation__texte">
        Dans Safari, menu <strong>Fichier</strong> puis <strong>« Ajouter au Dock »</strong> (macOS Sonoma ou
        plus récent).
      </p>
    ) : mode === 'firefox' ? (
      <p className="invitation-installation__texte">
        Firefox ne sait pas installer d’application web : ouvrez cette page dans <strong>Chrome</strong> ou{' '}
        <strong>Edge</strong>, qui vous proposeront de l’installer.
      </p>
    ) : null

  if (variante === 'ligne') {
    return (
      <>
        <button
          type="button"
          className="settings-row settings-row--button"
          onClick={() => (mode === 'bouton' ? installation.installer() : setInstructionsOuvertes((o) => !o))}
        >
          <span>Installer l’application</span>
          <Icon name={mode === 'bouton' ? 'chevronRight' : instructionsOuvertes ? 'chevronDown' : 'chevronRight'} size={18} />
        </button>
        {mode !== 'bouton' && instructionsOuvertes && <div className="invitation-installation">{instructions}</div>}
      </>
    )
  }

  return (
    <div className="invitation-installation">
      <p className="invitation-installation__titre">Installez l’application Contretemps</p>
      <p className="invitation-installation__texte">
        Une icône pour l’ouvrir directement, dans sa propre fenêtre, et les notifications des messages.
      </p>
      {mode === 'bouton' ? (
        <button type="button" className="btn btn--primary btn--block" onClick={() => installation.installer()}>
          Installer l’application
        </button>
      ) : (
        instructions
      )}
      <button
        type="button"
        className="btn btn--link"
        onClick={() => {
          installation.reporter()
          setMasquee(true)
        }}
      >
        Plus tard
      </button>
    </div>
  )
}
