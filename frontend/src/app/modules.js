// Les modules de l'appli Contretemps côté écran, dans l'ordre des onglets de
// la barre du bas (spec/core.md §9 bis.2). Un module peut ne pas avoir
// d'onglet (`tabs: []`) et porter des réglages (`settings` : composant
// affiché sur sa ligne de Fonctionnalités). Les onglets du core (Admin,
// Supervision, Profil) sont dans data/nav.js.
import choregraphies from '../modules/choregraphies/module.js'
import documents from '../modules/documents/module.js'
import finances from '../modules/finances/module.js'
import helloasso from '../modules/helloasso/module.js'
import messagerie from '../modules/messagerie/module.js'
import presence from '../modules/presence/module.js'
import sessionClips from '../modules/session-clips/module.js'

export const MODULES = [presence, choregraphies, messagerie, documents, finances, sessionClips, helloasso]
