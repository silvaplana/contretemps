import MailReglages from './MailReglages.jsx'
import * as api from './api.js'

// Déclaration du sous-module Mail de la Messagerie (spec/core.md §9 bis,
// spec/modules/mail.md) : pas d'onglet à lui, la puce Mail de Messages
// (MessagerieScreen.jsx) ; en retrait sous Messagerie dans Fonctionnalités ;
// la boîte du club se connecte dans Admin › École › Connexions (`connection`).
export default {
  key: 'mail',
  tabs: [],
  sousModule: true,
  connection: {
    label: 'Boîte mail du club',
    Reglages: MailReglages,
    // Une boîte coupée compte « à connecter » (§4 bis : toutes les boîtes).
    connecte: (ecoleId) => api.etat(ecoleId).then((e) => Boolean(e?.connected && !e.boxes?.some((b) => b.cut))),
  },
}
