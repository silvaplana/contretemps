// Coûts d'IA affichés en euros (Seb, 16 octobre). Anthropic facture en
// dollars et les coûts sont enregistrés en dollars ; le serveur donne le taux
// de la Banque centrale européenne (lu une fois par jour, voir
// backend/src/change/taux.py), chargé ici une fois par session.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

let eurParUsd = 0.9 // valeur de secours, remplacée dès que le taux est lu

export async function chargerTauxChange() {
  try {
    const reponse = await fetch(`${BASE_URL}/taux-change`)
    if (reponse.ok) eurParUsd = (await reponse.json()).eur_par_usd
  } catch {
    // hors ligne : la valeur de secours sert
  }
}

// « 0,045 € » : deux décimales, trois pour les petits montants.
export function enEuros(usd) {
  const euros = (usd ?? 0) * eurParUsd
  return `${euros.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: euros < 1 ? 3 : 2 })} €`
}
