import { useEffect, useState } from 'react'

// « Pour qui ? » après un dépôt dans le bac Échanges (spec documents.md
// §4.7 ter) : Tout le monde (le choix par défaut, il suffit de fermer), ou
// une personne ou un groupe, qui seuls le verront avec qui l'a déposé.

function Avatar({ p }) {
  if (p.type === 'group') return <div className="dx-av">👥</div>
  return <div className="dx-av">{(p.label ?? '?').slice(0, 1).toUpperCase()}</div>
}

export default function PourQui({ api, items, onClose, onDone, onError }) {
  const [recherche, setRecherche] = useState('')
  const [suggestions, setSuggestions] = useState([])

  useEffect(() => {
    let annule = false
    const t = setTimeout(() => {
      api.principals(recherche).then((liste) => !annule && setSuggestions(liste), () => {})
    }, 200)
    return () => {
      annule = true
      clearTimeout(t)
    }
  }, [api, recherche])

  async function choisir(p) {
    try {
      for (const item of items) await api.setRecipient(item.id, p)
      onDone(p ? `Pour ${p.label} : seuls vous et ${p.type === 'group' ? 'ce groupe' : 'cette personne'} le voyez` : 'Pour tout le monde')
    } catch (e) {
      onError(e)
    }
  }

  const nom = items.length > 1 ? `${items.length} éléments` : `« ${items[0].name} »`
  return (
    <div className="dx-panel" role="dialog" aria-label="Pour qui ?">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer">✕</button>
        <h2>Pour qui ?</h2>
      </div>
      <div className="dx-body">
        <div className="dx-muted dx-share__name">{nom} dans Échanges</div>
        <button type="button" className="dx-opt dx-opt--on" onClick={() => choisir(null)}>
          <span className="dx-opt__rad" />
          <span>
            <span className="dx-opt__t">Tout le monde</span>
            <span className="dx-opt__d">Tous ceux qui ont accès au bac. Il part à la corbeille dans 30 jours.</span>
          </span>
        </button>
        <div className="dx-sec">Ou seulement pour</div>
        <div className="dx-sugg">
          <input
            className="dx-input"
            placeholder="Nom, cours…"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
          <div className="dx-sugg__list">
            {suggestions
              .filter((p) => p.id !== 'role:admin')
              .map((p) => (
                <button key={`${p.type}:${p.id}`} type="button" onClick={() => choisir(p)}>
                  <Avatar p={p} />
                  <span className="dx-meta">
                    <span className="dx-n">{p.label}</span>
                    <span className="dx-s">{p.detail}</span>
                  </span>
                </button>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
