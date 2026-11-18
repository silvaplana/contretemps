import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import Modal from '../../components/Modal.jsx'
import * as api from './api.js'

// ⋮ > Statistiques des adhérents de la saison (spec/modules/helloasso.md
// §7.8, maquette « Adhérents ASC ») : chiffres de la saison, encaissements,
// soldes et projection (ces deux-là avec l'Accès au Financier).

const euros = (n) => `${Number(n || 0).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} €`
const jour = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
const date = (iso) => `${jour(iso)}/${iso.slice(0, 4)}`
const mois = (aaaamm) =>
  new Date(`${aaaamm}-01T12:00:00`).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })
const finDe = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { month: 'long' })
const pluriel = (n, mot) => `${n} ${mot}${n > 1 ? 's' : ''}`

function Ligne({ libelle, montant }) {
  return (
    <div className="stats__ligne">
      <span>{libelle}</span>
      <b>{montant}</b>
    </div>
  )
}

function Depliable({ titre, total, children }) {
  return (
    <details className="stats__depliable">
      <summary>
        <span>{titre}</span>
        <b>{total}</b>
      </summary>
      <div className="stats__detail">{children}</div>
    </details>
  )
}

function Salaires({ payroll, fin }) {
  if (!payroll || !payroll.total) return null
  const base = payroll.regular ? 'montant des 3 derniers mois' : 'moyenne des derniers mois'
  const detail = payroll.months ? ` (${payroll.months} mois × ${euros(payroll.monthly)}, ${base})` : ''
  return <Ligne libelle={`− Salaires et cotisations jusqu’à fin ${finDe(fin)}${detail}`} montant={euros(payroll.total)} />
}

function Contenu({ s }) {
  const c = s.cash
  return (
    <>
      <div className="stats__chiffres">
        <div>
          <span>Majeurs</span>
          <b>{s.adults}</b>
        </div>
        <div>
          <span>Mineurs</span>
          <b>{s.minors}</b>
        </div>
        <div>
          <span>Prix moyen</span>
          <b>{s.average_price == null ? '—' : euros(Math.round(s.average_price))}</b>
        </div>
      </div>
      <p className="muted">
        {pluriel(s.members, 'adhérent')}, {euros(s.total_price)} au total (résiliées non comptées).
      </p>

      {s.accounts && (
        <>
          <h3 className="stats__titre">Solde actuel</h3>
          {s.accounts.map((a) => (
            <Ligne key={a.name} libelle={a.as_of ? `${a.name}, au ${date(a.as_of)}` : a.name} montant={euros(a.balance)} />
          ))}
        </>
      )}

      <h3 className="stats__titre">Encaissements des adhésions</h3>
      <Depliable titre="Déjà arrivé sur le compte courant" total={euros(c.on_account_total)}>
        {c.on_account.length === 0 && <p className="muted">Rien pour l’instant.</p>}
        {c.on_account.map((r) => (
          <Ligne
            key={r.requested}
            libelle={`Reçu le ${jour(r.date)}${r.requested !== r.date ? ` (versement HelloAsso du ${jour(r.requested)})` : ''}, ${pluriel(r.payments, 'paiement')}`}
            montant={euros(r.amount)}
          />
        ))}
      </Depliable>
      <Depliable titre="Reste à encaisser" total={euros(c.to_receive)}>
        <Ligne libelle="Versement en cours HelloAsso → compte courant" montant={c.in_transit ? euros(c.in_transit) : 'Aucun'} />
        <Ligne libelle="Payé sur HelloAsso, versé vers le 10 du mois prochain" montant={c.held ? euros(c.held) : 'Aucun'} />
        {c.upcoming.map((e) => (
          <Ligne key={e.month} libelle={`Échéances de ${mois(e.month)}`} montant={euros(e.amount)} />
        ))}
      </Depliable>

      {s.projected != null && (
        <>
          <h3 className="stats__titre">Projection de fin de saison</h3>
          <Depliable titre={`Solde projeté au ${date(s.season_end)}`} total={euros(s.projected)}>
            <Ligne libelle="Solde actuel" montant={euros(s.balance)} />
            <Ligne libelle="+ Reste à encaisser" montant={euros(c.to_receive)} />
            <Salaires payroll={s.payroll} fin={s.season_end} />
            {s.licences && (
              <Ligne
                libelle={`− Licences FFST encore à payer (${s.licences.count} × ${euros(s.licences.price)})`}
                montant={euros(s.licences.count * s.licences.price)}
              />
            )}
            <p className="muted">
              Chiffre optimiste : il ne compte ni les autres dépenses (matériel, frais bancaires…), ni les adhésions qui
              peuvent encore arriver.
            </p>
          </Depliable>
        </>
      )}
      <p className="muted">
        Les soldes et la projection ne se voient qu’avec l’Accès au Financier ; ils viennent des comptes du Financier.
      </p>
    </>
  )
}

function StatistiquesModal({ ecoleId, onClose }) {
  const [stats, setStats] = useState(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api
      .statistiques(ecoleId)
      .then(setStats)
      .catch((e) => setErreur(e.message))
  }, [ecoleId])
  return (
    <Modal
      title={stats ? `Statistiques de la saison ${stats.season}` : 'Statistiques de la saison'}
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--primary" onClick={onClose}>
            Fermer
          </button>
        </div>
      }
    >
      {stats && <Contenu s={stats} />}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// L'écran s'ouvre hors du tableau, comme « Vérifier les adhérents ».
export function ouvrirStatistiques(ecoleId) {
  const hote = document.createElement('div')
  document.body.appendChild(hote)
  const racine = createRoot(hote)
  const fermer = () => {
    racine.unmount()
    hote.remove()
  }
  racine.render(<StatistiquesModal ecoleId={ecoleId} onClose={fermer} />)
}
