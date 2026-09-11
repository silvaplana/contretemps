// Recopie de backend/src/inscriptions/saison.py:saison_actuelle — juste
// pour l'affichage côté formulaire (voir App.jsx). La saison qui fait
// foi reste celle calculée côté serveur à la soumission (voir
// Confirmation.jsx, qui affiche resultat.saison).

export function saisonActuelle(aujourdhui = new Date()) {
  const annee = aujourdhui.getFullYear()
  const mois = aujourdhui.getMonth() + 1 // getMonth() est 0-indexé
  return mois >= 8 ? `${annee}-${annee + 1}` : `${annee - 1}-${annee}`
}
