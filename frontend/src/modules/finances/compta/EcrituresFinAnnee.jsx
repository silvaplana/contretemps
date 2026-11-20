// Bilan › Préparer, étape 4 › Écritures de fin d'année (spec/modules/financier.md
// §8.14, Seb 20/11 ; Engagement). L'appli propose ce qui ne tombe pas sur la
// bonne saison ; le choix conseillé est déjà fait sur chaque ligne, avec sa
// raison. Les touches nomment la saison. Rien n'est écrit avant « Valider mes choix ».
import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'

const { euros, dateFr } = api

function touches(item, data, annees) {
  if (item.kind === 'depreciation') return [`Étaler sur ${annees} ans`, `Tout en ${data.season}`]
  if (item.kind === 'invoice_due') return [`Compter en ${data.season}`, `Laisser en ${data.next}`]
  return [`Compter en ${data.next}`, `Laisser en ${data.season}`]
}

export default function EcrituresFinAnnee({ season, onChange, onErreur }) {
  const [data, setData] = useState(null)
  const [choix, setChoix] = useState({}) // clé → { keep, years }
  const [ouvertes, setOuvertes] = useState({})
  const [envoi, setEnvoi] = useState(false)

  const recevoir = useCallback((d) => {
    setData(d)
    setChoix(Object.fromEntries(d.items.map((i) => [i.key, { keep: i.keep, years: i.years }])))
  }, [])

  useEffect(() => {
    api
      .ecrituresFinAnnee(season.id)
      .then(recevoir)
      .catch((err) => onErreur(err.message))
  }, [season.id, recevoir, onErreur])

  async function envoyer(action) {
    setEnvoi(true)
    try {
      recevoir(await action())
      onChange()
    } catch (err) {
      onErreur(err.message)
    } finally {
      setEnvoi(false)
    }
  }

  if (!data) return null
  const fige = data.validated || data.closed
  const detail = (i) => (i.kind === 'depreciation' ? i.byYears[choix[i.key]?.years ?? 5] : i)
  const effet = data.items.reduce((s, i) => s + (choix[i.key]?.keep ? detail(i).effect : 0), 0)
  const gardees = data.items.filter((i) => choix[i.key]?.keep).length
  const regler = (key, valeur) => setChoix((c) => ({ ...c, [key]: { ...c[key], ...valeur } }))

  return (
    <div className="fin-preparer__bloc fin-finannee">
      <span className="fin-cp-t">Écritures de fin d’année {data.season}</span>
      {data.items.length === 0 ? (
        <span className="fin-cp-s">Rien à proposer : l’appli n’a rien repéré qui tombe sur la mauvaise saison.</span>
      ) : (
        <span className="fin-cp-s">
          La saison se termine le {dateFr(data.endDate)}. L’appli a repéré ce qui ne tombe pas sur la bonne saison. Le choix conseillé est déjà fait sur
          chaque ligne : gardez-le ou changez-le.
        </span>
      )}
      {data.items.map((i) => {
        const c = choix[i.key] ?? {}
        const d = detail(i)
        const [oui, non] = touches(i, data, c.years ?? 5)
        return (
          <div key={i.key} className="fin-finannee__ligne">
            <span className="fin-finannee__tete">
              <span className="fin-cp-t">{i.title}</span>
              <span className="fin-preparer__montant">{euros(d.amount)}</span>
            </span>
            <span>{i.text}</span>
            {i.kind === 'depreciation' && (
              <>
                <span className="fin-finannee__choix fin-finannee__choix--3">
                  {[3, 5, 10].map((a) => (
                    <button key={a} type="button" className="btn btn--secondary" aria-pressed={c.years === a} disabled={fige} onClick={() => regler(i.key, { years: a })}>
                      {a} ans
                    </button>
                  ))}
                </span>
                <span className="fin-cp-s">{d.note}</span>
              </>
            )}
            <span className="fin-finannee__conseil">
              Conseillé : {i.advised ? oui : non}. {i.reason}
            </span>
            <span className="fin-finannee__choix">
              <button type="button" className="btn btn--secondary" aria-pressed={!!c.keep} disabled={fige} onClick={() => regler(i.key, { keep: true })}>
                {oui}
              </button>
              <button type="button" className="btn btn--secondary" aria-pressed={!c.keep} disabled={fige} onClick={() => regler(i.key, { keep: false })}>
                {non}
              </button>
            </span>
            <button type="button" className="btn btn--link" onClick={() => setOuvertes((o) => ({ ...o, [i.key]: !o[i.key] }))}>
              {ouvertes[i.key] ? 'Cacher l’écriture' : 'Voir l’écriture'}
            </button>
            {ouvertes[i.key] && (
              <div className="fin-finannee__ecriture">
                <table>
                  <thead>
                    <tr>
                      <th>Au {dateFr(data.endDate)}</th>
                      <th>Débit</th>
                      <th>Crédit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.lines.map((l, n) => (
                      <tr key={n}>
                        <td>{l.account}</td>
                        <td>{l.debit ? euros(l.debit) : ''}</td>
                        <td>{l.credit ? euros(l.credit) : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
      {data.items.length > 0 && (
        <>
          <div className="fin-finannee__resultat">
            <span>
              <span>Résultat avant ces écritures</span>
              <span>{euros(data.resultBefore)}</span>
            </span>
            <span>
              <span>Effet de vos choix</span>
              <span>{effet > 0 ? '+ ' : effet < 0 ? '− ' : ''}{euros(Math.abs(effet))}</span>
            </span>
            <span className="fin-finannee__final">
              <span>Résultat de la saison</span>
              <span>{euros(data.resultBefore + effet)}</span>
            </span>
          </div>
          {data.validated ? (
            <>
              <span className="fin-finannee__fait">
                Choix validés : {gardees === 0 ? 'aucune écriture.' : `${gardees} écriture${gardees > 1 ? 's' : ''} enregistrée${gardees > 1 ? 's' : ''} au ${dateFr(data.endDate)}.`}
              </span>
              <span className="fin-cp-s">
                Les charges et produits d’avance repartent tout seuls sur {data.next} à sa première journée, une fois {data.season} clôturée.
              </span>
              {!data.closed && (
                <button type="button" className="btn btn--secondary" disabled={envoi} onClick={() => envoyer(() => api.annulerEcrituresFinAnnee(season.id))}>
                  Annuler
                </button>
              )}
            </>
          ) : (
            !data.closed && (
              <button
                type="button"
                className="btn btn--primary"
                disabled={envoi}
                onClick={() => envoyer(() => api.validerEcrituresFinAnnee(season.id, data.items.map((i) => ({ key: i.key, ...choix[i.key] }))))}
              >
                Valider mes choix
              </button>
            )
          )}
        </>
      )}
    </div>
  )
}
