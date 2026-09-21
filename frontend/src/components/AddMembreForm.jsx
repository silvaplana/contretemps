import { useState } from 'react'

// Formulaire "Ajouter un membre" (type admin/professeur/élève/cours +
// sélection) — partagé par Admin > Messagerie (AdminGroupes.jsx, ajout
// immédiat) et "Nouveau groupe" depuis Messagerie (NouveauGroupeModal.jsx,
// ajout en local le temps de la modale) : même UI, seul ce que fait
// `onAdd` diffère entre les deux appelants.
export default function AddMembreForm({ admins, professeurs, eleves, cours, onAdd }) {
  const [type, setType] = useState('cours')
  const [id, setId] = useState(cours[0]?.id ?? '')

  const OPTIONS_PAR_TYPE = { admin: admins, professeur: professeurs, eleve: eleves, cours }
  const options = OPTIONS_PAR_TYPE[type]

  return (
    <div className="add-membre-form">
      <p className="add-membre-form__title">Ajouter un membre</p>
      <div className="segmented segmented--sm">
        {['admin', 'professeur', 'eleve', 'cours'].map((t) => (
          <button
            key={t}
            type="button"
            className={`segmented__option ${type === t ? 'is-active' : ''}`}
            onClick={() => {
              setType(t)
              setId(OPTIONS_PAR_TYPE[t][0]?.id ?? '')
            }}
          >
            {t === 'admin' ? 'Admin' : t === 'professeur' ? 'Prof' : t === 'eleve' ? 'Élève' : 'Cours'}
          </button>
        ))}
      </div>

      <div className="add-membre-form__row">
        <select
          value={id}
          onChange={(e) => {
            // <select> ne renvoie que des chaînes (e.target.value), même
            // pour un id numérique (réel) — sans ce repli, comparer cet id
            // à option.id avec `===` échoue toujours (voir libelleMembre),
            // d'où le "?" affiché après avoir vraiment changé la sélection
            // (pas remarqué avant : le 1er item reste un vrai number tant
            // qu'on n'a pas touché le <select>, voir useState ci-dessus).
            const choisi = options.find((o) => String(o.id) === e.target.value)
            setId(choisi ? choisi.id : e.target.value)
          }}
        >
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {type === 'cours' ? o.nom : `${o.prenom} ${o.nom}`}
            </option>
          ))}
          {options.length === 0 && <option value="">Aucun</option>}
        </select>
        <button type="button" className="btn btn--secondary" disabled={!id} onClick={() => onAdd({ type, id })}>
          Ajouter
        </button>
      </div>
    </div>
  )
}
