// Service worker minimal, uniquement pour satisfaire les critères
// d'installabilité PWA (voir main.jsx) — Samsung Internet/Chrome
// n'affichent l'icône "Contretemps" pleine (sans le petit badge du
// navigateur) sur l'écran d'accueil que si le site est reconnu comme une
// vraie appli installable, pas un simple raccourci de page. Aucune mise en
// cache volontaire : chaque requête part directement au réseau, comme sans
// service worker — on ne veut pas d'un mode hors-ligne qui servirait de
// vieilles versions de l'app ou des données périmées (voir spec/SPEC.md,
// rien n'est prévu côté hors-ligne).
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request))
})
