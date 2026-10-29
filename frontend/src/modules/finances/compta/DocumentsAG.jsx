// Bloc « Documents de l'AG » sous un bilan (spec/modules/financier.md §8.6) :
// Synthèse Dépenses-Recettes (Excel et à l'écran), et au niveau Complet
// Balance, Grand livre, Honoraires par professeur. Tout est additionné par
// l'appli depuis les lignes de banque et de caisse ; chaque fichier produit
// est aussi rangé dans Docs › Financier › AG. Le Rapport financier est
// rédigé par le modèle (le texte seulement : chaque montant est placé par
// l'appli, un nombre écrit par le modèle est signalé « à vérifier »).
import { useEffect, useRef, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import Modal from '../../../components/Modal.jsx'
import { enEuros } from '../../../utils/euros.js'
import { documentsApi } from '../../../api/documents.js'
import { ouvrirDansDocs } from '../../documents/lienDocs.js'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import './compta.css'

const { euros, dateFr } = api
// Au retour de Docs, le bloc revient à l'écran (voir ouvrirFichier).
const RETOUR_KEY = 'finances-documents-ag-retour'

// L'œil d'un document : le fichier est produit et rangé dans Docs, puis
// ouvert comme dans Docs (Word, Excel : OnlyOffice ; PDF : la visionneuse
// du téléphone, qui s'ouvre pendant le toucher sinon le navigateur bloque).
// Fermer l'aperçu ramène au Bilan.
async function ouvrirFichier(produire, pdf) {
  const telephone = pdf && !navigator.pdfViewerEnabled
  const onglet = telephone ? window.open('', '_blank') : null
  try {
    const { id, orgId } = await produire()
    if (!telephone) {
      try {
        sessionStorage.setItem(RETOUR_KEY, '1')
      } catch {
        // Stockage indisponible : le retour se fait en haut du bilan.
      }
      return ouvrirDansDocs(id, { retour: true })
    }
    const url = await documentsApi(orgId).lienFichier(id)
    if (onglet) onglet.location.href = url
    else window.location.href = url
  } catch (err) {
    onglet?.close()
    throw err
  }
}

// L'icône Docs : le fichier est produit et rangé, puis Docs s'ouvre sur
// son dossier (Financier › AG).
async function allerDansDocs(produire, folderId) {
  await produire()
  ouvrirDansDocs(folderId)
}

export default function DocumentsAG({ reportId, seasonName }) {
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const bloc = useRef(null)

  useEffect(() => {
    if (!data) return
    try {
      if (!sessionStorage.getItem(RETOUR_KEY)) return
      sessionStorage.removeItem(RETOUR_KEY)
    } catch {
      return
    }
    bloc.current?.scrollIntoView({ block: 'start' })
  }, [data])

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
    <div className="fin-cp" ref={bloc}>
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
                  <button
                    type="button"
                    className="btn btn--secondary"
                    onClick={() => ouvrirFichier(() => api.documentAGDansDocs(reportId, d.id), d.format === 'pdf').catch((err) => setErreur(err.message))}
                  >
                    <Icon name="eye" size={16} /> Voir
                  </button>
                  <button type="button" className="btn btn--secondary" onClick={() => telecharger(d)}>
                    <Icon name="download" size={16} /> {d.format === 'pdf' ? 'PDF' : 'Excel'}
                  </button>
                  {data.folderId != null && (
                    <button
                      type="button"
                      className="btn btn--secondary"
                      aria-label="Voir dans Docs"
                      title="Voir dans Docs"
                      onClick={() => allerDansDocs(() => api.documentAGDansDocs(reportId, d.id), data.folderId).catch((err) => setErreur(err.message))}
                    >
                      <Icon name="folder" size={16} />
                    </button>
                  )}
                </span>
                <span className="fin-cp-s">{SOUS_TITRES[d.id]}</span>
              </div>
            ))}
          </div>
          <RapportFinancier reportId={reportId} seasonName={seasonName} folderId={data.folderId} onErreur={setErreur} />
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

function RapportFinancier({ reportId, seasonName, folderId, onErreur }) {
  const [data, setData] = useState(null)
  const [rediger, setRediger] = useState(false)

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
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => ouvrirFichier(() => api.rapportDansDocs(reportId, 'docx'), false).catch((err) => onErreur(err.message))}
                >
                  <Icon name="eye" size={16} /> Voir
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => telecharger('docx')}>
                  <Icon name="download" size={16} /> Word
                </button>
                <button type="button" className="btn btn--secondary" onClick={() => telecharger('pdf')}>
                  <Icon name="download" size={16} /> PDF
                </button>
                {folderId != null && (
                  <button
                    type="button"
                    className="btn btn--secondary"
                    aria-label="Voir dans Docs"
                    title="Voir dans Docs"
                    onClick={() => allerDansDocs(() => api.rapportDansDocs(reportId, 'docx'), folderId).catch((err) => onErreur(err.message))}
                  >
                    <Icon name="folder" size={16} />
                  </button>
                )}
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
      </div>
      {rediger && data && (
        <RedigerModal
          reportId={reportId}
          options={data}
          onClose={() => setRediger(false)}
          onRedige={(r) => {
            setData((d) => ({ ...d, rapport: r }))
            setRediger(false)
          }}
        />
      )}
    </>
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
