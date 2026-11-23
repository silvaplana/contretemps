import { useEffect, useState } from 'react'
import { InstructionsInstallation } from '../components/InstructionsInstallation.jsx'
import Logo from '../components/Logo.jsx'
import * as installation from '../api/installation.js'
import { appliAndroid } from '../api/personnalisation.js'

// Plein écran, juste après une connexion réussie (voir App.jsx) — demande
// utilisateur du 2026-09-22 : remplace l'ancien encart de l'écran de
// connexion (7 jours de répit max, voir git history). Ne s'affiche QUE si
// l'appli n'est pas déjà installée et si "Ne plus me demander" n'a jamais
// été coché sur cet appareil (voir App.jsx et api/installation.js :
// neJamaisDemander) — sinon, redemande à CHAQUE connexion.
export default function InstallationScreen({ onContinuer, compteId, ecoleId }) {
  const mode = installation.useModeInstallation()
  const [neJamaisDemander, setNeJamaisDemander] = useState(false)
  // Invité sur l'appli Android (Seb 23/11) : le lien du fichier, au lieu de l'appli web.
  const [apk, setApk] = useState(null)
  useEffect(() => {
    if (!ecoleId || !installation.inviteAppliAndroid()) return
    appliAndroid(ecoleId).then(
      (a) => a.actif && a.url && setApk(a.url),
      () => {},
    )
  }, [ecoleId])
  // Devient vrai après un clic sur "Oui, installer" pour tout ce qui n'est
  // pas une installation en un appui (iOS, Safari Mac, Firefox, Android
  // hors Chrome...) : affiche alors les instructions pas-à-pas — pour
  // 'ouvrir-chrome' en particulier (Android), le message qui invite à
  // choisir Chrome (demande utilisateur du 2026-09-23) — avec un
  // "Continuer" pour sortir de cet écran une fois le geste fait (ou pas).
  // Seul 'bouton' (Chrome/Chromium, installation en un appui) déclenche
  // directement l'action sans passer par cet état.
  const [instructionsAffichees, setInstructionsAffichees] = useState(false)

  function continuer() {
    if (neJamaisDemander) installation.definirNeJamaisDemander()
    onContinuer()
  }

  async function installerMaintenant() {
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
      </div>

      {apk ? (
        <div className="installation-screen__choix">
          <a className="btn btn--primary btn--block" href={apk}>
            Télécharger l’appli Android
          </a>
          <p className="invitation-installation__texte">
            Ouvrez le fichier téléchargé, autorisez Chrome à installer des applis si le téléphone le demande, puis
            touchez Installer. Connectez-vous avec votre email et votre mot de passe.
          </p>
          <button type="button" className="btn btn--secondary btn--block" onClick={continuer}>
            Continuer dans le navigateur web
          </button>
        </div>
      ) : instructionsAffichees ? (
        <div className="invitation-installation">
          <InstructionsInstallation mode={mode} compteId={compteId} />
        </div>
      ) : (
        <div className="installation-screen__choix">
          <button type="button" className="btn btn--primary btn--block" onClick={installerMaintenant}>
            Oui, installer
          </button>
          <button type="button" className="btn btn--secondary btn--block" onClick={continuer}>
            Non merci, continuer dans le navigateur web
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
