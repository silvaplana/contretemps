import MailReglages from './MailReglages.jsx'

// Déclaration du sous-module Mail de la Messagerie (spec/core.md §9 bis,
// spec/modules/mail.md) : pas d'onglet à lui, la puce Mail de Messages
// (MessagerieScreen.jsx) ; en retrait sous Messagerie dans Fonctionnalités.
export default {
  key: 'mail',
  tabs: [],
  sousModule: true,
  settings: MailReglages,
}
