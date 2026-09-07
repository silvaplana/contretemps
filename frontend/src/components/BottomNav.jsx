import { TABS } from '../data/nav.js'
import Icon from './Icon.jsx'

// Barre de navigation basse fixe (voir spec/SPEC.md §3 et §4) : les onglets
// visibles dépendent du rôle du profil actif (Admin est réservé à l'Admin,
// Présence à l'Admin/Professeur — voir data/nav.js).
export default function BottomNav({ active, onChange, role }) {
  const visibles = TABS.filter((tab) => tab.roles.includes(role))
  return (
    <nav className="bottom-nav">
      {visibles.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`bottom-nav__item ${active === tab.key ? 'is-active' : ''}`}
          onClick={() => onChange(tab.key)}
        >
          <Icon name={tab.icon} size={20} />
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
