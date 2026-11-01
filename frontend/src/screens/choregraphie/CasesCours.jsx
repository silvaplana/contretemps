// Les cours d'une chorégraphie, à cocher : une chorégraphie peut être
// dansée par plusieurs cours (Seb, 1er novembre). Il en reste toujours au
// moins un coché. `modifiable(c)` : faux pour un cours qu'on ne gère pas
// (sa case reste visible mais grisée).
export default function CasesCours({ cours, coches, onChange, modifiable = () => true }) {
  function basculer(id) {
    if (coches.includes(id)) {
      if (coches.length > 1) onChange(coches.filter((x) => x !== id))
    } else {
      onChange([...coches, id])
    }
  }

  return (
    <div className="checkbox-list">
      {cours.map((c) => {
        const coche = coches.includes(c.id)
        return (
          <label key={c.id} className="checkbox-list__item">
            <input
              type="checkbox"
              checked={coche}
              disabled={!modifiable(c) || (coche && coches.length === 1)}
              onChange={() => basculer(c.id)}
            />
            {c.nom}
          </label>
        )
      })}
    </div>
  )
}
