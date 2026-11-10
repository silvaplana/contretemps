import { useEffect, useRef, useState } from 'react'
import Icon from './Icon.jsx'

// Modale plein écran simple (formulaires d'ajout, commentaire, sélection de
// cours...). Pas de librairie : juste un overlay + un panneau.
// Le bas du panneau (bouton principal) reste toujours visible ; tant qu'il
// reste quelque chose plus bas, une bande « ↓ Suite plus bas » le dit (Seb, 10/11).
export default function Modal({ title, onClose, children, footer }) {
  const panneau = useRef(null)
  const [suite, setSuite] = useState(false)

  function mesurer() {
    const p = panneau.current
    if (p) setSuite(p.scrollHeight - p.scrollTop - p.clientHeight > 8)
  }

  useEffect(() => {
    const p = panneau.current
    mesurer()
    const ro = new ResizeObserver(mesurer)
    ro.observe(p)
    for (const enfant of p.children) ro.observe(enfant)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" ref={panneau} onScroll={mesurer} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            aria-label="Fermer"
          >
            <Icon name="x" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {(footer || suite) && (
          <div className="modal-bas">
            {suite && (
              <button
                type="button"
                className="modal-suite"
                onClick={() => panneau.current.scrollBy({ top: panneau.current.clientHeight * 0.7, behavior: 'smooth' })}
              >
                ↓ Suite plus bas
              </button>
            )}
            {footer && <div className="modal-footer">{footer}</div>}
          </div>
        )}
      </div>
    </div>
  )
}
