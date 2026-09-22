import * as installation from '../api/installation.js'
import Icon from './Icon.jsx'

// Explication du geste d'installation, selon le navigateur (tout sauf
// l'installation en un appui, mode 'bouton') — utilisée par le menu ⋮ de
// l'en-tête (Header.jsx) et par l'invitation plein écran après connexion
// (screens/InstallationScreen.jsx). `compteId` : uniquement nécessaire pour
// le mode 'ouvrir-chrome', transmis à ouvrirDansChrome (voir
// api/installation.js) pour reconnecter automatiquement dans Chrome.
export function InstructionsInstallation({ mode, compteId }) {
  return mode === 'ouvrir-chrome' ? (
    <>
      <p className="invitation-installation__texte">
        Choisissez le navigateur <strong>Chrome</strong> à l’étape suivante pour une installation
        réussie.
      </p>
      <button
        type="button"
        className="btn btn--primary btn--block"
        onClick={() => installation.ouvrirDansChrome(compteId)}
      >
        Lancer l’installation
      </button>
    </>
  ) : mode?.startsWith('ios') ? (
    // Étapes fournies par l'utilisateur, testées sur iPhone (2026-09-21) —
    // les mêmes quel que soit le navigateur : la 1re ramène dans Safari.
    <ol className="invitation-installation__texte invitation-installation__etapes">
      <li>
        Ouvrez ce site dans <strong>Safari</strong>
        {mode === 'ios-ouvrir-safari' && ' (menu ⋯ ou « Ouvrir dans le navigateur »)'}.
      </li>
      <li>
        Appuyez sur le bouton <strong>Partager</strong> <Icon name="partager" size={16} /> — le carré avec une
        flèche vers le haut.
      </li>
      <li>
        Faites défiler et choisissez <strong>« Sur l’écran d’accueil »</strong>.
      </li>
      <li>
        Activez <strong>« Ouvrir comme app web »</strong> si l’option apparaît.
      </li>
      <li>
        Appuyez sur <strong>Ajouter</strong>.
      </li>
    </ol>
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
