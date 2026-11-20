// Une demande au serveur qui échoue (réseau pas encore prêt au réveil du
// téléphone, serveur qui redémarre pendant une mise en ligne) est refaite
// toute seule, au lieu de laisser l'écran vide (Seb, 20/11/2026).
// `erreur.definitive` : inutile de réessayer (ex. session expirée).
export async function reessayer(appel, delais = [2000, 5000, 10000]) {
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
