// Comptes ⋯ › « Soldes de départ » (spec/modules/financier.md §8.7, niveau
// Complet) : un solde par compte du bilan au premier jour de la saison,
// repris de la Balance de l'an dernier ; l'appli compare les 512x aux
// relevés, la différence va dans 110 Report à nouveau.
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import './compta.css'

const SOLDES_EVENT = 'finances-soldes-depart'

// Entrée « Soldes de départ » du menu ⋯ (voir Financier.jsx).
export function requestSoldesDepart() {
  window.dispatchEvent(new Event(SOLDES_EVENT))
}

export const SOLDES_EVENTS = { soldes: SOLDES_EVENT }

const SOURCES = {
  saisie: 'Soldes repris par le trésorier.',
  cloture: 'Soldes reportés par la clôture de la saison précédente.',
  releves: 'Les soldes de l’an dernier ne sont pas encore repris : seule la trésorerie des relevés est connue, les dettes, créances et fonds partent de zéro.',
}

export default function SoldesDepart({ onClose }) {
  const [saisons, setSaisons] = useState([])
  const [seasonId, setSeasonId] = useState(null)
  const [data, setData] = useState(null)
  const [lignes, setLignes] = useState([])
  const [erreur, setErreur] = useState('')
  const [lecture, setLecture] = useState(null) // la Balance de l'an dernier lue, pas encore enregistrée
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api
      .saisons()
      .then(({ seasons }) => {
        setSaisons(seasons)
        setSeasonId((seasons.find((s) => s.current) ?? seasons[0])?.id ?? null)
      })
      .catch((err) => setErreur(err.message))
  }, [])

  useEffect(() => {
    if (seasonId == null) return
    api
      .soldesDepart(seasonId)
      .then((d) => {
        setData(d)
        setLecture(null)
        setLignes(d.accounts.map((a) => ({ ...a, balance: a.balance === 0 ? '' : String(a.balance) })))
      })
      .catch((err) => setErreur(err.message))
  }, [seasonId])

  // « Reprendre les soldes de l'an dernier » : l'appli lit la Balance de la
  // saison précédente dans Docs et remplit les cases ; rien n'est enregistré
  // avant « Utiliser ces soldes » (financier.md §8.7, Seb 10/11).
  async function reprendreAnDernier() {
    setEnCours(true)
    setErreur('')
    try {
      const lu = await api.soldesPrecedents(seasonId)
      const lus = new Map(lu.accounts.map((a) => [a.number, a]))
      const connus = new Set(lignes.map((l) => l.number))
      setLignes([
        ...lignes.map((l) => ({ ...l, balance: lus.has(l.number) ? String(lus.get(l.number).balance) : '' })),
        ...lu.accounts.filter((a) => !connus.has(a.number)).map((a) => ({ ...a, balance: String(a.balance) })),
      ].sort((a, b) => a.number.localeCompare(b.number)))
      setLecture(lu)
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  async function reprendre() {
    try {
      const d = await api.enregistrerSoldesDepart(
        seasonId,
        lignes.map((l) => ({ number: l.number, label: l.label, balance: Number(l.balance) || 0 })),
      )
      setData(d)
      setLecture(null)
      setLignes(d.accounts.map((a) => ({ ...a, balance: a.balance === 0 ? '' : String(a.balance) })))
      setErreur('')
    } catch (err) {
      setErreur(err.message)
    }
  }

  const debut = saisons.find((s) => s.id === seasonId)?.startDate
  const total = lignes.reduce((s, l) => s + (Number(l.balance) || 0), 0)
  // La vérification des banques : sur la lecture tant qu'elle n'est pas enregistrée, sinon sur l'enregistré.
  const verification = (lecture ?? data)?.bankCheck ?? []

  return (
    <Modal
      title="Soldes de départ"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={reprendre} disabled={!data || data.closed}>
          Utiliser ces soldes au {debut ? api.dateFr(debut) : 'début de la saison'}
        </button>
      }
    >
      <div className="fin-cp">
        <label className="fin-cp-champ">
          <span>Saison</span>
          <select className="field-input" value={seasonId ?? ''} onChange={(e) => setSeasonId(Number(e.target.value))}>
            {saisons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        {data && (
          <>
            <p className={data.source === 'releves' && !lecture ? 'fin-cp-alerte' : 'muted'}>{SOURCES[data.source]}</p>
            {data.source !== 'cloture' && !data.closed && (
              <div className="fin-preparer__bloc">
                <span className="fin-cp-s">
                  {lecture
                    ? `Soldes lus dans « ${lecture.file} » (saison ${lecture.previousSeason})${lecture.readBy === 'lecture' ? ', lus par l’appli : à vérifier ligne par ligne' : ''}. Vérifiez, corrigez au besoin, puis « Utiliser ces soldes ».`
                    : 'Déposez la Balance de l’an dernier dans Docs › Financier (saison précédente ou en cours, « Balance » dans le nom), appuyez sur Reprendre, vérifiez, puis « Utiliser ces soldes ». Sans Balance, remplissez les cases à la main.'}
                </span>
                <button type="button" className="btn btn--secondary" onClick={reprendreAnDernier} disabled={enCours}>
                  {enCours ? 'Lecture…' : 'Reprendre les soldes de l’an dernier'}
                </button>
              </div>
            )}
            <p className="muted">Solde positif = débiteur (banque, caisse), négatif = dû (fournisseurs, report).</p>
            <p className="muted">
              Ces soldes sont la première ligne de chaque compte au début de la saison. Ils servent pour le Grand livre et la Balance,
              la trésorerie de la Synthèse et du Rapport financier, et ce que la clôture reporte sur la saison suivante. Ils ne changent
              ni les dépenses, ni les recettes, ni le résultat.
            </p>
          </>
        )}
        {data?.closed && <p className="fin-cp-alerte">Saison clôturée : rouvrez-la (Bilan › Documents de l’AG) pour changer ses soldes.</p>}
        {lignes.map((l, i) => (
          <label key={l.number} className="fin-cp-champ fin-cp-solde">
            <span>
              {l.number} {l.label}
            </span>
            <input
              className="field-input"
              type="number"
              step="0.01"
              inputMode="decimal"
              value={l.balance}
              placeholder="0,00"
              onChange={(e) => setLignes((ls) => ls.map((x, j) => (j === i ? { ...x, balance: e.target.value } : x)))}
            />
          </label>
        ))}
        {verification.map((c) =>
          Math.round((c.statements - c.entered) * 100) === 0 ? null : (
            <p key={c.number} className="fin-cp-alerte">
              {c.number} {c.label} : les relevés donnent {api.euros(c.statements)} au début de la saison, {lecture ? 'la Balance donne' : 'vous avez'}{' '}
              {api.euros(c.entered)}
              {lecture ? ' : un chèque pas encore débité, ou une erreur à expliquer avant de valider.' : '.'}
            </p>
          ),
        )}
        <p className="muted">
          {Math.round(total * 100) === 0
            ? 'Les soldes s’équilibrent.'
            : `Différence de ${api.euros(-total)} : elle ira dans 110 Report à nouveau.`}
        </p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
