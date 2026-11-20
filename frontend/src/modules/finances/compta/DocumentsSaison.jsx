// Bilan › Préparer, étapes 6 et 7 (spec/modules/financier.md §8.10, Seb 10/11) :
// les documents de la saison d'après ceux du Bilan financier de l'an dernier
// (reconnus par l'appli, cochés et corrigés par la trésorière, nommés comme
// l'an dernier), à voir ou télécharger : rien n'est rangé dans Docs. Puis la
// clôture de la saison, sans passer par un « bilan ».
import { useCallback, useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import { telechargerFichier } from '../../../utils/telechargement.js'
import { RapportFinancier } from './DocumentsAG.jsx'
import Apercu from './Apercu.jsx'
import BudgetPrevisionnel from './BudgetPrevisionnel.jsx'
import RapportCorrection from './RapportCorrection.jsx'
import * as api from '../api.js'
import './compta.css'

const { euros, dateFr } = api
const AUTRE = 'autre'
const RAPPORT = 'rapport'

// « Voir » un PDF : l'onglet s'ouvre pendant le toucher (sinon le navigateur
// le bloque), le fichier y arrive ensuite.
async function voirPdf(url) {
  const onglet = window.open('', '_blank')
  try {
    const reponse = await fetch(url)
    if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
    const lien = URL.createObjectURL(await reponse.blob())
    if (onglet) onglet.location.href = lien
    else window.location.href = lien
  } catch (err) {
    onglet?.close()
    throw err
  }
}

export function useDocumentsSaison(seasonId) {
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const charger = useCallback(() => {
    api
      .documentsSaison(seasonId)
      .then((d) => {
        setData(d)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
  }, [seasonId])
  useEffect(charger, [charger])
  return { data, setData, erreur, setErreur, charger }
}

export function Etape6Documents({ season, docs }) {
  const { data, setData, erreur, setErreur, charger } = docs
  const [budget, setBudget] = useState(false)
  const [rapportOuvert, setRapportOuvert] = useState(null) // le nom du fichier : le rapport à lire et corriger
  const [rapportId, setRapportId] = useState(null)
  const [ajout, setAjout] = useState('')
  const [produits, setProduits] = useState([]) // noms des documents produits depuis l'ouverture de l'écran
  const [enCours, setEnCours] = useState('')
  const [apercu, setApercu] = useState(null) // { titre, charger } : un Excel, un Word, le FEC dans OnlyOffice

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!data) return <p className="muted">Chargement…</p>
  if (budget)
    return (
      <BudgetPrevisionnel
        season={season}
        onClose={() => {
          setBudget(false)
          charger()
        }}
      />
    )

  const reportId = rapportId ?? data.reportId
  if (rapportOuvert) return <RapportCorrection reportId={reportId} titre={rapportOuvert} onClose={() => setRapportOuvert(null)} />

  // Les choix tels qu'à l'écran, envoyés en entier à chaque changement : un
  // fichier de l'an dernier coché = « Comme l'an dernier », un document ajouté
  // coché = « Nouveau », ni l'un ni l'autre = « Non ».
  function items(choix, nature = () => ({})) {
    const modeles = data.models.map((m) => {
      const kind = nature(m).kind ?? m.kind
      const voulu = choix(kind)
      return { nodeId: m.nodeId, name: m.name, kind, selected: voulu ? voulu === 'same' : kind !== m.kind ? kind !== AUTRE : m.selected }
    })
    const ajoutes = data.rows.map((r) => ({ nodeId: null, name: '', kind: r.kind, selected: (choix(r.kind) ?? r.choice) === 'new' }))
    return [...modeles, ...ajoutes]
  }

  async function enregistrer(liste) {
    try {
      setData({ ...(await api.choisirDocuments(season.id, liste)), reportId: data.reportId })
    } catch (err) {
      setErreur(err.message)
    }
  }

  const choisir = (kind, choice) => enregistrer(items((k) => (k === kind ? choice : null)))
  // « Tout comme l'an dernier » : là où il y a un fichier ; « Tout nouveau » : sauf les « Non ».
  const toutChoisir = (choice) =>
    enregistrer(items((k) => (data.rows.some((r) => r.kind === k && (choice === 'same' ? r.lastYear : r.choice !== 'none')) ? choice : null)))

  function telecharger(d) {
    telechargerFichier(api.urlDocumentSaison(season.id, d.kind, d.name), d.name).catch((err) => setErreur(err.message))
  }

  // « Produire » un document à la fois (Seb, 20/11) : l'appli le calcule, puis on peut le voir.
  async function produire(d) {
    setEnCours(d.name)
    try {
      const reponse = await fetch(api.urlDocumentSaison(season.id, d.kind, d.name))
      if (!reponse.ok) throw new Error(`Le document n’a pas pu être produit (${reponse.status})`)
      setProduits((p) => [...p, d.name])
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours('')
    }
  }

  async function rediger() {
    try {
      setRapportId((await api.bilanDuRapport(season.id)).reportId)
    } catch (err) {
      setErreur(err.message)
    }
  }

  // « Voir » : un PDF dans un nouvel onglet, le reste dans OnlyOffice en lecture seule (Seb 13/11).
  function voir(d) {
    if (d.name.endsWith('.pdf')) voirPdf(api.urlDocumentSaison(season.id, d.kind, d.name)).catch((err) => setErreur(err.message))
    else setApercu({ titre: d.name, charger: () => api.apercuDocumentSaison(season.id, d.kind, d.name) })
  }

  const voirEtTelecharger = (d) => (
    <>
      <button type="button" className="btn btn--secondary" onClick={() => voir(d)}>
        <Icon name="eye" size={16} /> Voir
      </button>
      <button type="button" className="btn btn--secondary" onClick={() => telecharger(d)}>
        <Icon name="download" size={16} /> Télécharger
      </button>
    </>
  )

  const budgetDoc = data.documents.find((d) => d.kind === 'budget')
  const autres = data.models.filter((m) => m.kind === AUTRE)

  return (
    <>
      {apercu && <Apercu titre={apercu.titre} charger={apercu.charger} onClose={() => setApercu(null)} />}
      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Documents {season.name}</span>
        <span className="fin-cp-s">Pour chaque document : le même que l’an dernier (même nom, année avancée), ou un nouveau.</span>
        {data.models.length > 0 && (
          <span className="fin-cp-a fin-docs__tout">
            <button type="button" className="btn btn--secondary" onClick={() => toutChoisir('same')}>
              Tout comme l’an dernier
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => toutChoisir('new')}>
              Tout nouveau
            </button>
          </span>
        )}
        {data.rows.map((r) => {
          const d = { kind: r.kind, name: r.name }
          const produit = produits.includes(r.name)
          return (
            <div key={r.kind} className="fin-docs__doc">
              <span className="fin-cp-t">{r.label}</span>
              <span className="fin-docs__trois">
                <button type="button" className="btn btn--secondary" aria-pressed={r.choice === 'same'} disabled={!r.lastYear} onClick={() => choisir(r.kind, 'same')}>
                  Comme l’an dernier
                </button>
                <button type="button" className="btn btn--secondary" aria-pressed={r.choice === 'new'} onClick={() => choisir(r.kind, 'new')}>
                  Nouveau
                </button>
                <button type="button" className="btn btn--secondary" aria-pressed={r.choice === 'none'} onClick={() => choisir(r.kind, 'none')}>
                  Non
                </button>
              </span>
              <span className="fin-cp-s">
                {r.choice === 'same' && `D’après « ${r.lastYear} » · `}
                {r.choice !== 'same' && !r.lastYear && 'Pas de fichier l’an dernier · '}
                {r.choice === 'none' ? 'Pas produit' : `Fichier : ${r.name}`}
                {produit && r.choice !== 'none' && (data.provisional ? ' · Produit, provisoire' : ' · Produit')}
              </span>
              {r.choice !== 'none' &&
                (r.kind === RAPPORT ? (
                  reportId != null ? (
                    <RapportFinancier
                      reportId={reportId}
                      seasonName={season.name}
                      titre={r.name}
                      sansDocs
                      rediger={rapportId != null}
                      onErreur={setErreur}
                      onApercu={() => setRapportOuvert(r.name)}
                    />
                  ) : (
                    <span className="fin-cp-a">
                      <button type="button" className="btn btn--secondary" onClick={rediger}>
                        <Icon name="edit" size={16} /> Rédiger
                      </button>
                    </span>
                  )
                ) : (
                  <span className="fin-cp-a">
                    <button type="button" className="btn btn--secondary" onClick={() => produire(d)} disabled={enCours === r.name}>
                      {enCours === r.name ? 'Calcul…' : produit ? 'Produire à nouveau' : 'Produire'}
                    </button>
                    {produit && voirEtTelecharger(d)}
                  </span>
                ))}
              {r.kind === 'fec' && r.choice !== 'none' && data.fecCheck && (
                <span className={data.fecCheck.ok ? 'fin-cp-s' : 'fin-cp-alerte'}>
                  {data.fecCheck.ok ? `FEC juste : ${data.fecCheck.entries} écriture(s) équilibrée(s)` : `FEC à corriger : ${data.fecCheck.problems.join(' ')}`}
                </span>
              )}
            </div>
          )
        })}
        {budgetDoc && (
          // Budget prévisionnel de la saison suivante (Seb, 20/11) : à remplir, puis Voir / Télécharger.
          <div className="fin-docs__doc">
            <span className="fin-cp-t">{budgetDoc.label}</span>
            <span className="fin-cp-s">Fichier : {budgetDoc.name}</span>
            <span className={budgetDoc.filled ? 'fin-cp-s' : 'fin-cp-alerte'}>{budgetDoc.filled ? 'Montants prévus tapés' : 'À remplir'}</span>
            <span className="fin-cp-a">
              <button type="button" className="btn btn--secondary" onClick={() => setBudget(true)}>
                <Icon name="edit" size={16} /> {budgetDoc.filled ? 'Modifier' : 'Remplir'}
              </button>
              {budgetDoc.filled && voirEtTelecharger(budgetDoc)}
            </span>
          </div>
        )}
        {autres.length > 0 && (
          <>
            <span className="fin-cp-t">Aussi dans Docs l’an dernier, à refaire à la main</span>
            {autres.map((m) => (
              <div key={m.nodeId} className="fin-docs__doc">
                <span>{m.name}</span>
                <span className="fin-docs__nature">
                  <span className="fin-cp-s">Si l’appli sait le faire, c’est un</span>
                  <select
                    className="field-input"
                    value={m.kind}
                    aria-label={`Nature de ${m.name}`}
                    onChange={(e) => enregistrer(items(() => null, (x) => (x.nodeId === m.nodeId ? { kind: e.target.value } : {})))}
                  >
                    {Object.entries(data.labels).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </span>
              </div>
            ))}
          </>
        )}
        {data.addable.length > 0 && (
          <label className="fin-cp-champ">
            <span>Ajouter un document</span>
            <select
              className="field-input"
              value={ajout}
              onChange={(e) => {
                const kind = e.target.value
                setAjout('')
                if (kind) enregistrer([...items(() => null), { nodeId: null, name: '', kind, selected: true }])
              }}
            >
              <option value="">Choisir…</option>
              {data.addable.map((k) => (
                <option key={k} value={k}>
                  {data.labels[k]}
                </option>
              ))}
            </select>
          </label>
        )}
        {data.provisional && (
          <span className="fin-cp-s">Tant que la saison n’est pas clôturée, chaque document porte la mention « provisoire ». Après la clôture, il prend son nom officiel.</span>
        )}
        <span className="fin-cp-s">Rien n’est rangé tout seul dans Docs : on télécharge, et on dépose soi-même dans Docs › Financier ce qu’on veut garder.</span>
      </div>
    </>
  )
}

// Étape 7 : clôturer la saison (§8.7), possible quand les étapes 1 à 6 sont vertes.
export function Etape7Cloture({ season, docs, pret, onChange }) {
  const { data, setData, setErreur } = docs
  const [depot, setDepot] = useState(null) // { place, count } après « Déposer »
  const [enCours, setEnCours] = useState(false)
  if (!data) return null
  const closing = data.closing

  async function basculer() {
    if (!closing && !window.confirm(`Clôturer la saison ${season.name} ?`)) return
    try {
      const r = closing ? await api.rouvrirSaison(season.id) : await api.cloturerSaison(season.id)
      setData((d) => ({ ...d, closing: r.closing }))
      docs.charger()
      onChange?.()
    } catch (err) {
      setErreur(err.message)
    }
  }

  // Après la clôture, la trésorière range elle-même les documents dans Docs (Seb 13/11).
  async function deposer() {
    setEnCours(true)
    try {
      setDepot(await api.deposerDocumentsSaison(season.id))
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  if (data.level !== 'complet') return <p className="muted">La clôture est en Engagement (partie double) (Comptes › ⋯ › Plan comptable).</p>
  return (
    <div className="fin-preparer__corps">
      {closing ? (
        <p>
          Saison clôturée le {dateFr(closing.closedAt.slice(0, 10))} : {closing.result > 0 ? 'déficit' : 'excédent'} de {euros(Math.abs(closing.result))}{' '}
          reporté, soldes de départ de la saison suivante en découlent.
        </p>
      ) : (
        <div className="fin-docs__cloture">
          <p>Clôturer {season.name} :</p>
          <ul>
            <li>porte le résultat de la saison au compte 110 Report à nouveau ;</li>
            <li>reporte les soldes de bilan comme soldes de départ de la saison suivante ;</li>
            <li>verrouille les écritures de la saison (cadenas) : plus de rattachement ni d’import de relevé sur la saison.</li>
          </ul>
        </div>
      )}
      <button type="button" className={closing ? 'btn btn--secondary' : 'btn btn--primary'} onClick={basculer} disabled={!closing && !pret}>
        {closing ? `Rouvrir ${season.name}` : `Clôturer ${season.name}`}
      </button>
      {!closing && !pret && <p className="fin-cp-s">Possible quand les étapes 1 à 6 sont vertes.</p>}
      {closing && (
        <div className="fin-docs__cloture">
          <p>Déposer les documents de l’étape 6, tels qu’aujourd’hui, dans Docs › {season.name} › Financier › Bilan financier : l’an prochain, l’étape 6 repartira d’eux.</p>
          <button type="button" className="btn btn--primary" onClick={deposer} disabled={enCours}>
            <Icon name="folder" size={16} /> {enCours ? 'Dépôt…' : 'Déposer les documents dans Docs'}
          </button>
          {depot && (
            <p className="fin-cp-s">
              {depot.count} document(s) déposé(s) dans {depot.place}.
            </p>
          )}
        </div>
      )}
      {data.closingHistory.length > 0 && (
        <p className="fin-cp-s">
          {data.closingHistory.map((h) => `Clôturée le ${dateFr(h.closedAt.slice(0, 10))}, rouverte le ${dateFr(h.reopenedAt.slice(0, 10))}`).join(' · ')}
        </p>
      )}
    </div>
  )
}
