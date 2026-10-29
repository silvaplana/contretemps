// Bloc « Documents de l'AG » sous un bilan (spec/modules/financier.md §8.6) :
// Synthèse Dépenses-Recettes (Excel et à l'écran), et au niveau Complet
// Balance, Grand livre, Honoraires par professeur. Tout est additionné par
// l'appli depuis les lignes de banque et de caisse ; chaque fichier produit
// est aussi rangé dans Docs › Financier › AG. Le Rapport financier est
// rédigé par le modèle (le texte seulement : chaque montant est placé par
// l'appli, un nombre écrit par le modèle est signalé « à vérifier »).
import { useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import Modal from '../../../components/Modal.jsx'
import { enEuros } from '../../../utils/euros.js'
import { ouvrirDansDocs } from '../../documents/lienDocs.js'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import './compta.css'

const { euros, dateFr } = api

export default function DocumentsAG({ reportId, seasonName }) {
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const [voir, setVoir] = useState(false)

  useEffect(() => {
    if (reportId == null) return
    api
      .documentsAG(reportId)
      .then(setData)
      .catch((err) => setErreur(err.message))
  }, [reportId])

  if (reportId == null) return null

  function telecharger(doc) {
    telechargerFichier(api.urlDocumentAG(reportId, doc.id), `${doc.title} ${seasonName}.${doc.format}`).catch((err) => setErreur(err.message))
  }

  return (
    <div className="fin-cp">
      <h4 className="reports-subtitle">Documents de l’AG</h4>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!data && !erreur && <p className="muted">Chargement…</p>}
      {data && (
        <>
          <div className="fin-cp-carte">
            {data.documents.map((d) => (
              <div key={d.id} className="fin-cp-doc">
                <span className="fin-cp-t">{d.title}</span>
                <span className="fin-cp-a">
                  {d.id === 'synthese' && (
                    <button type="button" className="btn btn--secondary" onClick={() => setVoir((v) => !v)}>
                      <Icon name="eye" size={16} /> Voir
                    </button>
                  )}
                  <button type="button" className="btn btn--secondary" onClick={() => telecharger(d)}>
                    <Icon name="download" size={16} /> {d.format === 'pdf' ? 'PDF' : 'Excel'}
                  </button>
                </span>
                <span className="fin-cp-s">{SOUS_TITRES[d.id]}</span>
              </div>
            ))}
          </div>
          {voir && <Synthese s={data.synthese} />}
          {data.folderId != null && (
            <div className="fin-cp-boutons">
              <button type="button" className="btn btn--secondary" onClick={() => ouvrirDansDocs(data.folderId)}>
                <Icon name="docs" size={16} /> Ouvrir dans Docs
              </button>
            </div>
          )}
          <RapportFinancier reportId={reportId} seasonName={seasonName} onErreur={setErreur} />
          {data.level === 'complet' && (
            <Cloture reportId={reportId} seasonName={seasonName} closing={data.closing} onChange={(closing) => setData((d) => ({ ...d, closing }))} onErreur={setErreur} />
          )}
          <p className="muted">
            Additionnés par l’appli depuis les lignes de banque (compte du plan confirmé) et la caisse, du{' '}
            {dateFr(data.synthese.start)} au {dateFr(data.synthese.cutoff)}. Les fichiers vont dans Docs › Financier › AG.
            {data.level === 'simple' && ' Grand livre, Balance et Honoraires par professeur : niveau Complet (Comptes › ⋯ › Plan comptable).'}
          </p>
          {data.synthese.unclassified !== 0 && (
            <p className="fin-cp-proposition fin-cp-proposition--aucune">
              {euros(data.synthese.unclassified)} de lignes sans compte, sur « à classer » : Comptes › Sans compte.
            </p>
          )}
        </>
      )}
    </div>
  )
}

const SOUS_TITRES = {
  synthese: 'charges et produits par poste, trésorerie, fournisseurs à payer',
  balance: 'totaux débit / crédit et soldes par compte',
  'grand-livre': 'toutes les lignes, par compte, avec la pièce',
  honoraires: 'par professeur et par mois, pour la DAS-2',
}

