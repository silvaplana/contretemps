import { useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'

// Emplacement, dans l'en-tête, À DROITE du badge de l'utilisateur, pour une
// action propre à l'écran affiché (ex. le menu ⋮ d'Admin > École, demande du
// 2026-09-21). L'en-tête rend l'emplacement vide ; l'écran y place son
// contenu avec <ActionsEntete>, sans que l'en-tête ait à le connaître.
export const ID_ACTIONS_ENTETE = 'actions-entete'

// L'emplacement est cherché APRÈS l'affichage : quand l'appli s'ouvre
// directement sur l'écran (dernier onglet retenu, page rechargée, retour de
// la banque), l'en-tête et l'écran se dessinent ensemble et l'emplacement
// n'existe pas encore pendant le rendu (le menu ⋯ du Financier manquait
// alors, Seb 28 octobre).
function useEmplacement(id) {
  const [cible, setCible] = useState(() => document.getElementById(id))
  useLayoutEffect(() => {
    if (!cible) setCible(document.getElementById(id))
  }, [cible, id])
  return cible
}

export default function ActionsEntete({ children }) {
  const cible = useEmplacement(ID_ACTIONS_ENTETE)
  return cible ? createPortal(children, cible) : null
}

// Emplacement, à GAUCHE de l'en-tête, pour le titre d'un écran ouvert par
// dessus (ex. un fichier de Docs : ← nom, état ; Seb, 21 octobre). Tant
// qu'il est rempli, il remplace le logo et le titre de l'onglet.
export const ID_TITRE_ENTETE = 'titre-entete'

export function TitreEntete({ children }) {
  const cible = useEmplacement(ID_TITRE_ENTETE)
  return cible ? createPortal(children, cible) : null
}
