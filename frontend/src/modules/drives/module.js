import DrivesReglages from './DrivesReglages.jsx'
import * as api from './api.js'

// Drives du club (spec/core.md §3) : pas d'onglet ; la ligne « Drives du
// club » d'Admin › École › Connexions, faite comme celle des boîtes mail.
// Les autres modules s'en servent (Import auto pièces).
export default {
  key: 'drives',
  tabs: [],
  connection: {
    label: 'Drives du club',
    Reglages: DrivesReglages,
    connecte: (ecoleId) => api.etat(ecoleId).then((e) => Boolean(e?.connected && !e.drives?.some((d) => d.cut))),
  },
}
