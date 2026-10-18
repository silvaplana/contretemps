import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { normaliserRecherche } from '../../utils/recherche.js'
import { trierParNom } from './personnes.js'

const TITRES = {
  admin: 'Choisir des admins',
  professeur: 'Choisir des profs',
  eleve: 'Choisir des élèves',
  cours: 'Choisir des cours',
}

function nomDe(type, o) {
  return type === 'cours' ? o.nom : `${o.prenom} ${o.nom}`
}

// Choix de plusieurs admins, profs, élèves ou cours d'un coup, par-dessus
// la fenêtre « Nouveau groupe » (spec/modules/messagerie-instantanee.md
// §3.5) : une case par ligne, « Tout sélectionner » en haut, « Valider »
// toujours visible en bas. Ceux déjà dans le groupe arrivent cochés ; les
// décocher les retire. `onValider(ids)` reçoit la sélection complète.
export default function ChoixMembresScreen({ type, options, dejaChoisis, onValider, onBack }) {
  const [choisis, setChoisis] = useState(() => new Set(dejaChoisis))
  const [recherche, setRecherche] = useState('')

  const triees = trierParNom(options, (o) => nomDe(type, o))
  const requete = normaliserRecherche(recherche.trim())
  const visibles = requete ? triees.filter((o) => normaliserRecherche(nomDe(type, o)).includes(requete)) : triees
  const toutCoche = options.length > 0 && options.every((o) => choisis.has(o.id))

  function basculer(id) {
    setChoisis((s) => {
      const copie = new Set(s)
      if (copie.has(id)) copie.delete(id)
      else copie.add(id)
      return copie
    })
  }

  return (
    <div className="ecran-dessus">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour au groupe">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className="thread-screen__header-text">
          <strong>{TITRES[type]}</strong>
          <span className="muted">{choisis.size} sélectionné{choisis.size > 1 ? 's' : ''}</span>
        </span>
      </div>

      <div className="ecran-dessus__liste">
        <label className="choix-membres__ligne choix-membres__tout">
          <input
            type="checkbox"
            checked={toutCoche}
            disabled={options.length === 0}
            onChange={() => setChoisis(toutCoche ? new Set() : new Set(options.map((o) => o.id)))}
          />
          <span>Tout sélectionner</span>
        </label>

        <div className="search-bar choix-membres__recherche">
          <Icon name="search" size={18} />
          <input value={recherche} onChange={(e) => setRecherche(e.target.value)} placeholder="Rechercher" />
        </div>

        {visibles.map((o) => (
          <label key={o.id} className="choix-membres__ligne">
            <input type="checkbox" checked={choisis.has(o.id)} onChange={() => basculer(o.id)} />
            <span>{nomDe(type, o)}</span>
          </label>
        ))}
        {visibles.length === 0 && <p className="muted">Aucun résultat.</p>}
      </div>

      <div className="ecran-dessus__pied">
        <button type="button" className="btn btn--primary btn--block" onClick={() => onValider([...choisis])}>
          Valider ({choisis.size})
        </button>
      </div>
    </div>
  )
}
