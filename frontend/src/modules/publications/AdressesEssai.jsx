import { useState } from 'react'
import Icon from '../../components/Icon.jsx'

// Les adresses d'un essai par mail (§12.13), comme dans Gmail (Seb,
// 19 novembre) : chaque adresse devient une pastille, et en tapant quelques
// lettres la case propose les gens de l'école (administrateurs, profs, élèves).
const ADRESSE = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/
const simple = (texte) => texte.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const MAX_PROPOSITIONS = 6

const adresseValide = (texte) => ADRESSE.test(texte.trim())

export default function AdressesEssai({ adresses, saisie, gens, onChange }) {
  const [ouvert, setOuvert] = useState(false)
  const cherche = simple(saisie.trim())
  // Le prénom ou le nom qui commence par ces lettres d'abord, puis l'adresse.
  const rang = (g) => {
    const nom = simple(g.nom)
    if (nom.split(' ').some((mot) => mot.startsWith(cherche))) return 0
    return nom.includes(cherche) ? 1 : g.email.includes(cherche) ? 2 : 3
  }
  const propositions = cherche
    ? gens
        .filter((g) => !adresses.includes(g.email) && rang(g) < 3)
        .sort((x, y) => rang(x) - rang(y))
        .slice(0, MAX_PROPOSITIONS)
    : []

  const ajouter = (adresse) => {
    const propre = adresse.trim().toLowerCase()
    onChange({ adresses: adresses.includes(propre) ? adresses : [...adresses, propre], saisie: '' })
  }
  // « , », « ; », espace ou Entrée : l'adresse tapée devient une pastille.
  const taper = (texte) => {
    const morceaux = texte.split(/[,;\s]+/)
    const reste = morceaux.pop()
    const bonnes = morceaux.filter(adresseValide).map((a) => a.toLowerCase())
    const nouvelles = bonnes.filter((a) => !adresses.includes(a))
    const ignorees = morceaux.filter((a) => a && !adresseValide(a))
    onChange({ adresses: [...adresses, ...nouvelles], saisie: [...ignorees, reste].join(' ') })
    setOuvert(true)
  }
  const touche = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (adresseValide(saisie)) ajouter(saisie)
      else if (propositions.length === 1) ajouter(propositions[0].email)
    } else if (e.key === 'Backspace' && !saisie && adresses.length) {
      onChange({ adresses: adresses.slice(0, -1), saisie })
    }
  }

  return (
    <div className="adresses-essai">
      <div className="adresses-essai__case">
        {adresses.map((a) => (
          <span key={a} className="adresses-essai__pastille" title={a}>
            {gens.find((g) => g.email === a)?.nom ?? a}
            <button
              type="button"
              aria-label={`Retirer ${a}`}
              onClick={() => onChange({ adresses: adresses.filter((x) => x !== a), saisie })}
            >
              <Icon name="x" size={16} />
            </button>
          </span>
        ))}
        <input
          type="email"
          inputMode="email"
          autoComplete="off"
          aria-label="Adresse de l’essai"
          placeholder={adresses.length ? 'Une autre adresse' : 'Un nom ou une adresse'}
          value={saisie}
          onChange={(e) => taper(e.target.value)}
          onKeyDown={touche}
          onFocus={() => setOuvert(true)}
          // Le temps qu'un clic sur une proposition arrive.
          onBlur={() => setTimeout(() => {
            setOuvert(false)
            if (adresseValide(saisie)) ajouter(saisie)
          }, 150)}
        />
      </div>
      {ouvert && propositions.length > 0 && (
        <ul className="adresses-essai__propositions">
          {propositions.map((g) => (
            <li key={`${g.nom}-${g.email}`}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => ajouter(g.email)}>
                <b>{g.nom}</b>
                <span>{g.email}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