// Clôture de la saison (§8.7) : résultat dans 110, soldes reportés sur la
// saison suivante, plus de rattachement tant qu'elle n'est pas rouverte.
function Cloture({ reportId, seasonName, closing, onChange, onErreur }) {
  async function basculer() {
    if (!closing && !window.confirm(`Clôturer la saison ${seasonName} ? Plus aucune ligne ne pourra changer sans la rouvrir.`)) return
    try {
      onChange((closing ? await api.rouvrir(reportId) : await api.cloturer(reportId)).closing)
    } catch (err) {
      onErreur(err.message)
    }
  }
  return (
    <div className="fin-cp-carte">
      <div className="fin-cp-doc">
        <span className="fin-cp-t">{closing ? `Saison clôturée le ${dateFr(closing.closedAt.slice(0, 10))}` : 'Clôture de la saison'}</span>
        <span className="fin-cp-a">
          <button type="button" className="btn btn--secondary" onClick={basculer}>
            {closing ? 'Rouvrir' : 'Clôturer'}
          </button>
        </span>
        <span className="fin-cp-s">
          {closing
            ? `${closing.result > 0 ? 'Déficit' : 'Excédent'} de ${euros(Math.abs(closing.result))} reporté ; les soldes de départ de la saison suivante en découlent.`
            : 'après le bilan officiel : le résultat va dans le report à nouveau, la saison est verrouillée'}
        </span>
      </div>
    </div>
  )
}

function RapportFinancier({ reportId, seasonName, onErreur }) {
  const [data, setData] = useState(null)
  const [rediger, setRediger] = useState(false)
  const [voir, setVoir] = useState(false)

  useEffect(() => {
    api.rapportFinancier(reportId).then(setData).catch((err) => onErreur(err.message))
  }, [reportId, onErreur])

  const rapport = data?.rapport

  function telecharger(format) {
    telechargerFichier(api.urlRapportFinancier(reportId, format), `Rapport financier ${seasonName}.${format}`).catch((err) =>
      onErreur(err.message),
    )
  }

  return (
    <>
      <div className="fin-cp-carte">
        <div className="fin-cp-doc fin-cp-doc--large">
          <span className="fin-cp-t">Rapport financier</span>
          <span className="fin-cp-a">
            <button type="button" className="btn btn--secondary" onClick={() => setRediger(true)} disabled={!data}>
              <Icon name="edit" size={16} /> {rapport ? 'Rédiger à nouveau' : 'Rédiger'}
            </button>
            {rapport && (
              <>
                <button type="button" className="btn btn--secondary" onClick={() => setVoir((v) => !v)}>
                  <Icon name="eye" size={16} /> Voir
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => telecharger('docx')}>
                  <Icon name="download" size={16} /> Word
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => telecharger('pdf')}>
                  <Icon name="download" size={16} /> PDF
                </button>
              </>
            )}
          </span>
          <span className="fin-cp-s">
            {rapport
              ? `rédigé le ${dateFr(rapport.createdAt.slice(0, 10))} (${rapport.modelLabel}, ${enEuros(rapport.costUsd)})`
              : 'recettes, dépenses, points à revoir, conclusion : le texte est rédigé, les chiffres placés par l’appli'}
          </span>
        </div>
        {rapport?.warnings.length > 0 && (
          <p className="fin-cp-alerte">À vérifier avant l’AG : {rapport.warnings.join(' ')}</p>
        )}
        {voir && rapport && <TexteRapport r={rapport} />}
      </div>
      {rediger && data && (
        <RedigerModal
          reportId={reportId}
          options={data}
          onClose={() => setRediger(false)}
          onRedige={(r) => {
            setData((d) => ({ ...d, rapport: r }))
            setRediger(false)
            setVoir(true)
          }}
        />
      )}
    </>
  )
}

