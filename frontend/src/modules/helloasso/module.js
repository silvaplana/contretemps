import HelloAssoCampagne from './HelloAssoCampagne.jsx'
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
// (`memberColumns`, adherents.jsx) ; « Impayés HelloAsso » à côté des
// adhérents (`adminTabs`).
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
  memberList,
  memberColumns,
  adminTabs: [{ value: 'helloasso-impayes', label: 'Impayés HelloAsso', Ecran: Impayes }],
}
