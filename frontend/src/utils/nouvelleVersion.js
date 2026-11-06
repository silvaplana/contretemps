// Une PWA restée ouverte en arrière-plan garde l'ancien code après une mise
// en ligne. Au retour au premier plan, si l'index.html en ligne annonce un
// autre bundle que celui qui tourne, l'appli se recharge toute seule, sans
// rien demander (Seb, 6 novembre 2026). index.html est servi sans cache.
export function rechargerSiNouvelleVersion() {
  const actuel = document.querySelector('script[type="module"][src*="/assets/index-"]')?.getAttribute('src')
  if (!actuel) return // en développement (npm run dev), pas de bundle
  document.addEventListener('visibilitychange', async () => {
    if (document.visibilityState !== 'visible') return
    try {
      const html = await (await fetch(import.meta.env.BASE_URL, { cache: 'no-store' })).text()
      const enLigne = html.match(/src="([^"]*\/assets\/index-[^"]+\.js)"/)?.[1]
      if (enLigne && enLigne !== actuel) window.location.reload()
    } catch {
      // Hors ligne : on garde la version qui tourne.
    }
  })
}
