// Coût de la lecture automatique d'une fiche papier, facturé en dollars
// par Anthropic (voir backend/src/inscriptions/lecture_fiche.py).
export function formaterCout(coutUsd) {
  return `${coutUsd.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 3 })} $`
}