function TexteRapport({ r }) {
  return (
    <div className="fin-cp-rapport">
      <p>
        Saison {r.season}, du {dateFr(r.period.start)} au {dateFr(r.period.end)}. {r.introduction}
      </p>
      <h5>A - Recettes</h5>
      {r.recettes.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      <h5>B - Dépenses</h5>
      {r.depenses.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
      {r.points.length > 0 && (
        <>
          <h5>Points à revoir</h5>
          <ul>
            {r.points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </>
      )}
      <h5>Conclusion</h5>
      <p>{r.conclusion}</p>
    </div>
  )
}

function RedigerModal({ reportId, options, onClose, onRedige }) {
  const [form, setForm] = useState({ prompt: options.rapport?.prompt ?? '', model: options.rapport?.model ?? options.defaultModel })
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const champ = (nom) => (e) => setForm((f) => ({ ...f, [nom]: e.target.value }))

  async function lancer() {
    setEnCours(true)
    setErreur('')
    try {
      onRedige(await api.redigerRapport(reportId, form))
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Rédiger le rapport financier"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={lancer} disabled={enCours}>
          {enCours ? 'Rédaction en cours…' : 'Rédiger'}
        </button>
      }
    >
      <div className="fin-cp">
        <label className="fin-cp-champ">
          <span>Consignes du trésorier (ce qui explique les hausses et les baisses, les points à revoir)</span>
          <textarea
            className="field-input"
            rows={4}
            value={form.prompt}
            onChange={champ('prompt')}
            placeholder="Ex : la location a baissé car le gala a eu lieu à la salle des fêtes ; point à revoir : l’assurance."
          />
        </label>
        <label className="fin-cp-champ">
          <span>Modèle</span>
          <select className="field-input" value={form.model} onChange={champ('model')}>
            {options.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <p className="muted">
          Le texte est rédigé d’après la Synthèse de la saison, celle de la saison précédente et l’analyse du bilan. Chaque
          montant est placé par l’appli ; le Word et le PDF vont dans Docs › Financier › AG.
        </p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}

function Groupes({ groupes }) {
  return groupes.map((g) => (
    <tbody key={g.code}>
      <tr className="grp">
        <td colSpan={2}>
          {g.code} · {g.label}
        </td>
      </tr>
      {g.lines.map((l) => (
        <tr key={l.number}>
          <td>{l.label}</td>
          <td className="r">{euros(l.amount)}</td>
        </tr>
      ))}
    </tbody>
  ))
}

function Synthese({ s }) {
  return (
    <>
      <div className="fin-cp-carte">
        <table className="fin-cp-table">
          <Groupes groupes={s.charges} />
          <tbody>
            <tr className="tot">
              <td>Total des charges</td>
              <td className="r">{euros(s.totalCharges)}</td>
            </tr>
          </tbody>
          <Groupes groupes={s.produits} />
          <tbody>
            <tr className="tot">
              <td>Total des produits</td>
              <td className="r">{euros(s.totalProduits)}</td>
            </tr>
            <tr className="tot">
              <td>{s.result < 0 ? 'Déficit' : 'Excédent'}</td>
              <td className={s.result < 0 ? 'r unpaid-amount' : 'r success-state'}>{euros(s.result)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="fin-cp-carte">
        <table className="fin-cp-table">
          <tbody>
            <tr className="grp">
              <td colSpan={2}>Trésorerie au {dateFr(s.cutoff)}</td>
            </tr>
            {s.treasury.map((t) => (
              <tr key={t.label}>
                <td>{t.label}</td>
                <td className="r">{euros(t.amount)}</td>
              </tr>
            ))}
            <tr className="tot">
              <td>Solde de trésorerie</td>
              <td className="r">{euros(s.treasuryTotal)}</td>
            </tr>
            <tr>
              <td>Fournisseurs à payer{s.unpaid.length > 0 && ` (${s.unpaid.map((u) => u.title).join(', ')})`}</td>
              <td className="r">{euros(s.unpaidTotal)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {s.events.map((e) => (
        <div key={e.event} className="fin-cp-carte">
          <table className="fin-cp-table">
            <tbody>
              <tr className="grp">
                <td colSpan={2}>{e.event}</td>
              </tr>
              <tr>
                <td>Ressources</td>
                <td className="r">{euros(e.resources)}</td>
              </tr>
              <tr>
                <td>Coût</td>
                <td className="r">{euros(e.cost)}</td>
              </tr>
              <tr className="tot">
                <td>{e.profit < 0 ? 'Perte' : 'Bénéfice'}</td>
                <td className="r">{euros(e.profit)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
    </>
  )
}
