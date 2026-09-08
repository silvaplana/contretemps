// Onglet Admin > École (voir spec/SPEC.md §5.1.1 et §6.1) : nom de l'école
// et ses 3 codes d'accès, modifiables par tout admin (pas seulement le
// créateur de l'école). Premier sous-onglet, le plus à gauche.
export default function AdminParametres({ ecole, setEcole }) {
  function update(patch) {
    setEcole((e) => ({ ...e, ...patch }))
  }

  return (
    <div className="admin-panel">
      <div className="form-fields">
        <label htmlFor="ecole-param-nom">Nom de l’école</label>
        <input
          id="ecole-param-nom"
          className="field-input"
          value={ecole.nom}
          onChange={(e) => update({ nom: e.target.value })}
        />

        <label htmlFor="ecole-param-admin">Code d’accès Admin</label>
        <input
          id="ecole-param-admin"
          className="field-input"
          value={ecole.codeAccesAdmin}
          onChange={(e) => update({ codeAccesAdmin: e.target.value })}
        />

        <label htmlFor="ecole-param-prof">Code d’accès Professeur</label>
        <input
          id="ecole-param-prof"
          className="field-input"
          value={ecole.codeAccesProf}
          onChange={(e) => update({ codeAccesProf: e.target.value })}
        />

        <label htmlFor="ecole-param-eleve">Code d’accès Élève</label>
        <input
          id="ecole-param-eleve"
          className="field-input"
          value={ecole.codeAccesEleve}
          onChange={(e) => update({ codeAccesEleve: e.target.value })}
        />
      </div>
    </div>
  )
}
