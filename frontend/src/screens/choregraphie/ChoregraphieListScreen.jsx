import Icon from '../../components/Icon.jsx'

// Écran 1/2 de Chorégraphie (voir spec/SPEC.md 5.3) : liste des
// chorégraphies du cours sélectionné. Cliquer en ouvre une en plein écran
// (voir ChoregraphieDetailScreen.jsx) — même principe que la Messagerie.
export default function ChoregraphieListScreen({ list, onSelect, onAddNew }) {
  return (
    <div className="screen">
      <div className="choregraphie-list choregraphie-list--full">
        {list.map((ch) => (
          <button
            key={ch.id}
            type="button"
            className="choregraphie-list__item"
            onClick={() => onSelect(ch.id)}
          >
            <span className="choregraphie-list__icon">
              <Icon name="music" size={18} />
            </span>
            <span>
              <strong>{ch.nom}</strong>
              <span className="muted"> {ch.eleveIds.length} élèves</span>
            </span>
            <Icon name="chevronRight" size={18} className="muted" />
          </button>
        ))}
        {list.length === 0 && (
          <p className="muted" style={{ padding: '12px 14px' }}>
            Aucune chorégraphie pour ce cours.
          </p>
        )}
        <button type="button" className="choregraphie-list__add" onClick={onAddNew}>
          <Icon name="plus" size={18} /> Nouvelle chorégraphie
        </button>
      </div>
    </div>
  )
}
