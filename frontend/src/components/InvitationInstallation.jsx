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

  const instructions = <InstructionsInstallation mode={mode} />

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

// Explication du geste d'installation, selon le navigateur (tout sauf
// l'installation en un appui, mode 'bouton'). Aussi utilisée par le menu ⋮
// de l'en-tête (voir Header.jsx).
export function InstructionsInstallation({ mode }) {
  return mode === 'ouvrir-chrome' ? (
    <>
      <p className="invitation-installation__texte">
        Pour une vraie application, avec son icône sur l’écran d’accueil, ouvrez cette page dans{' '}
        <strong>Chrome</strong> et installez-la depuis Chrome (vous devrez vous y reconnecter).
      </p>
      <button type="button" className="btn btn--primary btn--block" onClick={installation.ouvrirDansChrome}>
        Ouvrir dans Chrome
      </button>
      {installation.installationDirectePossible() && (
        <button type="button" className="btn btn--link" onClick={() => installation.installer()}>
          Installer quand même avec ce navigateur
        </button>
      )}
    </>
  ) : mode === 'ios-ouvrir-safari' ? (
    <p className="invitation-installation__texte">
      Pour installer l’application, ouvrez d’abord cette page dans <strong>Safari</strong> (menu ⋯ ou
      « Ouvrir dans le navigateur »).
    </p>
  ) : mode === 'ios' ? (
    <p className="invitation-installation__texte">
      Touchez <Icon name="partager" size={16} /> <strong>Partager</strong> dans Safari — en bas de l’écran, ou
      dans le menu <strong>⋯</strong> sur les iPhone récents, en haut à droite sur iPad —, puis{' '}
      <strong>« Sur l’écran d’accueil »</strong> (faites défiler la liste si besoin).
    </p>
  ) : mode === 'ios-chrome' ? (
    <p className="invitation-installation__texte">
      Touchez <Icon name="partager" size={16} /> <strong>Partager</strong>, en haut à droite dans la barre
      d’adresse de Chrome, puis <strong>« Sur l’écran d’accueil »</strong>. Si l’option n’apparaît pas,
      ouvrez cette page dans <strong>Safari</strong>.
    </p>
  ) : mode === 'ios-autre' ? (
    <p className="invitation-installation__texte">
      Touchez <Icon name="partager" size={16} /> <strong>Partager</strong> dans le menu du navigateur, puis{' '}
      <strong>« Sur l’écran d’accueil »</strong>. Si l’option n’apparaît pas, ouvrez cette page dans{' '}
      <strong>Safari</strong>.
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
}
