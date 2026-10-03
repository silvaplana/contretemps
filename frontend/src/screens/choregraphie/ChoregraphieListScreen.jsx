import Icon from '../../components/Icon.jsx'

// Écran 1/2 de Chorégraphie (voir spec/SPEC.md §5.3) : les chorégraphies
// de l'école retenues par le sélecteur discipline / niveau (voir
// ChoregraphieScreen.jsx). Cliquer en ouvre une en plein écran (voir
// ChoregraphieDetailScreen.jsx) — même principe que la Messagerie.
export default function ChoregraphieListScreen({ filtres, list, coursParId, onSelect, onAddNew, peutCreer }) {
  return (
    <div className="screen">
      {filtres}
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
              <span className="muted">
                {' '}
                {coursParId.get(ch.coursId)?.nom ?? ''} · {ch.eleveIds.length} élève
                {ch.eleveIds.length > 1 ? 's' : ''} · {ch.videos.length} vidéo
                {ch.videos.length > 1 ? 's' : ''}
              </span>
            </span>
            <Icon name="chevronRight" size={18} className="muted" />
          </button>
        ))}
        {list.length === 0 && (
          <p className="muted" style={{ padding: '12px 14px' }}>
            Aucune chorégraphie.
          </p>
        )}
      </div>

      {peutCreer && (
        <button type="button" className="fab" onClick={onAddNew} aria-label="Nouvelle chorégraphie">
          <Icon name="plus" size={24} />
        </button>
      )}
    </div>
  )
}
