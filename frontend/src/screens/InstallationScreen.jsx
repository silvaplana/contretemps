import { useEffect, useState } from 'react'
import { InstructionsInstallation } from '../components/InstructionsInstallation.jsx'
import Logo from '../components/Logo.jsx'
import * as installation from '../api/installation.js'
import { useApparence } from '../api/apparence.js'
import * as personnalisationApi from '../api/personnalisation.js'

// Téléphone Android dans un navigateur (pas déjà dans l'appli Android).
const SUR_ANDROID = /Android/i.test(navigator.userAgent) && !window.Capacitor?.isNativePlatform?.()

// Plein écran, juste après une connexion réussie (voir App.jsx) — demande
// utilisateur du 2026-09-22 : remplace l'ancien encart de l'écran de
// connexion (7 jours de répit max, voir git history). Ne s'affiche QUE si
// l'appli n'est pas déjà installée et si "Ne plus me demander" n'a jamais
// été coché sur cet appareil (voir App.jsx et api/installation.js :
// neJamaisDemander) — sinon, redemande à CHAQUE connexion.
export default function InstallationScreen({ onContinuer, compteId, ecoleId }) {
  const mode = installation.useModeInstallation()
  const [neJamaisDemander, setNeJamaisDemander] = useState(false)
  // Devient vrai après un clic sur "Oui, installer" pour tout ce qui n'est
  // pas une installation en un appui (iOS, Safari Mac, Firefox, Android
  // hors Chrome...) : affiche alors les instructions pas-à-pas — pour
  // 'ouvrir-chrome' en particulier (Android), le message qui invite à
  // choisir Chrome (demande utilisateur du 2026-09-23) — avec un
  // "Continuer" pour sortir de cet écran une fois le geste fait (ou pas).
  // Seul 'bouton' (Chrome/Chromium, installation en un appui) déclenche
  // directement l'action sans passer par cet état.
  const [instructionsAffichees, setInstructionsAffichees] = useState(false)

  // Appli Android de l'école (Seb 18/11/2026, maquette
  // https://claude.ai/artifact/D1ebpynBsJdPyGj8qpui93) : sur Android, quand
  // l'école en a une (réglage « Appli Android »), on propose de la
  // télécharger à la place de l'installation dans Chrome. iPhone : inchangé.
  const [appli, setAppli] = useState(null)
  const [appliTelechargee, setAppliTelechargee] = useState(false)
  const apparence = useApparence()
  useEffect(() => {
    if (!SUR_ANDROID || !ecoleId) return
    personnalisationApi
      .appliAndroid(ecoleId)
      .then((etat) => etat.prete && setAppli(etat))
      .catch(() => {})
  }, [ecoleId])

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

  if (appli) {
    const fichier = appli.url.split('/').pop()
    return (
      <div className="login-screen installation-screen">
        <div className="login-screen__brand">
          <Logo size={90} />
          <h1>{appliTelechargee ? 'Installer l’appli' : 'Installez l’application'}</h1>
        </div>
        {appliTelechargee ? (
          <>
            <ol className="installation-screen__etapes">
              <li>
                Ouvrez le fichier <b>{fichier}</b> qui vient de se télécharger.
              </li>
              <li>Si le téléphone le demande, autorisez Chrome à installer des applis.</li>
              <li>
                Touchez <b>Installer</b>, puis <b>Ouvrir</b>.
              </li>
              <li>Connectez-vous avec votre email et votre mot de passe.</li>
            </ol>
            <button type="button" className="btn btn--link" onClick={continuer}>
              Continuer dans le navigateur
            </button>
          </>
        ) : (
          <div className="installation-screen__choix">
            <p className="muted">L’appli Android {apparence.nomAppli ? `de ${apparence.nomAppli} ` : ''}permet aussi de filmer.</p>
            <a className="btn btn--primary btn--block" href={appli.url} onClick={() => setAppliTelechargee(true)}>
              Télécharger l’appli Android
            </a>
            <button type="button" className="btn btn--secondary btn--block" onClick={continuer}>
              Non merci, continuer dans le navigateur web
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="login-screen installation-screen">
      <div className="login-screen__brand">
        <Logo size={90} />
        <h1>Installez l’application</h1>
      </div>

      {instructionsAffichees ? (
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
