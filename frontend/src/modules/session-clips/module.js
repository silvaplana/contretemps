// Déclaration du module Sparring (spec/core.md §9 bis,
// spec/modules/video-combats.md §6) : tout le monde voit « Mes combats » ;
// les coachs ont aussi Séances et À vérifier.
export default {
  key: 'session_clips',
  tabs: [{ key: 'sparring', label: 'Sparring', icon: 'video', roles: ['admin', 'professeur', 'eleve'] }],
}
