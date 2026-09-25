import { useRef, useState } from 'react'
import { useFermerAuClicExterieur } from '../hooks/useFermerAuClicExterieur.js'
import ActionsEntete from './ActionsEntete.jsx'
import Icon from './Icon.jsx'

// Menu ⋮ d'un écran, placé dans l'en-tête à droite du badge (voir
// ActionsEntete.jsx) — même présentation que celui d'Admin > École
// (SauvegardeEcoleMenu.jsx). `actions` : [{ label, icon, onClick }].
export default function MenuEntete({ label, actions }) {
  const [ouvert, setOuvert] = useState(false)
  const menuRef = useRef(null)
  useFermerAuClicExterieur(menuRef, ouvert, () => setOuvert(false))

  return (
    <ActionsEntete>
      <div className="header-menu" ref={menuRef}>
        <button type="button" className="icon-btn" onClick={() => setOuvert((o) => !o)} aria-label={label}>
          <Icon name="moreVertical" />
        </button>
        {ouvert && (
          <div className="dropdown-menu header-menu__panel">
            {actions.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => {
                  setOuvert(false)
                  action.onClick()
                }}
              >
                <Icon name={action.icon} size={18} /> {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </ActionsEntete>
  )
}
