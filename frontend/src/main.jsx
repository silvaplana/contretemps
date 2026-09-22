import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { installerIdentiteAppelant } from './api/identite.js'
import { ecouterInstallation } from './api/installation.js'

// Avant tout rendu : chaque appel à notre API porte l'id du profil actif
// (RBAC du serveur, voir api/identite.js).
installerIdentiteAppelant()
// Tout de suite : l'annonce "installable" du navigateur peut arriver avant
// le premier affichage (voir api/installation.js).
ecouterInstallation()

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
