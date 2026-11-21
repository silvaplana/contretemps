// Une demande au serveur qui échoue (réseau pas encore prêt au réveil du
// téléphone, serveur qui redémarre pendant une mise en ligne) est refaite
// toute seule, au lieu de laisser l'écran vide (Seb, 20/11/2026).
// Pendant un peu plus de 3 minutes : une mise en ligne coupe le serveur
// plus de 17 s (« 0 élève » à 1 h 10 le 21/11, pendant la mise en ligne).
// `erreur.definitive` : inutile de réessayer (ex. session expirée).
const DELAIS = [2000, 5000, 10000, 20000, 30000, 30000, 30000, 30000, 30000]
export async function reessayer(appel, delais = DELAIS) {
  for (const delai of delais) {
    try {
      return await appel()
    } catch (erreur) {
      if (erreur?.definitive) throw erreur
      await new Promise((fin) => setTimeout(fin, delai))
    }
  }
  return appel()
}
