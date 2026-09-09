// Suivi du statut de migration de chaque domaine vers api/<domaine>.js
// (voir api/README.md) — sert UNIQUEMENT à l'indicateur visuel "zone pas
// encore branchée" (voir components/ZoneMigration.jsx), activable par
// l'admin en mode dev (Admin > École). Mis à jour manuellement ici à
// chaque domaine migré — ce n'est qu'une checklist, pas une logique
// consultée par le reste de l'appli.
export const DOMAINES_MIGRES = {
  auth: true,
  ecoles: true,
  eleves: true,
  profs: true,
  cours: true,
  presence: true,
  choregraphies: true,
  videos: true,
  messagerie: false,
}

// Libellé + écran principal, pour l'écran "État des modules" (Admin >
// École) — voir AdminParametres.jsx.
export const INFOS_DOMAINES = {
  auth: { label: 'Connexion', ecran: 'Login' },
  ecoles: { label: 'École', ecran: 'Admin > École' },
  eleves: { label: 'Élèves', ecran: 'Admin > Élèves' },
  profs: { label: 'Professeurs', ecran: 'Admin > Professeurs' },
  cours: { label: 'Cours', ecran: 'Admin > Cours' },
  presence: { label: 'Présence', ecran: 'Présence + Comptage d’heures' },
  choregraphies: { label: 'Chorégraphies', ecran: 'Chorégraphie' },
  videos: { label: 'Vidéos', ecran: 'Vidéo' },
  messagerie: { label: 'Messagerie', ecran: 'Admin > Conversations + Messagerie' },
}

const CLE_STOCKAGE = 'contretemps_afficher_migration'

export function estAffichageMigrationActif() {
  try {
    return localStorage.getItem(CLE_STOCKAGE) === 'oui'
  } catch {
    return false
  }
}

export function definirAffichageMigration(actif) {
  try {
    localStorage.setItem(CLE_STOCKAGE, actif ? 'oui' : 'non')
  } catch {
    /* pas grave : juste un indicateur visuel de dev, pas bloquant */
  }
}
