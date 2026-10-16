import { StrictMode, Suspense, lazy } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { installerIdentiteAppelant } from './api/identite.js'
import { chargerParAdresse } from './api/apparence.js'
import { ecouterInstallation } from './api/installation.js'
import { pageDuHost } from './pagePublique/hote.js'

// <page>.<école>.contretemps.silvaplana.cloud : la page en ligne d'un
// fichier de l'appli (documents.md §5.5), sans le reste de l'appli.
const pagePublique = pageDuHost(window.location.hostname)
const PagePublique = lazy(() => import('./pagePublique/PagePublique.jsx'))

// Avant tout rendu : chaque appel à notre API porte l'id du profil actif
// (RBAC du serveur, voir api/identite.js).
if (!pagePublique) installerIdentiteAppelant()
// Tout de suite : l'annonce "installable" du navigateur peut arriver avant
// le premier affichage (voir api/installation.js).
if (!pagePublique) ecouterInstallation()
// L'apparence de l'école de l'adresse visitée (spec §2.7), avant même la
// page de connexion ; rien à faire sur l'adresse générique.
if (!pagePublique) chargerParAdresse()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {pagePublique ? (
      <Suspense fallback={null}>
        <PagePublique slug={pagePublique.page} />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
)

// Enregistre le service worker (voir public/sw.js) : sans lui, Samsung
// Internet/Chrome ne proposent qu'un simple raccourci de page pour "Ajouter
// à l'écran d'accueil" — avec le badge du navigateur collé sur l'icône —
// plutôt qu'une vraie appli installée avec l'icône Contretemps seule.
if (!pagePublique && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`)
  })
}
