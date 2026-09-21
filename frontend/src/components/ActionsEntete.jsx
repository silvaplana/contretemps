import { useState } from 'react'
import { createPortal } from 'react-dom'

// Emplacement, dans l'en-tête, À DROITE du badge de l'utilisateur, pour une
// action propre à l'écran affiché (ex. le menu ⋮ d'Admin > École, demande du
// 2026-09-21). L'en-tête rend l'emplacement vide ; l'écran y place son
// contenu avec <ActionsEntete>, sans que l'en-tête ait à le connaître.
export const ID_ACTIONS_ENTETE = 'actions-entete'

export default function ActionsEntete({ children }) {
  // L'en-tête est déjà monté quand un écran qui s'en sert apparaît (ex.
  // Admin > École n'est jamais le sous-onglet ouvert d'office) : on cherche
  // l'emplacement une fois, au premier rendu.
  const [cible] = useState(() => document.getElementById(ID_ACTIONS_ENTETE))
  return cible ? createPortal(children, cible) : null
}
