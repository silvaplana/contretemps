// Libellés du statut de paiement d'un élève (voir spec/SPEC.md §6.4 et
// AdminEleves.jsx) — la valeur ('en_cours'/'paye') est celle stockée côté
// backend (colonne statut_paiement, voir backend/src/eleves/models.py).
export const paiementLabels = {
  en_cours: 'En cours',
  paye: 'Payé',
}
