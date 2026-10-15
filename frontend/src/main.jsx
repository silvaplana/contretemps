import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { installerIdentiteAppelant } from './api/identite.js'
import { chargerParAdresse } from './api/apparence.js'
import { ecouterInstallation } from './api/installation.js'

// Avant tout rendu : chaque appel à notre API porte l'id du profil actif
// (RBAC du serveur, voir api/identite.js).
installerIdentiteAppelant()
// Tout de suite : l'annonce "installable" du navigateur peut arriver avant
// le premier affichage (voir api/installation.js).
ecouterInstallation()
// L'apparence de l'école de l'adresse visitée (spec §2.7), avant même la
// page de connexion ; rien à faire sur l'adresse générique.
chargerParAdresse()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// Enregistre le service worker (voir public/sw.js) : sans lui, Samsung
// Internet/Chrome ne proposent qu'un simple raccourci de page pour "Ajouter
// à l'écran d'accueil" — avec le badge du navigateur collé sur l'icône —
// plutôt qu'une vraie appli installée avec l'icône Contretemps seule.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`)
  })
}
