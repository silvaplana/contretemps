import { FamilyDot } from '../icons.jsx'
import { FAMILIES } from '../kinds.js'
import { FAMILY_TEXT } from './blocks.js'

// Les trois natures d'un fichier de l'appli, en cartes (création, et
// pastille de nature d'un fichier ouvert : fichier-de-base.md §1).
export default function FamilyCards({ value, onPick }) {
  return (
    <div className="af-cards">
      {Object.entries(FAMILIES).map(([cle, f]) => (
        <button key={cle} type="button" className={`af-card${value === cle ? ' af-card--on' : ''}`} style={{ '--c': f.color }} onClick={() => onPick(cle)}>
          <FamilyDot family={cle} size={34} />
          <span>
            <b>{f.label}</b>
            <small>{FAMILY_TEXT[cle].hint}</small>
            <em>{FAMILY_TEXT[cle].examples}</em>
          </span>
        </button>
      ))}
    </div>
  )
}
