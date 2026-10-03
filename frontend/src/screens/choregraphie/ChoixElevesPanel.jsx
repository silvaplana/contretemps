import { useMemo, useState } from 'react'
import Modal from '../../components/Modal.jsx'
import { correspond } from '../../utils/recherche.js'

// Panneau de choix des élèves d'une chorégraphie (spec §5.3, décision du
// 2026-10-03) : on choisit parmi TOUS les élèves de l'école, avec un filtre
// par cours pour s'y retrouver. Le filtre ne fait que restreindre la liste
// affichée : un élève coché le reste quand on change de cours.
export default function ChoixElevesPanel({ eleves, cours, coursInitial, choisis, onValider, onClose }) {
  const [selection, setSelection] = useState(() => new Set(choisis))
  // Ouvert sur le cours de la chorégraphie : ce sont le plus souvent ses élèves.
  const [coursId, setCoursId] = useState(coursInitial ?? '')
  const [recherche, setRecherche] = useState('')

  const affiches = useMemo(
    () =>
      eleves
        .filter((el) => !coursId || el.coursIds.includes(Number(coursId)))
        .filter((el) => !recherche || correspond(`${el.prenom} ${el.nom}`, recherche))
        .sort((a, b) => a.nom.localeCompare(b.nom, 'fr') || a.prenom.localeCompare(b.prenom, 'fr')),
    [eleves, coursId, recherche],
  )

  function basculer(id) {
    setSelection((s) => {
      const suivante = new Set(s)
      if (suivante.has(id)) suivante.delete(id)
      else suivante.add(id)
      return suivante
    })
  }

  const tousCoches = affiches.length > 0 && affiches.every((el) => selection.has(el.id))

  function basculerTous() {
    setSelection((s) => {
      const suivante = new Set(s)
      for (const el of affiches) {
        if (tousCoches) suivante.delete(el.id)
        else suivante.add(el.id)
      }
      return suivante
    })
  }

  return (
    <Modal
      title="Choisir des élèves"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary btn--block" onClick={() => onValider([...selection])}>
          Valider ({selection.size})
        </button>
      }
    >
      <div className="choix-eleves__filtres">
        <select aria-label="Filtrer par cours" value={coursId} onChange={(e) => setCoursId(e.target.value)}>
          <option value="">Tous les cours</option>
          {cours.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nom}
            </option>
          ))}
        </select>
        <input
          aria-label="Rechercher un élève"
          placeholder="Rechercher"
          value={recherche}
          onChange={(e) => setRecherche(e.target.value)}
        />
      </div>

      <div className="checkbox-list">
        {affiches.length > 1 && (
          <label className="checkbox-list__item choix-eleves__tous">
            <input type="checkbox" checked={tousCoches} onChange={basculerTous} />
            Tout cocher ({affiches.length})
          </label>
        )}
        {affiches.map((el) => (
          <label key={el.id} className="checkbox-list__item">
            <input type="checkbox" checked={selection.has(el.id)} onChange={() => basculer(el.id)} />
            {el.prenom} {el.nom}
          </label>
        ))}
        {affiches.length === 0 && <p className="muted">Aucun élève ne correspond.</p>}
      </div>
    </Modal>
  )
}
