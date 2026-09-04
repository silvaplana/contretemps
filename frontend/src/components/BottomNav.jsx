import Icon from './Icon.jsx'

// Barre de navigation basse fixe (voir spec/SPEC.md 4). Rôle Admin : les 6
// onglets sont visibles (Admin est réservé à ce rôle, voir 5.1).
const TABS = [
  { key: 'admin', label: 'Admin', icon: 'admin' },
  { key: 'presence', label: 'Présence', icon: 'presence' },
  { key: 'choregraphie', label: 'Chorégraphie', icon: 'choregraphie' },
  { key: 'video', label: 'Vidéo', icon: 'video' },
  { key: 'messagerie', label: 'Messagerie', icon: 'messagerie' },
  { key: 'profil', label: 'Profil', icon: 'profil' },
]

export default function BottomNav({ active, onChange }) {
  return (
    <nav className="bottom-nav">
      {TABS.map((tab) => (
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
