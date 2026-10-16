import { Inline } from './Page.jsx'
import { BLOCKS, euros, formatValue, label, options, questions, resultBlocks } from './blocks.js'

// Le formulaire de résultat, rempli avec les réponses (fichier-de-base.md
// §2.4 et §6.1) : il relit les questions du formulaire d'entrée pour savoir
// comment s'appelle chaque colonne. Les réponses viennent de la base, jamais
// écrites à la main.

function Count({ rows, expected }) {
  const vraies = rows.filter((r) => !r.is_test).length
  const essais = rows.length - vraies
  return (
    <div className="ar-counters">
      <div className="ar-counter">
        <b>{expected ? `${vraies} / ${expected}` : vraies}</b>
        <span>{vraies > 1 ? 'ont répondu' : 'a répondu'}</span>
      </div>
      {essais > 0 && (
        <div className="ar-counter ar-counter--test">
          <b>{essais}</b>
          <span>{essais > 1 ? 'essais' : 'essai'}</span>
        </div>
      )}
    </div>
  )
}

function Chart({ question, rows }) {
  if (!question) return <p className="ar-missing">Ce graphique suivait une question qui n’existe plus.</p>
  const choix = question.type === 'yesNo' ? ['Oui', 'Non'] : options(question)
  const valeur = (r) => {
    const v = r.values?.[question.id]
    if (question.type === 'yesNo') return v === true ? ['Oui'] : v === false ? ['Non'] : []
    return Array.isArray(v) ? v : v != null ? [v] : []
  }
  const comptes = choix.map((c) => rows.filter((r) => valeur(r).includes(c)).length)
  const max = Math.max(1, ...comptes)
  return (
    <div className="ar-chart">
      <h4>{label(question)}</h4>
      {choix.map((c, i) => (
        <div key={c} className="ar-bar">
          <span>{c}</span>
          <b>{comptes[i]}</b>
          <div className="ar-track">
            <div className="ar-fill" style={{ width: `${(comptes[i] / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function Total({ question, rows }) {
  if (!question) return <p className="ar-missing">Ce total suivait une question qui n’existe plus.</p>
  const somme = rows.reduce((s, r) => {
    const v = r.values?.[question.id]
    if (v == null) return s
    return s + Number(question.type === 'payment' ? v.amount : v)
  }, 0)
  return (
    <div className="ar-counter ar-counter--wide">
      <b>{question.type === 'payment' ? euros(somme) : somme.toLocaleString('fr-FR')}</b>
      <span>{question.type === 'payment' ? `${label(question)} : total` : `Total : ${label(question)}`}</span>
    </div>
  )
}

function Table({ qs, rows }) {
  const colonnes = qs.filter((q) => q.type !== 'signature' || rows.some((r) => r.values?.[q.id]))
  return (
    <div className="ar-tablewrap">
      <table className="ar-table">
        <thead>
          <tr>
            <th>Qui</th>
            {colonnes.map((q) => (
              <th key={q.id}>{label(q)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={colonnes.length + 1} className="ar-none">Aucune réponse pour l’instant.</td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.id}>
              <td>
                {r.who}
                {r.is_test && <span className="ar-pill">Essai</span>}
                {r.example && <span className="ar-pill ar-pill--ex">Exemple</span>}
              </td>
              {colonnes.map((q) => (
                <td key={q.id}>{formatValue(q, r.values?.[q.id])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Réponses d'exemple pour l'Aperçu du formulaire de résultat, tant qu'il
// n'y en a pas de vraies (marquées « Exemple »).
export function exampleRows(content) {
  const noms = ['Camille Martin', 'Léa Bernard', 'Hugo Petit', 'Inès Moreau', 'Nathan Roux']
  const qs = questions(content)
  return noms.map((who, i) => ({
    id: `ex${i}`,
    who,
    example: true,
    values: Object.fromEntries(
      qs.map((q, j) => {
        const choix = options(q)
        const v = {
          choice: choix.length ? (q.props?.multiple ? [choix[(i + j) % choix.length]] : choix[(i * 2 + j) % choix.length]) : null,
          yesNo: i % 3 !== 0,
          number: 3 + i,
          date: `2026-11-${String(10 + i).padStart(2, '0')}`,
          payment: { amount: q.props?.amount ?? 0, test: false },
          member: { first_name: who.split(' ')[0], last_name: who.split(' ')[1], email: `${who.split(' ')[0].toLowerCase()}@exemple.fr` },
          shortText: 'Oui, avec plaisir',
          longText: 'Merci pour l’organisation !',
          signature: 'signé',
        }[q.type]
        return [q.id, v]
      }),
    ),
  }))
}

export default function Results({ content, rows, expected }) {
  const qs = questions(content)
  if (!qs.length) {
    return <p className="ar-missing">Ajoutez une question au formulaire d’entrée : le formulaire de résultat se fabriquera tout seul.</p>
  }
  const parId = Object.fromEntries(qs.map((q) => [q.id, q]))
  return (
    <div className="ar">
      {resultBlocks(content).map((b) => {
        let corps
        if (b.type === 'responseCount') corps = <Count rows={rows} expected={expected} />
        else if (b.type === 'choiceChart') corps = <Chart question={parId[b.props?.questionId]} rows={rows} />
        else if (b.type === 'total') corps = <Total question={parId[b.props?.questionId]} rows={rows} />
        else if (b.type === 'responseTable') corps = <Table qs={qs} rows={rows} />
        else if (b.type === 'heading') corps = <h3 className="ap-h"><Inline content={b.content} /></h3>
        else if (b.type === 'divider') corps = <hr className="ap-hr" />
        else corps = <p className="ap-p"><Inline content={b.content} /></p>
        return (
          <section key={b.id} className="ar-block" aria-label={BLOCKS[b.type]?.label}>
            {corps}
          </section>
        )
      })}
    </div>
  )
}
