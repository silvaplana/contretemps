// Page publique d'inscription d'un élève (frontend-inscription/, voir
// spec/SPEC-inscription.md), servie à côté de l'appli sur le même domaine :
// silvaplana.cloud/contretemps-inscription/. Ouverte depuis le menu ⋮
// d'Admin > École et d'Admin > Élèves (demande utilisateur du 2026-09-25).
// Aucun paramètre : la page retrouve l'école toute seule.
// VITE_INSCRIPTION_URL permet de pointer ailleurs en développement.
const URL_INSCRIPTION = import.meta.env.VITE_INSCRIPTION_URL ?? '/contretemps-inscription/'

// Nouvel onglet : l'admin garde l'appli ouverte (et, dans l'appli
// installée, la page s'ouvre dans le navigateur).
export function ouvrirInscriptionEleve() {
  window.open(URL_INSCRIPTION, '_blank', 'noopener')
}
