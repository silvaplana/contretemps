// Normalisation partagée par toutes les barres de recherche de l'appli
// (Admin > Élèves/Profs/Cours/Groupes, Messagerie) — demande utilisateur
// du 2026-09-18 : insensible à la casse ET aux accents ("melanie" doit
// trouver "Mélanie"). Même principe que backend/src/comptes/comptes.py:
// _normaliser (login), pour un comportement cohérent partout — mais la
// technique diffère : pas d'encodage ascii ici, `\p{Diacritic}` (regex
// Unicode) est nativement supporté par tous les navigateurs ciblés.
export function normaliserRecherche(texte) {
  return texte
    .normalize('NFKD')
    .replace(/\p{Diacritic}/gu, '')
    .toLowerCase()
}

// Vrai si `texte` contient `requete`, insensible à la casse et aux
// accents — sucre pour le cas d'usage le plus courant (un `.filter` de
// liste), évite de renormaliser `requete` à chaque élément comparé côté
// appelant.
export function correspond(texte, requete) {
  return normaliserRecherche(texte).includes(normaliserRecherche(requete))
}
