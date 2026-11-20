// Plan comptable › « Proposer des comptes » (spec/modules/financier.md §8.2,
// Seb 20/11 ; maquette https://claude.ai/artifact/1i4V8WhNst2j8mQup5SvSH) :
// des sous-comptes d'après les transactions qui reviennent. On coche, on peut
// renommer ; rien n'est créé avant « Créer les comptes cochés ».
import { useEffect, useState } from 'react'
import * as api from '../api.js'
import './compta.css'

const { euros } = api

export default function ComptesProposes({ onClose, onCrees }) {
  const [propositions, setPropositions] = useState(null)
  const [coches, setCoches] = useState({})
  const [noms, setNoms] = useState({})
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api
      .comptesProposes()
      .then((d) => {
        setPropositions(d.proposals)
        setCoches(Object.fromEntries(d.proposals.map((p) => [p.number, true])))
      })
      .catch((err) => setErreur(err.message))
  }, [])

  if (erreur && !propositions) return <p className="login-screen__erreur">{erreur}</p>
  if (!propositions) return <p className="muted">Chargement…</p>

  const choisis = propositions.filter((p) => coches[p.number])

  async function creer() {
    setEnCours(true)
    setErreur('')
    try {
      const items = choisis.map((p) => ({ parentId: p.parentId, key: p.key, label: noms[p.number] ?? p.label }))
      onCrees(await api.creerComptesProposes(items))
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <section className="fin-cp" aria-label="Comptes proposés">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Plan comptable
      </button>
      <h3>Comptes proposés</h3>
      {propositions.length === 0 ? (
        <p className="muted">Rien à proposer pour l’instant : aucun nom ne revient au moins trois fois dans un même compte sur les douze derniers mois.</p>
      ) : (
        <>
          <p className="muted">
            D’après les transactions des douze derniers mois, ces comptes rendraient la Balance plus claire. Cochez ceux à garder ; vous pouvez changer leur nom. Rien
            n’est créé avant de valider.
          </p>
          {propositions.map((p) => (
            <div key={p.number} className={`fin-cp-carte fin-proposes__carte${coches[p.number] ? ' is-active' : ''}`}>
              <label className="fin-proposes__coche">
                <input type="checkbox" checked={!!coches[p.number]} onChange={(e) => setCoches((c) => ({ ...c, [p.number]: e.target.checked }))} />
                <span className="fin-cp-t">{p.number}</span>
                <span className="fin-cp-s">sous {p.parent}</span>
              </label>
              <label className="fin-cp-champ">
                <span>Nom du compte</span>
                <input
                  type="text"
                  className="field-input"
                  maxLength={80}
                  value={noms[p.number] ?? p.label}
                  onChange={(e) => setNoms((n) => ({ ...n, [p.number]: e.target.value }))}
                />
              </label>
              <span>
                {p.count} transactions « {p.key} »{p.sameAmount != null && `, toutes de ${euros(p.sameAmount)}`}.
              </span>
              <span className="fin-cp-s">
                Ces {p.count} transactions passent de {p.parentNumber} à {p.number} ; mot-clé : {p.key}.
              </span>
            </div>
          ))}
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
          <div className="fin-cp-boutons">
            <button type="button" className="btn btn--primary" onClick={creer} disabled={enCours || choisis.length === 0}>
              {choisis.length === 0 ? 'Aucun compte coché' : `Créer les comptes cochés (${choisis.length})`}
            </button>
            <button type="button" className="btn btn--secondary" onClick={onClose}>
              Annuler
            </button>
          </div>
        </>
      )}
    </section>
  )
}
