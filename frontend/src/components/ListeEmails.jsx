import { useState } from 'react'
import Icon from './Icon.jsx'

// Emails d'une fiche (spec §2.1 « Plusieurs emails par fiche », 2026-10-16) :
// une adresse par ligne, « + Ajouter un email », une croix pour en retirer
// une. Tous équivalents, l'ordre n'a pas d'importance. `valeur` et
// `onChange` parlent la forme du serveur : « a@x.fr, b@x.fr ».
function separerEmails(texte) {
  return (texte ?? '')
    .split(/[;,\s]+/)
    .map((e) => e.trim())
    .filter(Boolean)
}

export default function ListeEmails({ id, valeur, onChange }) {
  const [lignes, setLignes] = useState(() => {
    const emails = separerEmails(valeur)
    return emails.length ? emails : ['']
  })

  function changer(suivantes) {
    setLignes(suivantes)
    onChange(suivantes.map((e) => e.trim()).filter(Boolean).join(', '))
  }

  return (
    <div className="liste-emails">
      {lignes.map((email, i) => (
        <div key={i} className="liste-emails__ligne">
          <input
            id={i === 0 ? id : undefined}
            className="field-input"
            type="email"
            value={email}
            placeholder={i === 0 ? 'Email' : 'Autre email'}
            onChange={(e) => changer(lignes.map((x, j) => (j === i ? e.target.value : x)))}
          />
          {(lignes.length > 1 || email) && (
            <button
              type="button"
              className="icon-btn"
              onClick={() => changer(lignes.length > 1 ? lignes.filter((_, j) => j !== i) : [''])}
              aria-label={`Retirer ${email || 'cet email'}`}
            >
              <Icon name="x" size={16} />
            </button>
          )}
        </div>
      ))}
      <button type="button" className="btn btn--secondary liste-emails__ajouter" onClick={() => setLignes([...lignes, ''])}>
        <Icon name="plus" size={16} /> Ajouter un email
      </button>
    </div>
  )
}
