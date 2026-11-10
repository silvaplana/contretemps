// Bilan › Préparer (spec/modules/financier.md §8.10, Seb 9/11) : les six
// étapes du bilan d'une saison, dans l'ordre, chacune avec ce qui reste à
// faire. Rien ne se calcule sans que la trésorière l'ait vu. Un numéro de
// compte ne s'affiche jamais seul : toujours avec son libellé.
import { useCallback, useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import * as sessionApi from '../../../api/session.js'
import * as nfApi from '../../../api/notesFrais.js'
import { requestACote, requestSousOnglet } from '../navigation.js'
import RelevesGrille from '../RelevesGrille.jsx'
import SoldesDepart from './SoldesDepart.jsx'
import FicheOperation from './FicheOperation.jsx'
import Modal from '../../../components/Modal.jsx'
import { nomCompte } from './PlanComptable.jsx'
import * as api from '../api.js'
import './compta.css'

const { euros, dateFr } = api

export default function Preparer({ season, onDocuments }) {
  const [etat, setEtat] = useState(null)
  const [rapprocher, setRapprocher] = useState(null) // compteurs de Pièces › Rapprocher sur la saison
  const [erreur, setErreur] = useState('')
  const [ouverte, setOuverte] = useState(null) // étape dépliée : 1 à 6
  const [ficheOp, setFicheOp] = useState(null)
  const [enCours, setEnCours] = useState(null)

  const charger = useCallback(() => {
    api
      .preparation(season.id)
      .then((d) => {
        setEtat(d)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
    nfApi
      .rapprochement(season.startDate, season.endDate)
      .then(setRapprocher)
      .catch(() => setRapprocher(null))
  }, [season])
  useEffect(charger, [charger])

  async function validerCompte(groupe) {
    setEnCours(groupe.account.id)
    try {
      await api.validerCompte(season.id, groupe.operations.map((o) => o.id), groupe.account.id)
      charger()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(null)
    }
  }

  function ouvrirRapprocher() {
    sessionApi.sauvegarderEcran('financier-pieces', 'rapprocher')
    requestSousOnglet('pieces')
  }

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!etat) return <p className="muted">Chargement…</p>

  const { statements, opening, classify, controls, offBank, comparison } = etat
  const aRapprocher = rapprocher ? rapprocher.paires.length + rapprocher.sans_paiement.filter((p) => p.a_rapprocher).length : 0
  const resteEtape3 = aRapprocher + classify.withoutAccount
  const controlesKo = controls.filter((c) => !c.ok).length
  const etapes = [
    { n: 1, titre: 'Obtenir les relevés', reste: statements.missing, detail: statements.ok ? `${statements.accounts} compte(s), tous les mois sont là` : `${statements.missing} mois à importer` },
    {
      n: 2,
      titre: 'Reprendre les soldes de départ',
      reste: opening.toCarry ? 1 : opening.mismatches,
      detail: opening.ok ? SOURCES[opening.source] : opening.toCarry ? 'Les soldes de l’an dernier ne sont pas repris : seule la trésorerie des relevés est connue' : `${opening.mismatches} compte(s) en écart avec les relevés`,
    },
    { n: 3, titre: 'Rapprocher les factures et classer les transactions bancaires', reste: resteEtape3, detail: resteEtape3 === 0 ? 'Chaque transaction bancaire a sa pièce ou son compte' : `${aRapprocher} facture(s) à rapprocher, ${classify.withoutAccount} transaction(s) bancaire(s) sans compte` },
    {
      n: 4,
      titre: 'Compter la caisse et les factures non payées',
      reste: 0,
      detail: `Caisse ${euros(offBank.cash)} · ${offBank.unpaid.length} facture${offBank.unpaid.length > 1 ? 's' : ''} non payée${offBank.unpaid.length > 1 ? 's' : ''} (${euros(offBank.unpaidTotal)})`,
    },
    { n: 5, titre: 'Passer les contrôles', reste: controlesKo, detail: controlesKo === 0 ? 'Tout est vert' : `${controlesKo} contrôle(s) en rouge` },
    {
      n: 6,
      titre: 'Produire les documents et comparer à l’an dernier',
      reste: comparison.unexplained,
      detail: comparison.previousSeason
        ? comparison.unexplained === 0
          ? `Comparée à ${comparison.previousSeason}, chaque écart est expliqué`
          : `${comparison.unexplained} compte(s) à expliquer par rapport à ${comparison.previousSeason}`
        : 'Première saison : pas de comparaison',
    },
  ]

  return (
    <div className="fin-cp fin-preparer">
      {etat.closed && <p className="muted">Saison clôturée : rouvrez-la (Clôture) pour changer quelque chose.</p>}
      <h3 className="fin-cp-t">Étapes du bilan {season.name}</h3>
      {/* Consulter sans quitter le bilan (Seb, 10/11 ; financier.md §8.10). */}
      <div className="fin-preparer__a-cote">
        <button type="button" className="btn btn--secondary" onClick={() => requestACote('comptes')}>
          Voir les Comptes
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => requestACote('pieces')}>
          Voir les Pièces
        </button>
      </div>
      <div className="fin-cp-carte">
        {etapes.map((e) => (
          <div key={e.n} className={`fin-cp-doc fin-cp-doc--large fin-preparer__etape${ouverte === e.n ? ' fin-preparer__etape--ouverte' : ''}`}>
            <button type="button" className="fin-preparer__tete" onClick={() => setOuverte(ouverte === e.n ? null : e.n)}>
              <span className={`fin-preparer__num${e.reste === 0 ? ' fin-preparer__num--ok' : ''}`}>{e.reste === 0 ? <Icon name="check" size={16} /> : e.n}</span>
              <span className="fin-cp-t">
                {e.n}. {e.titre}
                {e.reste > 0 && <span className="badge badge--warning fin-preparer__reste">{e.reste}</span>}
              </span>
              <span className="fin-cp-s">{e.detail}</span>
            </button>
            {ouverte === 1 && e.n === 1 && <RelevesGrille seasonId={season.id} onClose={() => setOuverte(null)} onImport={charger} />}
            {ouverte === 2 && e.n === 2 && <SoldesDepart initialSeasonId={season.id} onClose={() => setOuverte(null)} />}
            {ouverte === 3 && e.n === 3 && (
              <Etape3 rapprocher={rapprocher} aRapprocher={aRapprocher} classify={classify} enCours={enCours} onRapprocher={ouvrirRapprocher} onValider={validerCompte} onFiche={setFicheOp} />
            )}
            {ouverte === 4 && e.n === 4 && <Etape4 season={season} offBank={offBank} level={etat.level} onChange={charger} onErreur={setErreur} />}
            {ouverte === 6 && e.n === 6 && (
              <Etape6 season={season} comparison={comparison} onDocuments={onDocuments} onChange={charger} onErreur={setErreur} />
            )}
            {ouverte === 5 && e.n === 5 && (
              <ul className="fin-preparer__controles">
                {controls.map((c) => (
                  <li key={c.label} className={c.ok ? 'fin-preparer__ok' : 'fin-preparer__ko'}>
                    <Icon name={c.ok ? 'check' : 'info'} size={16} /> {c.label}
                    {!c.ok && c.detail && <span className="muted"> : {c.detail}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
      {ficheOp && (
        <FicheOperation
          operationId={ficheOp}
          onClose={() => setFicheOp(null)}
          onChange={charger}
        />
      )}
    </div>
  )
}

const SOURCES = {
  releves: 'Trésorerie des relevés au début de la saison',
  cloture: 'Reportés par la clôture de la saison précédente',
  saisie: 'Saisis et vérifiés contre les relevés',
}

// Étape 3 : d'abord Rapprocher (les pièces), puis un compte sur chaque
// transaction bancaire : à confirmer une par une quand l'appli ne propose
// rien, sinon par compte entier (« Valider le compte »).
function Etape3({ rapprocher, aRapprocher, classify, enCours, onRapprocher, onValider, onFiche }) {
  return (
    <div className="fin-preparer__corps">
      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Rapprocher les factures</span>
        <span className="fin-cp-s">
          {rapprocher
            ? `${rapprocher.paires.length} suggestion(s) de rattachement, ${rapprocher.sans_paiement.filter((p) => p.a_rapprocher).length} facture(s) à rapprocher, ${rapprocher.lignes_sans_piece.length} transaction(s) bancaire(s) sans facture`
            : 'Le rapprochement des pièces n’est pas disponible.'}
        </span>
        <button type="button" className={`btn ${aRapprocher > 0 ? 'btn--primary' : 'btn--secondary'}`} onClick={onRapprocher}>
          Ouvrir Rapprocher les factures
        </button>
      </div>

      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">À confirmer une par une · {classify.unsure.length}</span>
        {classify.unsure.length === 0 && <span className="fin-cp-s">Aucune : l’appli propose un compte pour chaque transaction bancaire restante.</span>}
        {classify.unsure.map((o) => (
          <button key={o.id} type="button" className="fin-preparer__ligne" onClick={() => onFiche(o.id)}>
            <span className="fin-preparer__libelle">
              {o.label}
              <span className="muted"> · {dateFr(o.date)}</span>
            </span>
            <span className="fin-preparer__montant">{euros(o.amount)}</span>
            <span className="fin-cp-proposition fin-cp-proposition--aucune">
              {o.chequeDeposit ? 'Remise de chèques : à ventiler entre ses comptes' : `Compte ? ${o.piece ? 'la pièce aide' : 'pas de pièce'}`}
            </span>
          </button>
        ))}
      </div>

      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Comptes proposés par l’appli · {classify.sure.reduce((n, g) => n + g.operations.length, 0)}</span>
        {classify.sure.length === 0 && <span className="fin-cp-s">Aucune transaction bancaire à valider par compte.</span>}
        {classify.sure.map((g) => (
          <div key={g.account.id} className="fin-preparer__groupe">
            <div className="fin-preparer__groupe-tete">
              <span className="fin-cp-t">
                {g.account.number} {g.account.label}
              </span>
              <button type="button" className="btn btn--primary" disabled={enCours !== null} onClick={() => onValider(g)}>
                Valider le compte : {g.operations.length} ligne{g.operations.length > 1 ? 's' : ''}
              </button>
            </div>
            {g.operations.map((o) => (
              <button key={o.id} type="button" className="fin-preparer__ligne" onClick={() => onFiche(o.id)}>
                <span className="fin-preparer__libelle">
                  {o.label}
                  <span className="muted"> · {dateFr(o.date)}</span>
                </span>
                <span className="fin-preparer__montant">{euros(o.amount)}</span>
                <span className="fin-cp-proposition">{o.reason}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

// Étape 4 : ce qui n'est pas sur les relevés. La caisse (Comptes › Caisse) et
// les factures validées pas encore payées : au niveau Complet elles sont dues
// (401 / 467x) au jour de la facture ; au niveau Simple elles restent dans
// « Fournisseurs à payer » de la Synthèse.
function Etape4({ season, offBank, level, onChange, onErreur }) {
  const [ajout, setAjout] = useState(false)

  async function supprimer(e) {
    try {
      await api.supprimerEcriture(e.id)
      onChange()
    } catch (err) {
      onErreur(err.message)
    }
  }

  return (
    <div className="fin-preparer__corps">
      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Caisse : {euros(offBank.cash)}</span>
        <span className="fin-cp-s">
          {offBank.cashLines} ligne{offBank.cashLines > 1 ? 's' : ''} ; la caisse se tient dans Comptes › Caisse.
        </span>
      </div>
      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Factures non payées · {offBank.unpaid.length}</span>
        <span className="fin-cp-s">
          {level === 'complet'
            ? 'Dues au dernier jour de la saison : en charge au jour de la facture, contre 401 Fournisseurs ou 467 Autres comptes débiteurs ou créditeurs.'
            : 'Niveau Simple (trésorerie) : elles restent dans « Fournisseurs à payer » de la Synthèse, sans écriture.'}
        </span>
        {offBank.unpaid.map((u, i) => (
          <div key={i} className="fin-preparer__ligne fin-preparer__ligne--texte">
            <span className="fin-preparer__libelle">
              {u.title}
              {u.date && <span className="muted"> · {dateFr(u.date)}</span>}
            </span>
            <span className="fin-preparer__montant">{euros(u.amount)}</span>
          </div>
        ))}
        {offBank.unpaid.length > 0 && <span className="fin-cp-s">Total : {euros(offBank.unpaidTotal)}. Elles se paient dans Pièces › Virements.</span>}
      </div>
      <div className="fin-preparer__bloc">
        <span className="fin-cp-t">Écritures à la main · {offBank.entries.length}</span>
        <span className="fin-cp-s">
          {level === 'complet'
            ? 'Ce qui n’est ni sur les relevés ni dans la caisse : une cotisation due (411), la régularisation du compte d’attente (471)… Une ligne par question : date, libellé, compte débité, compte crédité, montant.'
            : 'Au niveau Complet (Comptes › ⋯ › Plan comptable).'}
        </span>
        {offBank.entries.map((e) => (
          <div key={e.id} className="fin-preparer__ligne fin-preparer__ligne--texte fin-preparer__ecriture">
            <span className="fin-preparer__libelle">
              {e.label}
              <span className="muted"> · {dateFr(e.date)}</span>
            </span>
            <span className="fin-preparer__montant">{euros(e.amount)}</span>
            <span className="fin-cp-s">
              Débit {nomCompte(e.debit)} · Crédit {nomCompte(e.credit)}
            </span>
            <button type="button" className="icon-btn icon-btn--danger" aria-label="Supprimer" title="Supprimer" onClick={() => supprimer(e)}>
              <Icon name="trash" size={18} />
            </button>
          </div>
        ))}
        {level === 'complet' && (
          <button type="button" className="btn btn--secondary" onClick={() => setAjout(true)}>
            Ajouter une écriture
          </button>
        )}
      </div>
      {ajout && <AjoutEcriture season={season} onClose={() => setAjout(false)} onAjoutee={() => { setAjout(false); onChange() }} />}
    </div>
  )
}

// Une écriture à la main : date (dans la saison), libellé, compte débité,
// compte crédité (jamais la banque ni la caisse), montant positif.
function AjoutEcriture({ season, onClose, onAjoutee }) {
  const [plan, setPlan] = useState(null)
  const [form, setForm] = useState({ date: season.endDate, label: '', debitAccountId: '', creditAccountId: '', amount: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api
      .planComptable()
      .then(setPlan)
      .catch((err) => setErreur(err.message))
  }, [])
  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const comptes = (plan?.accounts ?? []).filter((c) => c.active && c.nature !== 'banque' && c.nature !== 'caisse')
  const pret = form.label.trim() && form.debitAccountId && form.creditAccountId && Number(form.amount) > 0

  async function enregistrer() {
    setErreur('')
    try {
      await api.ajouterEcriture(season.id, {
        date: form.date,
        label: form.label,
        debitAccountId: Number(form.debitAccountId),
        creditAccountId: Number(form.creditAccountId),
        amount: Number(form.amount),
      })
      onAjoutee()
    } catch (err) {
      setErreur(err.message)
    }
  }

  const selectCompte = (k) => (
    <select className="field-input" value={form[k]} onChange={champ(k)}>
      <option value="">Choisir un compte</option>
      {comptes.map((c) => (
        <option key={c.id} value={c.id}>
          {nomCompte(c)}
        </option>
      ))}
    </select>
  )

  return (
    <Modal
      title="Ajouter une écriture"
      onClose={onClose}
      footer={
        <div className="nf-boutons">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="button" className="btn btn--primary" disabled={!pret} onClick={enregistrer}>
            Ajouter
          </button>
        </div>
      }
    >
      <label className="field">
        <span className="field-label">Date</span>
        <input className="field-input" type="date" min={season.startDate} max={season.endDate} value={form.date} onChange={champ('date')} />
      </label>
      <label className="field">
        <span className="field-label">Libellé</span>
        <input className="field-input" value={form.label} onChange={champ('label')} placeholder="Cotisations 2025-2026 dues au 31 août" />
      </label>
      <label className="field">
        <span className="field-label">Compte débité</span>
        {selectCompte('debitAccountId')}
      </label>
      <label className="field">
        <span className="field-label">Compte crédité</span>
        {selectCompte('creditAccountId')}
      </label>
      <label className="field">
        <span className="field-label">Montant</span>
        <input className="field-input" type="number" step="0.01" min="0" inputMode="decimal" value={form.amount} onChange={champ('amount')} />
      </label>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Étape 6 : la comparaison avec la saison précédente, compte par compte. Un
// écart de plus de 30 % est marqué « ? » : la trésorière l'explique en une
// ligne (reprise dans le Rapport financier) ou retourne pointer.
function Etape6({ season, comparison, onDocuments, onChange, onErreur }) {
  const [brouillons, setBrouillons] = useState({})

  async function enregistrer(l) {
    const note = brouillons[l.number]
    if (note === undefined || note === l.note) return
    try {
      await api.expliquerCompte(season.id, l.number, note)
      setBrouillons((b) => {
        const { [l.number]: _retire, ...reste } = b
        return reste
      })
      onChange()
    } catch (err) {
      onErreur(err.message)
    }
  }

  const pct = (l) => (l.pct === null ? (l.previous === 0 ? 'nouveau' : 'disparu') : `${l.pct > 0 ? '+' : ''}${String(l.pct).replace('.', ',')} %`)
  const flagged = comparison.lines.filter((l) => l.flag)
  const autres = comparison.lines.filter((l) => !l.flag && (l.current || l.previous))

  return (
    <div className="fin-preparer__corps">
      {!comparison.previousSeason && <p className="muted">Première saison dans l’appli : rien à comparer.</p>}
      {comparison.previousSeason && (
        <>
          <div className="fin-preparer__bloc">
            <span className="fin-cp-t">À expliquer · {flagged.length}</span>
            <span className="fin-cp-s">Écart de plus de 30 % avec {comparison.previousSeason}, ou compte nouveau ou disparu. Une ligne suffit ; elle est reprise dans le Rapport financier.</span>
            {flagged.length === 0 && <span className="fin-cp-s">Aucun.</span>}
            {flagged.map((l) => (
              <div key={l.number} className="fin-preparer__comparaison">
                <span className="fin-preparer__libelle">
                  {l.number} {l.label}
                  {!l.note && <span className="badge badge--warning fin-preparer__reste">?</span>}
                </span>
                <span className="fin-preparer__montant">
                  {euros(l.current)} <span className="muted">({euros(l.previous)} · {pct(l)})</span>
                </span>
                <input
                  type="text"
                  className="field-input"
                  placeholder="Pourquoi ? (une ligne)"
                  value={brouillons[l.number] ?? l.note}
                  maxLength={300}
                  onChange={(e) => setBrouillons((b) => ({ ...b, [l.number]: e.target.value }))}
                  onBlur={() => enregistrer(l)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') e.currentTarget.blur()
                  }}
                />
              </div>
            ))}
          </div>
          <div className="fin-preparer__bloc">
            <span className="fin-cp-t">Les autres comptes · {autres.length}</span>
            {autres.map((l) => (
              <div key={l.number} className="fin-preparer__ligne fin-preparer__ligne--texte">
                <span className="fin-preparer__libelle">
                  {l.number} {l.label}
                </span>
                <span className="fin-preparer__montant">
                  {euros(l.current)} <span className="muted">({euros(l.previous)} · {pct(l)})</span>
                </span>
              </div>
            ))}
          </div>
          <div className="fin-preparer__bloc">
            <span className="fin-cp-s">
              Recettes {euros(comparison.totals.produits[0])} ({euros(comparison.totals.produits[1])}) · Dépenses {euros(comparison.totals.charges[0])} (
              {euros(comparison.totals.charges[1])}) · Résultat {euros(comparison.totals.result[0])} ({euros(comparison.totals.result[1])}).
            </span>
          </div>
        </>
      )}
      <button type="button" className="btn btn--primary" onClick={onDocuments}>
        Aller aux documents
      </button>
    </div>
  )
}
