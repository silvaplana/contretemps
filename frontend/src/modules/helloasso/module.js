import HelloAssoCampagne from './HelloAssoCampagne.jsx'
import HelloAssoEditionSaison from './HelloAssoEditionSaison.jsx'
import HelloAssoReglages from './HelloAssoReglages.jsx'
import HelloAssoTarifs from './HelloAssoTarifs.jsx'
import Impayes from './Impayes.jsx'
import { memberColumns, memberList } from './adherents.jsx'
import * as api from './api.js'

// Déclaration du module HelloAsso (spec/core.md §9 bis,
// spec/modules/helloasso.md) : pas d'onglet ; sa ligne d'Admin › École ›
// Connexions porte la connexion de l'école (`connection`) ; la fiche d'un membre, la
// campagne de la saison (`memberFields`) ; une saison imposée par la
// campagne, le tableau des adhérents (`memberList`) et ses colonnes
// (`memberColumns`, adherents.jsx) ; « Paiements HelloAsso » à côté des
// adhérents (`adminTabs`, pastille = nombre d'impayés) ; le choix de la saison dans « Éditer la saison »
// (`seasonEditor`).
export default {
  key: 'helloasso',
  tabs: [],
  connection: {
    label: 'HelloAsso',
    Reglages: HelloAssoReglages,
    connecte: (ecoleId) => api.etat(ecoleId).then((e) => Boolean(e?.connected)),
  },
  memberFields: HelloAssoCampagne,
  seasonPrices: HelloAssoTarifs,
  seasonEditor: HelloAssoEditionSaison,
  memberList,
  memberColumns,
  adminTabs: [
    {
      value: 'helloasso-impayes',
      label: 'À encaisser',
      Ecran: Impayes,
      // Pastille : les échéances dépassées sans paiement (Seb, 18 novembre 2026).
      badge: (ecoleId) => api.impayes(ecoleId).then((r) => (r.campaign ? r.upcoming.filter((e) => e.overdue).length : 0)),
    },
  ],
}
