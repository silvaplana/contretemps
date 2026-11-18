import { useState } from 'react'

// Champ À, Cc ou Cci (Seb, 18 novembre) : adresses séparées par des
// virgules ; dès 2 lettres tapées, les gens de l'école et les adresses déjà
// échangées qui correspondent s'affichent dessous ; un toucher ajoute
// l'adresse.

const MAX = 6
const sansAccent = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

function champ(c) {
  return c.name ? `"${c.name.replaceAll('"', '')}" <${c.address}>` : c.address
}

export default function ChampAdresses({ label, value, onChange, contacts, autoFocus = false }) {
  const [ouvert, setOuvert] = useState(false)
  const coupe = value.lastIndexOf(',')
  const debut = coupe >= 0 ? value.slice(0, coupe + 1) : ''
  const tape = sansAccent(value.slice(coupe + 1).trim())
  const deja = sansAccent(debut)
  const suggestions =
    tape.length >= 2
      ? contacts
          .filter((c) => sansAccent(`${c.name} ${c.address}`).includes(tape) && !deja.includes(c.address.toLowerCase()))
          .slice(0, MAX)
      : []

  function choisir(c) {
    onChange(`${debut ? `${debut.trim()} ` : ''}${champ(c)}, `)
    setOuvert(false)
  }

  return (
    <div className="mail__adresses">
      <label className="mail__champ-ligne">
        <span>{label}</span>
        <input
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
            setOuvert(true)
          }}
          onBlur={() => setTimeout(() => setOuvert(false), 200)}
          inputMode="email"
          autoCapitalize="none"
          autoComplete="off"
          autoFocus={autoFocus}
        />
      </label>
      {ouvert && suggestions.length > 0 && (
        <ul className="mail__suggestions" role="listbox" aria-label={`Suggestions pour ${label}`}>
          {suggestions.map((c) => (
            <li key={c.address}>
              <button type="button" role="option" aria-selected="false" onMouseDown={(e) => e.preventDefault()} onClick={() => choisir(c)}>
                <strong>{c.name || c.address}</strong>
                {c.name && <small>{c.address}</small>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
