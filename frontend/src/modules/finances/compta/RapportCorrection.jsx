// Bilan › Préparer, étape 6 › Rapport financier › Voir (spec/modules/financier.md
// §8.6, Seb 20/11 ; maquette https://claude.ai/artifact/SSZArsbq9CQtTU1cE2vzkz) :
// le texte du rapport, et dessous « Ce qu'il faut changer » : la consigne est
// appliquée, le reste ne bouge pas, les chiffres restent ceux de l'appli. Le
// passage changé est surligné ; « Annuler la dernière correction » revient.
import { useEffect, useState } from 'react'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import './compta.css'

// Tous les paragraphes d'un rapport, pour repérer ce qui a changé.
function textes(r) {
  if (!r) return []
  const complements = (r.complements ?? []).flatMap((c) => [c.titre, ...c.paragraphes, ...(c.tableau ? c.tableau.lignes.map((l) => l.join(' ')) : [])])
  return [r.introduction, ...r.recettes, ...r.depenses, ...r.points, ...complements, r.conclusion]
}

export default function RapportCorrection({ reportId, titre, onClose }) {
  const [rapport, setRapport] = useState(null)
  const [avant, setAvant] = useState(null) // les textes d'avant la dernière correction faite ici
  const [consigne, setConsigne] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .rapportFinancier(reportId)
      .then((d) => setRapport(d.rapport))
      .catch((err) => setErreur(err.message))
  }, [reportId])

  async function corriger() {
    setEnCours(true)
    setErreur('')
    try {
      const corrige = await api.corrigerRapport(reportId, consigne)
      setAvant(textes(rapport))
      setRapport(corrige)
      setConsigne('')
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  async function annuler() {
    setErreur('')
    try {
      setRapport((await api.annulerCorrectionRapport(reportId)).rapport)
      setAvant(null)
    } catch (err) {
      setErreur(err.message)
    }
  }

  function telecharger(format) {
    const nom = titre.replace(/\.docx$/, '')
    telechargerFichier(api.urlRapportFinancier(reportId, format, nom), `${nom}.${format}`).catch((err) => setErreur(err.message))
  }

  if (!rapport) return erreur ? <p className="login-screen__erreur">{erreur}</p> : <p className="muted">Chargement…</p>

  const neuf = (t) => (avant && !avant.includes(t) ? 'fin-rapport__neuf' : undefined)
  const paragraphes = (liste) =>
    liste.map((t) => (
      <p key={t} className={neuf(t)}>
        {t}
      </p>
    ))

  return (
    <div className="fin-cp fin-rapport">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Étapes du bilan
      </button>
      <h3>{titre.replace(/\.docx$/, '')}</h3>
      <div className="fin-rapport__texte">
        <p className={neuf(rapport.introduction)}>{rapport.introduction}</p>
        <h4>A - Recettes</h4>
        {paragraphes(rapport.recettes)}
        <h4>B - Dépenses</h4>
        {paragraphes(rapport.depenses)}
        {rapport.points.length > 0 && (
          <>
            <h4>Points à revoir</h4>
            <ul>
              {rapport.points.map((t) => (
                <li key={t} className={neuf(t)}>
                  {t}
                </li>
              ))}
            </ul>
          </>
        )}
        {(rapport.complements ?? []).map((c) => (
          <div key={c.titre}>
            <h4 className={neuf(c.titre)}>{c.titre}</h4>
            {paragraphes(c.paragraphes)}
            {c.tableau && (
              <div className="fin-balance__table">
                <table>
                  <thead>
                    <tr>
                      {c.tableau.entetes.map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {c.tableau.lignes.map((l) => (
                      <tr key={l.join('|')} className={neuf(l.join(' '))}>
                        {l.map((x, i) => (
                          <td key={i}>{x}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
        <h4>Conclusion</h4>
        <p className={neuf(rapport.conclusion)}>{rapport.conclusion}</p>
      </div>
      {rapport.warnings.length > 0 && <p className="fin-cp-alerte">À vérifier avant l’AG : {rapport.warnings.join(' ')}</p>}
      <div className="fin-cp-a">
        <button type="button" className="btn btn--secondary" onClick={() => telecharger('docx')}>
          Word
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => telecharger('pdf')}>
          PDF
        </button>
      </div>
      <label className="fin-cp-champ">
        <span>Ce qu’il faut changer</span>
        <textarea
          className="field-input"
          rows={4}
          value={consigne}
          onChange={(e) => setConsigne(e.target.value)}
          placeholder="Ex : ajoute un comparatif du nombre d’élèves sur trois saisons."
        />
      </label>
      <p className="muted">Le reste du texte ne bouge pas. Les chiffres viennent de l’appli.</p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button type="button" className="btn btn--primary" onClick={corriger} disabled={enCours || !consigne.trim()}>
        {enCours ? 'Correction en cours…' : 'Corriger'}
      </button>
      {rapport.correction && (
        <button type="button" className="btn btn--secondary" onClick={annuler} disabled={enCours}>
          Annuler la dernière correction
        </button>
      )}
    </div>
  )
}
