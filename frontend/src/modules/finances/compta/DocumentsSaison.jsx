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
  const { data, setData, erreur, setErreur } = docs
  const [rapportId, setRapportId] = useState(null)
  const [ajout, setAjout] = useState('')
  const [apercu, setApercu] = useState(null) // { titre, charger } : un Excel, un Word, le FEC dans OnlyOffice

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!data) return <p className="muted">Chargement…</p>

  const reportId = rapportId ?? data.reportId

  // Les choix tels qu'à l'écran, envoyés en entier à chaque changement.
  function items(change) {
    const modeles = data.models.map((m) => ({ nodeId: m.nodeId, name: m.name, kind: m.kind, selected: m.selected, ...change(m) }))
    const ajoutes = data.documents.filter((d) => d.nodeId == null).map((d) => ({ nodeId: null, name: '', kind: d.kind, selected: true }))
    return [...modeles, ...ajoutes]
  }

  async function enregistrer(liste) {
    try {
      setData({ ...(await api.choisirDocuments(season.id, liste)), reportId: data.reportId })
    } catch (err) {
      setErreur(err.message)
    }
  }

  function telecharger(d) {
    telechargerFichier(api.urlDocumentSaison(season.id, d.kind, d.name), d.name).catch((err) => setErreur(err.message))
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

  return (
    <>
      {apercu && <Apercu titre={apercu.titre} charger={apercu.charger} onClose={() => setApercu(null)} />}
      {data.models.length > 0 && (
        <div className="fin-preparer__bloc">
          <span className="fin-cp-t">Documents à produire, d’après Docs › Financier › Bilan financier {data.previousSeason}</span>
          <span className="fin-cp-s">
            L’appli a reconnu chaque fichier d’après son contenu, puis son nom. Corrigez la nature si besoin, décochez ce qu’on ne refait pas.
          </span>
          {data.models.map((m) => (
            <label key={m.nodeId} className="fin-docs__choix">
              <input
                type="checkbox"
                checked={m.selected}
                onChange={(e) => enregistrer(items((x) => (x.nodeId === m.nodeId ? { selected: e.target.checked } : {})))}
              />
              <span>
                <span className="fin-cp-t">{m.name}</span>
                <span className="fin-docs__nature">
                  <span className="fin-cp-s">reconnu comme</span>
                  <select
                    className="field-input"
                    value={m.kind}
                    onChange={(e) => enregistrer(items((x) => (x.nodeId === m.nodeId ? { kind: e.target.value } : {})))}
                  >
                    {Object.entries(data.labels).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </span>
              </span>
            </label>
          ))}
        </div>
      )}

      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Documents {season.name}</span>
        {data.documents.length === 0 && <span className="fin-cp-s">Aucun document coché.</span>}
        {data.documents.map((d) =>
          d.kind === RAPPORT && d.available ? (
            reportId != null ? (
              <RapportFinancier
                key={`${d.kind}-${d.nodeId}`}
                reportId={reportId}
                seasonName={season.name}
                titre={d.name}
                sansDocs
                rediger={rapportId != null}
                onErreur={setErreur}
                onApercu={() => setApercu({ titre: d.name, charger: () => api.apercuRapportFinancier(reportId, d.name.replace(/\.docx$/, '')) })}
              />
            ) : (
              <div key={`${d.kind}-${d.nodeId}`} className="fin-docs__doc">
                <span className="fin-cp-t">{d.name}</span>
                <span className="fin-cp-s">Rapport financier : texte rédigé d’après les chiffres de la saison, à relire{d.model ? ` · nommé comme « ${d.model} »` : ''}</span>
                <span className="fin-cp-a">
                  <button type="button" className="btn btn--secondary" onClick={rediger}>
                    <Icon name="edit" size={16} /> Rédiger
                  </button>
                </span>
              </div>
            )
          ) : (
            <div key={`${d.kind}-${d.nodeId}`} className="fin-docs__doc">
              <span className="fin-cp-t">{d.name}</span>
              <span className="fin-cp-s">
                {d.kind === AUTRE ? 'À faire à la main, d’après le fichier de l’an dernier' : d.label}
                {d.kind !== AUTRE && d.model ? ` · nommé comme « ${d.model} »` : ''}
                {!d.available && ' · niveau Complet (Comptes › ⋯ › Plan comptable)'}
              </span>
              {d.kind !== AUTRE && d.available && (
                <span className="fin-cp-a">
                  <button type="button" className="btn btn--secondary" onClick={() => voir(d)}>
                    <Icon name="eye" size={16} /> Voir
                  </button>
                  <button type="button" className="btn btn--secondary" onClick={() => telecharger(d)}>
                    <Icon name="download" size={16} /> Télécharger
                  </button>
                </span>
              )}
              {d.kind === 'fec' && data.fecCheck && (
                <span className={data.fecCheck.ok ? 'fin-cp-s' : 'fin-cp-alerte'}>
                  {data.fecCheck.ok ? `FEC juste : ${data.fecCheck.entries} écriture(s) équilibrée(s)` : `FEC à corriger : ${data.fecCheck.problems.join(' ')}`}
                </span>
              )}
            </div>
          ),
        )}
        {data.addable.length > 0 && (
          <label className="fin-cp-champ">
            <span>Ajouter un document que l’appli sait faire</span>
            <select
              className="field-input"
              value={ajout}
              onChange={(e) => {
                const kind = e.target.value
                setAjout('')
                if (kind) enregistrer([...items(() => ({})), { nodeId: null, name: '', kind, selected: true }])
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
        <span className="fin-cp-s">Rien n’est rangé tout seul dans Docs : on télécharge, et on dépose soi-même dans Docs › Financier ce qu’on veut garder.</span>
      </div>
    </>
  )
}

// Étape 7 : clôturer la saison (§8.7), possible quand les étapes 1 à 6 sont vertes.
export function Etape7Cloture({ season, docs, pret, onChange }) {
  const { data, setData, setErreur } = docs
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

  if (data.level !== 'complet') return <p className="muted">La clôture est au niveau Complet (Comptes › ⋯ › Plan comptable).</p>
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
      {data.closingHistory.length > 0 && (
        <p className="fin-cp-s">
          {data.closingHistory.map((h) => `Clôturée le ${dateFr(h.closedAt.slice(0, 10))}, rouverte le ${dateFr(h.reopenedAt.slice(0, 10))}`).join(' · ')}
        </p>
      )}
    </div>
  )
}
