import { useState } from 'react'
import * as installation from '../api/installation.js'

// Bandeau "Installer l'application" — arrivée dans Chrome depuis "Lancer
// l'installation" (Samsung Internet, voir api/installation.js :
// ouvrirDansChrome/compteDepuisHandoff). Demande utilisateur du 2026-09-23 :
// pas un 2e écran plein écran bloquant juste après avoir déjà dû choisir
// Chrome — direct dans l'appli fonctionnelle, avec juste ce bandeau non
// bloquant pour le geste que Chrome exige (un vrai clic, aucun moyen de
// déclencher l'installation tout seul). Ne s'affiche QUE si Chrome a bien
// annoncé l'appli installable (mode 'bouton') : censé être systématique ici
// (on vient d'y arriver spécialement pour ça), sinon rien à proposer dans
// un espace aussi compact.
export default function BandeauInstallation({ visible, onTermine }) {
  const mode = installation.useModeInstallation()
  const [masque, setMasque] = useState(false)
  const [enCours, setEnCours] = useState(false)

  if (!visible || masque || mode !== 'bouton') return null

  async function installer() {
    setEnCours(true)
    await installation.installer()
    setMasque(true)
    onTermine?.()
  }

  return (
    <div className="bandeau-notifications" role="status">
      <p>Installez l’application d’un geste : une icône sur l’écran d’accueil.</p>
      <div className="bandeau-notifications__actions">
        <button
          type="button"
          className="btn btn--link"
          onClick={() => {
            setMasque(true)
            onTermine?.()
          }}
        >
          Plus tard
        </button>
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={installer}>
          Installer
        </button>
      </div>
    </div>
  )
}
