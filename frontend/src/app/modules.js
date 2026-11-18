// Les modules de l'appli Contretemps côté écran, dans l'ordre des onglets de
// la barre du bas (spec/core.md §9 bis.2). `tabs` peut être une fonction
// de ce que le module a lu pour l'école (ses blogs, pour Publications) ;
// leurs clés commencent alors par `tabPrefix` (data/nav.js). Un module peut ne pas avoir
// d'onglet (`tabs: []`) et porter des réglages (`settings` : composant
// affiché sur sa ligne de Fonctionnalités) et un bloc en tête de la fiche
// d'un membre (`memberFields`, voir ChampsMembres.jsx), et des tarifs
// imposés qui remplacent les nôtres (`seasonPrices`, voir Tarifs.jsx), et
// les membres de la saison quand c'est lui qui les apporte (`memberList` :
// ses colonnes, le verrou de création, sa part de la fiche ; voir
// AdminEleves.jsx et listeImposee ci-dessous), et ses colonnes et boutons
// dans le tableau des membres (`memberColumns`, voir colonnesModules
// ci-dessous), et des sous-onglets d'Admin (`adminTabs` : { value, label,
// Ecran }, après Cours, module allumé ; voir AdminScreen.jsx). Les onglets
// du core (Admin, Supervision, Profil) sont dans data/nav.js.
import choregraphies from '../modules/choregraphies/module.js'
import documents from '../modules/documents/module.js'
import ffst from '../modules/ffst/module.js'
import finances from '../modules/finances/module.js'
import helloasso from '../modules/helloasso/module.js'
import mail from '../modules/mail/module.js'
import messagerie from '../modules/messagerie/module.js'
import presence from '../modules/presence/module.js'
import publications from '../modules/publications/module.js'
import sessionClips from '../modules/session-clips/module.js'
import trials from '../modules/trials/module.js'

// Publications en premier : ses onglets (Actus…) viennent juste après Admin (Seb, 6 novembre).
export const MODULES = [publications, presence, choregraphies, messagerie, mail, documents, finances, sessionClips, helloasso, ffst, trials]

// Le module qui impose les membres de la saison affichée (HelloAsso,
// spec/modules/helloasso.md §7) : { module, liste: son `memberList`, donnees }, ou
// null (le tableau de l'école, comme toujours).
export async function listeImposee(ecoleId) {
  for (const m of MODULES.filter((x) => x.memberList)) {
    const donnees = await m.memberList.charger(ecoleId)
    if (donnees) return { module: m.key, liste: m.memberList, donnees }
  }
  return null
}

// Les colonnes et boutons que les modules ajoutent au tableau d'Admin >
// Élèves (spec/core.md §11.1) : chaque `memberColumns` lit ses données
// (`charger` → { members: { [fiche]: ligne } }, ou null : rien à montrer,
// module éteint compris) ; chaque colonne reçoit `ligne(ficheId)`.
export async function colonnesModules(ecoleId) {
  const lus = await Promise.all(
    MODULES.filter((m) => m.memberColumns).map(async (m) => ({ m, donnees: await m.memberColumns.charger(ecoleId) })),
  )
  return lus
    .filter(({ donnees }) => donnees)
    .flatMap(({ m, donnees }) =>
      m.memberColumns.colonnes.map((c) => ({ ...c, module: m.key, ligne: (ficheId) => donnees.members[ficheId] })),
    )
}

// « Rafraîchir » relit aussi ce que les modules montrent (listes FFST…).
export function rafraichirColonnes(ecoleId) {
  return Promise.all(MODULES.filter((m) => m.memberColumns?.rafraichir).map((m) => m.memberColumns.rafraichir(ecoleId)))
}
