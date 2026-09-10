// Persistance de "qui est connecté" (voir spec/SPEC.md §2.2 : session
// persistante web/mobile, sans reconnexion systématique) — juste l'id du
// PROFIL ACTIF, pas un identifiant/code : ce backend n'a aucune notion de
// session/token (voir backend/src/auth/receiver.py) — cohérent avec le
// reste de l'appli, où par exemple GET /comptes/{id} ne vérifie déjà rien
// (voir api/auth.js : basculerLibre). localStorage : survit à la
// fermeture de l'onglet/l'appli (web, PWA installée, Android, iOS —
// même mécanisme partout, c'est la même appli web dans les 4 cas), mais
// reste propre à CET appareil/navigateur, jamais partagé.
const CLE = 'contretemps:compteId'

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

export function sauvegarderCompte(compteId) {
  try {
    localStorage.setItem(CLE, String(compteId))
  } catch {
    // Pas grave : la prochaine ouverture retombera juste sur l'écran de
    // connexion, comme avant cette fonctionnalité.
  }
}

export function effacerCompteSauvegarde() {
  try {
    localStorage.removeItem(CLE)
  } catch {
    // Idem.
  }
}
