import { TABS } from '../data/nav.js'
import Icon from './Icon.jsx'

// Barre de navigation basse fixe (voir spec/SPEC.md §3 et §4) : les onglets
// visibles dépendent du rôle du profil actif (Admin est réservé à l'Admin,
// Présence à l'Admin/Professeur — voir data/nav.js).
//
// `alertes` : { [tabKey]: nombre } — badge numéroté sur l'icône de cet
// onglet (pour l'instant, seule la messagerie l'utilise : total des
// messages non lus toutes conversations confondues, voir App.jsx :
// compterNonLus). Objet plutôt qu'un simple nombre "messagerie" pour
// rester générique si un jour un autre onglet en a besoin.
export default function BottomNav({ active, onChange, role, alertes = {} }) {
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
          <span className="bottom-nav__icon">
            <Icon name={tab.icon} size={20} />
            {alertes[tab.key] > 0 && <span className="bottom-nav__badge">{alertes[tab.key]}</span>}
          </span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
