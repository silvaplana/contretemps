// Bilan › Préparer (spec/modules/financier.md §8.10, Seb 9/11) : les six
// étapes du bilan d'une saison, dans l'ordre, chacune avec ce qui reste à
// faire. Rien ne se calcule sans que la trésorière l'ait vu. Un numéro de
// compte ne s'affiche jamais seul : toujours avec son libellé.
import { useCallback, useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import * as sessionApi from '../../../api/session.js'
import * as nfApi from '../../../api/notesFrais.js'
import { requestSousOnglet } from '../navigation.js'
import RelevesGrille from '../RelevesGrille.jsx'
import SoldesDepart from './SoldesDepart.jsx'
import FicheOperation from './FicheOperation.jsx'
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

  const { statements, opening, classify, controls } = etat
  const aRapprocher = rapprocher ? rapprocher.paires.length + rapprocher.sans_paiement.filter((p) => p.a_rapprocher).length : 0
  const resteEtape3 = aRapprocher + classify.withoutAccount
  const controlesKo = controls.filter((c) => !c.ok).length
  const etapes = [
    { n: 1, titre: 'Relevés complets', reste: statements.missing, detail: statements.ok ? `${statements.accounts} compte(s), tous les mois sont là` : `${statements.missing} mois à importer` },
    { n: 2, titre: 'Soldes de départ', reste: opening.mismatches, detail: opening.ok ? SOURCES[opening.source] : `${opening.mismatches} compte(s) en écart avec les relevés` },
    { n: 3, titre: 'Rapprocher et classer', reste: resteEtape3, detail: resteEtape3 === 0 ? 'Chaque transaction bancaire a sa pièce ou son compte' : `${aRapprocher} à rapprocher, ${classify.withoutAccount} sans compte` },
    { n: 4, titre: 'Hors banque', reste: 0, detail: 'Caisse, factures non payées, cotisations dues : bientôt' },
    { n: 5, titre: 'Contrôles', reste: controlesKo, detail: controlesKo === 0 ? 'Tout est vert' : `${controlesKo} contrôle(s) en rouge` },
    { n: 6, titre: 'Documents', reste: 0, detail: controlesKo === 0 ? 'Prêts à produire' : 'Après les contrôles' },
  ]

  return (
    <div className="fin-cp fin-preparer">
      {etat.closed && <p className="muted">Saison clôturée : rouvrez-la (Clôture) pour changer quelque chose.</p>}
      <div className="fin-cp-carte">
        {etapes.map((e) => (
          <div key={e.n} className={`fin-cp-doc fin-cp-doc--large fin-preparer__etape${ouverte === e.n ? ' fin-preparer__etape--ouverte' : ''}`}>
            <button type="button" className="fin-preparer__tete" onClick={() => (e.n === 6 ? onDocuments() : setOuverte(ouverte === e.n ? null : e.n))}>
              <span className={`fin-preparer__num${e.reste === 0 ? ' fin-preparer__num--ok' : ''}`}>{e.reste === 0 ? <Icon name="check" size={16} /> : e.n}</span>
              <span className="fin-cp-t">
                {e.n}. {e.titre}
                {e.reste > 0 && <span className="badge badge--warning fin-preparer__reste">{e.reste}</span>}
              </span>
              <span className="fin-cp-s">{e.detail}</span>
            </button>
            {ouverte === 1 && e.n === 1 && <RelevesGrille onClose={() => setOuverte(null)} onImport={charger} />}
            {ouverte === 2 && e.n === 2 && <SoldesDepart onClose={() => setOuverte(null)} />}
            {ouverte === 3 && e.n === 3 && (
              <Etape3 rapprocher={rapprocher} aRapprocher={aRapprocher} classify={classify} enCours={enCours} onRapprocher={ouvrirRapprocher} onValider={validerCompte} onFiche={setFicheOp} />
            )}
            {ouverte === 4 && e.n === 4 && (
              <p className="muted">
                La caisse se tient dans Comptes › Caisse. Les factures non payées au dernier jour de la saison, les cotisations dues et le compte
                d’attente viendront ici dans une prochaine étape.
              </p>
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
        <span className="fin-cp-t">Rapprocher</span>
        <span className="fin-cp-s">
          {rapprocher
            ? `${rapprocher.paires.length} suggestion(s) de rattachement, ${rapprocher.sans_paiement.filter((p) => p.a_rapprocher).length} facture(s) à rapprocher, ${rapprocher.lignes_sans_piece.length} transaction(s) bancaire(s) sans facture`
            : 'Le rapprochement des pièces n’est pas disponible.'}
        </span>
        <button type="button" className={`btn ${aRapprocher > 0 ? 'btn--primary' : 'btn--secondary'}`} onClick={onRapprocher}>
          Ouvrir Rapprocher
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
            <span className="fin-cp-proposition fin-cp-proposition--aucune">Compte ? {o.piece ? 'la pièce aide' : 'pas de pièce'}</span>
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
