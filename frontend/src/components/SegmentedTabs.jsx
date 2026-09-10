// Sélecteur segmenté horizontal (sous-onglets Admin, statuts...).
// `className` optionnel : voir AdminScreen.jsx, qui l'utilise pour rester
// fixe en haut au défilement (sans affecter l'autre usage de ".segmented",
// un filtre dans AdminGroupes.jsx, pas concerné).
export default function SegmentedTabs({ options, value, onChange, className = '' }) {
  return (
    <div className={`segmented ${className}`} role="tablist">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="tab"
          aria-selected={opt.value === value}
          className={`segmented__option ${opt.value === value ? 'is-active' : ''}`}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
