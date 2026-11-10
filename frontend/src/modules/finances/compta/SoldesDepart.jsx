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

// Ce que veut dire un solde qui n'est pas à zéro, et ce qui l'explique
// peut-être (Seb, 10/11) : règles fixes du plan comptable, rien d'inventé.
// Rend { texte, alerte, pistes: [phrases] } ou null.
function explication(ligne, data, verification, veille) {
  const montant = Number(ligne.balance) || 0
  if (!data || Math.round(montant * 100) === 0) return null
  const n = ligne.number
  const centimes = Math.round(montant * 100)
  // Une transaction bancaire du début de saison du même montant règle sans doute ce solde.
  const memeMontant = (data.earlyTransactions ?? [])
    .filter((t) => Math.round(t.amount * 100) === centimes)
    .slice(0, 2)
    .map((t) => `Transaction bancaire du même montant : ${api.dateFr(t.date)}, « ${t.label} ».`)
  if (n.startsWith('51') || n.startsWith('53')) {
    const c = verification.find((v) => v.number === n)
    const accord = c && Math.round((c.statements - c.entered) * 100) === 0
    return { texte: `L’argent ${n.startsWith('53') ? 'dans la caisse' : 'sur ce compte'} au ${veille}${accord ? ' : ✓ égal aux relevés.' : '.'}` }
  }
  if (n === '110') return { texte: 'Les fonds de l’association : ce qu’elle possède moins ce qu’elle doit, accumulé d’année en année.' }
  if (n.startsWith('471')) {
    return {
      alerte: true,
      texte: 'Argent pas encore classé : un compte d’attente doit être vide. Demandez à la trésorière ce que c’est, puis mettez la somme dans le bon compte.',
      pistes: memeMontant,
    }
  }
  if (n.startsWith('401')) {
    const pieces = data.unpaidBefore ?? []
    const total = Math.round(pieces.reduce((s, p) => s + p.amount, 0) * 100)
    const pistes = pieces.map((p) => `${p.number ? `${p.number} ` : ''}${p.title}, ${api.dateFr(p.date)} : ${api.euros(p.amount)}.`)
    if (pieces.length) pistes.unshift(total === -centimes ? 'Les factures non payées dans Pièces donnent exactement ce total :' : 'Factures non payées dans Pièces avant la saison :')
    return { texte: montant < 0 ? `Factures reçues, pas encore payées au ${veille}.` : `Fournisseurs payés d’avance au ${veille}.`, pistes: [...pistes, ...memeMontant] }
  }
  if (n.startsWith('467')) {
    return { texte: montant < 0 ? `Ce que l’association devait encore à ${ligne.label} au ${veille}.` : `Ce que ${ligne.label} devait encore à l’association au ${veille}.`, pistes: memeMontant }
  }
  if (n.startsWith('411')) {
    return { texte: montant > 0 ? `Ce que des adhérents devaient encore au ${veille}.` : `Ce que des adhérents avaient payé d’avance au ${veille}.`, pistes: memeMontant }
  }
  return memeMontant.length ? { texte: '', pistes: memeMontant } : null
}

// `initialSeasonId` : la saison ouverte au départ (depuis Préparer, celle du bilan) ; sinon la saison en cours.
export default function SoldesDepart({ onClose, initialSeasonId }) {
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
        setSeasonId((seasons.find((s) => s.id === initialSeasonId) ?? seasons.find((s) => s.current) ?? seasons[0])?.id ?? null)
      })
      .catch((err) => setErreur(err.message))
  }, [initialSeasonId])

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
  // La saison qui précède celle choisie : le bouton dit de quelle Balance viennent les soldes (Seb, 10/11).
  const precedente = saisons.filter((s) => debut && s.startDate < debut).sort((a, b) => (a.startDate < b.startDate ? 1 : -1))[0]
  const libelleReprise = `Reprendre les soldes de la Balance ${precedente ? precedente.name : 'de l’an dernier'} (Docs › Financier)`
  const total = lignes.reduce((s, l) => s + (Number(l.balance) || 0), 0)
  // La vérification des banques : sur la lecture tant qu'elle n'est pas enregistrée, sinon sur l'enregistré.
  const verification = (lecture ?? data)?.bankCheck ?? []
  // La veille de la saison : la date des soldes de départ.
  const veille = debut ? api.dateFr(new Date(new Date(`${debut}T12:00:00`).getTime() - 86400000).toISOString().slice(0, 10)) : 'début de la saison'

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
        {/* Les écarts avec les relevés d'abord : c'est ce qu'il faut lire avant la liste (Seb, 10/11). */}
        {verification.map((c) =>
          Math.round((c.statements - c.entered) * 100) === 0 ? null : (
            <p key={c.number} className="fin-cp-alerte">
              {c.number} {c.label} : les relevés donnent {api.euros(c.statements)} au début de la saison, {lecture ? 'la Balance donne' : 'vous avez'}{' '}
              {api.euros(c.entered)}
              {lecture ? ' : un chèque pas encore débité, ou une erreur à expliquer avant de valider.' : '.'}
            </p>
          ),
        )}
        {data && (
          <>
            <p className={data.source === 'releves' && !lecture ? 'fin-cp-alerte' : 'muted'}>{SOURCES[data.source]}</p>
            {data.source !== 'cloture' && !data.closed && (
              <div className="fin-preparer__bloc">
                <span className="fin-cp-s">
                  {lecture
                    ? `Soldes lus dans « ${lecture.file} » (saison ${lecture.previousSeason})${lecture.readBy === 'lecture' ? ', lus par l’appli : à vérifier ligne par ligne' : ''}. Vérifiez, corrigez au besoin, puis « Utiliser ces soldes ».`
                    : 'Déposez la Balance de l’an dernier dans Docs › Financier (saison précédente ou en cours, « Balance » dans le nom), appuyez sur le bouton, vérifiez, puis « Utiliser ces soldes ». Sans Balance, remplissez les cases à la main.'}
                </span>
                <button type="button" className="btn btn--secondary" onClick={reprendreAnDernier} disabled={enCours}>
                  {enCours ? 'Lecture…' : libelleReprise}
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
        {lignes.map((l, i) => {
          const ex = explication(l, data, verification, veille)
          return (
            <div key={l.number} className="fin-cp-solde-bloc">
              <label className="fin-cp-champ fin-cp-solde">
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
              {ex && (
                <div className="fin-cp-solde-pourquoi">
                  {ex.texte && <p className={ex.alerte ? 'fin-cp-alerte' : 'muted'}>{ex.texte}</p>}
                  {(ex.pistes ?? []).map((p) => (
                    <p key={p} className="muted">
                      {p}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )
        })}
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
