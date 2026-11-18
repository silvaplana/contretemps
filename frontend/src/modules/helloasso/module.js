import HelloAssoCampagne from './HelloAssoCampagne.jsx'
import HelloAssoReglages from './HelloAssoReglages.jsx'
import HelloAssoTarifs from './HelloAssoTarifs.jsx'
import { memberList } from './adherents.jsx'

// Déclaration du module HelloAsso (spec/core.md §9 bis,
// spec/modules/helloasso.md) : pas d'onglet ; sa ligne de Fonctionnalités
// porte la connexion de l'école (`settings`) ; la fiche d'un membre, la
// campagne de la saison (`memberFields`) ; une saison imposée par la
// campagne, le tableau des adhérents (`memberList`, adherents.jsx).
export default {
  key: 'helloasso',
  tabs: [],
  settings: HelloAssoReglages,
  memberFields: HelloAssoCampagne,
  seasonPrices: HelloAssoTarifs,
  memberList,
}
