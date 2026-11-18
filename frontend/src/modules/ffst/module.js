import FfstReglages from './FfstReglages.jsx'
import * as api from './api.js'

// Déclaration du module FFST (spec/core.md §9 bis, spec/modules/ffst.md) :
// l'onglet FFST des admins (les listes lues sur le site de la fédération),
// sa ligne de Fonctionnalités (les identifiants du club, `settings`) et sa
// colonne « Statut FFST » dans le tableau des adhérents (`memberColumns`).

// → null (pas connecté, module éteint) ou { members: { [fiche]: { status } } }.
async function charger(ecoleId) {
  try {
    const lu = await api.adherents(ecoleId)
    return lu.connected ? lu : null
  } catch {
    return null // module éteint (404) ou hors ligne
  }
}

export default {
  key: 'ffst',
  tabs: [{ key: 'ffst', label: 'FFST', icon: 'fileCheck', roles: ['admin'] }],
  settings: FfstReglages,
  memberColumns: {
    charger,
    colonnes: [
      {
        key: 'ffst_status',
        label: 'Statut FFST',
        nature: 'Calculé',
        detail: 'FFST',
        texte: (l) => l?.status ?? '',
      },
    ],
    // « Rafraîchir » du tableau relit aussi le site de la FFST.
    rafraichir: (ecoleId) => api.lire(ecoleId).catch(() => null),
  },
}
