// Session (voir spec/SPEC.md §2.2) : le PROFIL ACTIF (id de la fiche) et
// le JETON signé remis par le serveur à la connexion. Les deux partent
// avec chaque requête (voir api/identite.js) : le serveur vérifie le jeton,
// et que le profil appartient bien à l'adresse email connectée.
//
// Deux niveaux :
// - EN MÉMOIRE (`ouvrirSession`) : la session en cours dans cet onglet,
//   dès la connexion ;
// - MÉMORISÉE dans localStorage (`sauvegarderCompte`) : pour rouvrir
//   l'appli sans se reconnecter (30 jours, prolongés à chaque usage).
//   Survit à la fermeture de l'onglet/l'appli (web, PWA installée,
//   Android, iOS — même mécanisme partout), mais reste propre à CET
//   appareil/navigateur. Écrite seulement une fois l'écran d'installation
//   passé (voir App.jsx) : inutile de la laisser dans un navigateur qu'on
//   quitte aussitôt pour Chrome.
const CLE = 'contretemps:compteId'
// Jeton de session, et (Superuser seulement, §2.5) l'école qu'il a choisie
// (il n'appartient à aucune). Effacés avec le reste.
const CLE_JETON = 'contretemps:jeton'
const CLE_ECOLE_CHOISIE = 'contretemps:ecoleChoisie'
// Dernier écran affiché (onglet du bas, sous-onglet d'Admin) : l'appli y
// revient à la prochaine ouverture (demande utilisateur du 2026-10-02).
// Rangé à côté du jeton de session, pas dedans : le jeton est signé par le
// serveur et ne se modifie pas sur l'appareil.
const PREFIXE_ECRAN = 'contretemps:ecran:'

// Toujours défensif (try/catch) : localStorage peut lever (navigation
// privée sur certains navigateurs, stockage désactivé...) — jamais une
// raison de planter l'appli, juste de retomber sur l'écran de connexion.

export function lireCompteSauvegarde() {
  try {
    const valeur = localStorage.getItem(CLE)
    return valeur ? Number(valeur) : null
  } catch {
    return null
  }
}

// --- Session en cours (mémoire) ---

let compteActif = null
let jetonActif = null

export function ouvrirSession(compteId, jeton) {
  compteActif = compteId
  if (jeton) jetonActif = jeton
}

// Ce que chaque requête envoie : la session en cours, sinon celle
// mémorisée (reprise à l'ouverture de l'appli).
export const compteEnCours = () => compteActif ?? lireCompteSauvegarde()
export const jetonEnCours = () => jetonActif ?? lire(CLE_JETON)

// Jeton prolongé par le serveur, ou neuf après une bascule de profil ou un
// changement de mot de passe : remplace l'ancien, mémorisé compris s'il y
// a une session mémorisée.
export function remplacerJeton(jeton) {
  jetonActif = jeton
  if (lireCompteSauvegarde() !== null) ecrire(CLE_JETON, jeton)
}

// --- Session mémorisée (localStorage) ---

export function sauvegarderCompte(compteId) {
  compteActif = compteId
  try {
    localStorage.setItem(CLE, String(compteId))
    if (jetonActif) localStorage.setItem(CLE_JETON, jetonActif)
  } catch {
    // Pas grave : la prochaine ouverture retombera juste sur l'écran de
    // connexion, comme avant cette fonctionnalité.
  }
}

export function effacerCompteSauvegarde() {
  compteActif = null
  jetonActif = null
  try {
    localStorage.removeItem(CLE)
    localStorage.removeItem(CLE_JETON)
    localStorage.removeItem(CLE_ECOLE_CHOISIE)
    for (const cle of Object.keys(localStorage)) {
      if (cle.startsWith(PREFIXE_ECRAN)) localStorage.removeItem(cle)
    }
  } catch {
    // Idem.
  }
}

function lire(cle) {
  try {
    return localStorage.getItem(cle)
  } catch {
    return null
  }
}

// `valeur` null = effacer (ex. connexion d'un compte d'école après une
// session Superuser sur le même appareil : l'ancien jeton ne doit pas
// rester envoyé).
function ecrire(cle, valeur) {
  try {
    if (valeur == null) localStorage.removeItem(cle)
    else localStorage.setItem(cle, String(valeur))
  } catch {
    // Pas grave : il faudra juste se reconnecter.
  }
}


export function lireEcoleChoisie() {
  const valeur = lire(CLE_ECOLE_CHOISIE)
  return valeur ? Number(valeur) : null
}
export const sauvegarderEcoleChoisie = (ecoleId) => ecrire(CLE_ECOLE_CHOISIE, ecoleId)

// --- Dernier écran affiché ---
// `nom` : 'onglet' (barre du bas) ou 'admin' (sous-onglet d'Admin).

export function lireEcran(nom) {
  return lire(PREFIXE_ECRAN + nom)
}

export function sauvegarderEcran(nom, valeur) {
  ecrire(PREFIXE_ECRAN + nom, valeur)
}
