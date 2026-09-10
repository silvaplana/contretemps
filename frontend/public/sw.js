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

// Notifications push (Web Push, voir spec/SPEC.md §8 et api/notifications.js) :
// `data` vient du backend (voir backend/src/notifications/notifications.py :
// envoyer_a_compte), un simple {title, body}. Si une fenêtre de l'appli est
// déjà au premier plan, elle a déjà vu le message en direct via SSE (voir
// App.jsx) — pas la peine d'AUSSI afficher une notification système.
self.addEventListener('push', (event) => {
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const dejaVisible = clients.some((c) => c.visibilityState === 'visible' && c.focused)
      if (dejaVisible) return
      const { title, body } = event.data.json()
      return self.registration.showNotification(title, {
        body,
        // Chemins RELATIFS (pas de "/" au début) : résolus par rapport à
        // l'URL de ce script lui-même (BASE_URL + "sw.js", voir main.jsx),
        // donc corrects aussi bien en dev (BASE_URL="/") qu'en prod
        // (BASE_URL="/contretemps/", voir vite.config.js) — un chemin
        // absolu "/icons/..." pointerait toujours à la racine du domaine,
        // jamais sous /contretemps/ en prod (piège déjà vu avec
        // site.webmanifest, voir sa note sur BASE_URL).
        icon: 'icons/icon-192.png',
        badge: 'icons/icon-192.png',
      })
    }),
  )
})

// Clic sur la notification : ramène au premier plan un onglet déjà ouvert
// s'il y en a un, sinon en ouvre un nouveau — jamais un 2e onglet en plus
// d'un existant.
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      if (clients.length > 0) return clients[0].focus()
      // `self.registration.scope`, pas "/" en dur : la racine de l'appli
      // est /contretemps/ en prod (voir BASE_URL, vite.config.js), pas la
      // racine du domaine silvaplana.cloud (qui héberge d'autres applis).
      return self.clients.openWindow(self.registration.scope)
    }),
  )
})
