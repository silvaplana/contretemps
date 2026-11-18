import HelloAssoCampagne from './HelloAssoCampagne.jsx'
import HelloAssoReglages from './HelloAssoReglages.jsx'
import HelloAssoTarifs from './HelloAssoTarifs.jsx'
import Impayes from './Impayes.jsx'
import { memberColumns, memberList } from './adherents.jsx'

// Déclaration du module HelloAsso (spec/core.md §9 bis,
// spec/modules/helloasso.md) : pas d'onglet ; sa ligne de Fonctionnalités
// porte la connexion de l'école (`settings`) ; la fiche d'un membre, la
// campagne de la saison (`memberFields`) ; une saison imposée par la
// campagne, le tableau des adhérents (`memberList`) et ses colonnes
// (`memberColumns`, adherents.jsx) ; « Impayés HelloAsso » à côté des
// adhérents (`adminTabs`).
export default {
  key: 'helloasso',
  tabs: [],
  settings: HelloAssoReglages,
  memberFields: HelloAssoCampagne,
  seasonPrices: HelloAssoTarifs,
  memberList,
  memberColumns,
  adminTabs: [{ value: 'helloasso-impayes', label: 'Impayés HelloAsso', Ecran: Impayes }],
}
