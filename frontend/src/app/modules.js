// Les modules de l'appli Contretemps qui ont un onglet dans la barre du bas,
// dans l'ordre des onglets (spec/core.md §9 bis.2). Les onglets du core
// (Admin, Supervision, Profil) sont dans data/nav.js.
import choregraphies from '../modules/choregraphies/module.js'
import documents from '../modules/documents/module.js'
import finances from '../modules/finances/module.js'
import messagerie from '../modules/messagerie/module.js'
import presence from '../modules/presence/module.js'
import sessionClips from '../modules/session-clips/module.js'

export const MODULES = [presence, choregraphies, messagerie, documents, finances, sessionClips]
