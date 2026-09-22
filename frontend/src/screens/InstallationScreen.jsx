import { useState } from 'react'
import { InstructionsInstallation } from '../components/InvitationInstallation.jsx'
import Logo from '../components/Logo.jsx'
import * as installation from '../api/installation.js'

// Plein écran, juste après une connexion réussie (voir App.jsx) — demande
// utilisateur du 2026-09-22 : remplace l'ancien encart de l'écran de
// connexion (7 jours de répit max, voir git history). Ne s'affiche QUE si
// l'appli n'est pas déjà installée et si "Ne plus me demander" n'a jamais
// été coché sur cet appareil (voir App.jsx et api/installation.js :
// neJamaisDemander) — sinon, redemande à CHAQUE connexion.
export default function InstallationScreen({ onContinuer }) {
  const mode = installation.useModeInstallation()
  const [neJamaisDemander, setNeJamaisDemander] = useState(false)
  // Devient vrai après un clic sur "Oui, installer" pour les navigateurs
  // sans action directe possible (iOS, Safari Mac, Firefox...) : affiche
  // alors les instructions pas-à-pas, avec un "Continuer" pour sortir de cet
  // écran une fois le geste fait (ou pas). Pour 'bouton'/'ouvrir-chrome',
  // l'action déclenche directement l'installation/la redirection — ce
  // sous-écran n'est jamais affiché.
  const [instructionsAffichees, setInstructionsAffichees] = useState(false)

  function continuer() {
    if (neJamaisDemander) installation.definirNeJamaisDemander()
    onContinuer()
  }

  async function installerMaintenant() {
    if (mode === 'ouvrir-chrome') {
      // Quitte cette page (réouverture dans Chrome, voir
      // api/installation.js: ouvrirDansChrome) — rien à continuer ici.
      installation.ouvrirDansChrome()
      return
    }
    if (mode === 'bouton') {
      // Quelle que soit la réponse au vrai dialogue du navigateur, on
      // continue ensuite dans l'appli (demande explicite) — le badge
      // "Installer l'application" (Profil) reste disponible si annulé.
      await installation.installer()
      continuer()
      return
    }
    setInstructionsAffichees(true)
  }

  return (
    <div className="login-screen installation-screen">
      <div className="login-screen__brand">
        <Logo size={90} />
        <h1>Installez l’application</h1>
        <p>
          Une icône sur l’écran d’accueil, dans sa propre fenêtre, et les notifications des nouveaux
          messages — même appli fermée.
        </p>
        {mode === 'ouvrir-chrome' && (
          <p className="invitation-installation__texte">
            Sur Android, seul <strong>Chrome</strong> sait créer une vraie icône sur l’écran d’accueil —
            en cliquant sur « Oui, installer », on vous proposera d’ouvrir cette page dans Chrome.
          </p>
        )}
      </div>

      {instructionsAffichees ? (
        <div className="invitation-installation">
          <InstructionsInstallation mode={mode} />
        </div>
      ) : (
        <div className="installation-screen__choix">
          <button type="button" className="btn btn--primary btn--block" onClick={installerMaintenant}>
            Oui, installer
          </button>
          <button type="button" className="btn btn--secondary btn--block" onClick={continuer}>
            Non merci
          </button>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={neJamaisDemander}
              onChange={(e) => setNeJamaisDemander(e.target.checked)}
            />
            Ne plus me demander
          </label>
        </div>
      )}

      {instructionsAffichees && (
        <button type="button" className="btn btn--link" onClick={continuer}>
          Continuer
        </button>
      )}
    </div>
  )
}
