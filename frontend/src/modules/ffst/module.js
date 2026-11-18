import { createElement } from 'react'
import ActionsFfst from './ActionsFfst.jsx'
import FfstReglages from './FfstReglages.jsx'
import * as api from './api.js'

// Déclaration du module FFST (spec/core.md §9 bis, spec/modules/ffst.md) :
// l'onglet FFST des admins (les listes lues sur le site de la fédération),
// sa ligne d'Admin › École › Connexions (les identifiants du club,
// `connection`) et ses
// colonnes « Statut FFST » et « Actions FFST » dans le tableau des adhérents
// (`memberColumns`).

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
  connection: {
    label: 'Site de la FFST',
    Reglages: FfstReglages,
    connecte: (ecoleId) => api.etat(ecoleId).then((e) => Boolean(e?.connected)),
  },
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
      {
        key: 'ffst_actions',
        label: 'Actions FFST',
        nature: 'Bouton',
        detail: 'FFST',
        texte: () => '',
        // Un composant (ses boutons ont un état), pas un simple rendu.
        cellule: (props) => createElement(ActionsFfst, props),
      },
    ],
    // « Rafraîchir » du tableau relit aussi le site de la FFST.
    rafraichir: (ecoleId) => api.lire(ecoleId).catch(() => null),
  },
}
