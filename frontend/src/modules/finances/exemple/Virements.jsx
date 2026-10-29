// Puce Virements de Pièces (spec/modules/financier.md §8.3 bis), EXEMPLE :
// ce qui attend d'être payé, en quatre états, et l'aide au virement (copier
// chaque ligne dans l'appli de la banque, ou faire payer par quelqu'un).
// L'appli ne paie pas. Tout vit en mémoire (exemple/donnees.js).
import { useState } from 'react'
import { VIREMENTS, eur } from './donnees.js'

const ETATS = [
  { id: 'a_payer', label: 'À payer' },
  { id: 'prepare', label: 'Préparés, en attente d’envoi' },
  { id: 'envoye', label: 'Envoyés' },
  { id: 'paye', label: 'Payés' },
]
const BADGES = { prepare: 'Chez la trésorière adjointe', envoye: 'Pas encore vu', paye: 'Payé' }

export default function Virements() {
  const [virements, setVirements] = useState(VIREMENTS)
  const [ouverts, setOuverts] = useState({ a_payer: true })
  const [choisi, setChoisi] = useState(null)
  const [message, setMessage] = useState('')

  function changer(id, etat, texte) {
    setVirements((l) => l.map((v) => (v.id === id ? { ...v, etat } : v)))
    setOuverts((o) => ({ ...o, [etat]: true }))
    setChoisi(null)
    setMessage(texte)
  }

  const v = virements.find((x) => x.id === choisi)
  if (v) {
    return (
      <AideAuVirement
        virement={v}
        onRetour={() => setChoisi(null)}
        onFait={() => changer(v.id, 'envoye', 'Noté comme envoyé : il passera en Payés quand l’appli le verra sur le compte.')}
        onFairePayer={() => changer(v.id, 'prepare', 'Envoyé à la trésorière adjointe : elle reçoit une notification « Virement à faire ».')}
        onRib={() => setVirements((l) => l.map((x) => (x.id === v.id ? { ...x, rib: { titulaire: 'THEATRE GALLI', iban: 'FR76 1007 1690 0000 0020 0123 456', par: 'vous, à l’instant' } } : x)))}
      />
    )
  }

  return (
    <>
      <p className="muted">
        Les notes de frais validées et les notes d’honoraires arrivent ici toutes seules ; une facture, par « À payer
        par virement ». Un achat déjà payé (carte, prélèvement) n’y passe jamais.
      </p>
      {message && <p className="history-report">{message}</p>}
      {ETATS.map((e) => {
        const liste = virements.filter((x) => x.etat === e.id)
        if (liste.length === 0) return null
        const ouvert = !!ouverts[e.id]
        return (
          <div key={e.id} className="fin-ex-vir-partie">
            <button
              type="button"
              className="fin-ex-vir-titre"
              aria-expanded={ouvert}
              onClick={() => setOuverts((o) => ({ ...o, [e.id]: !ouvert }))}
            >
              <span>
                {e.label} <span className="muted">{liste.length}</span>
              </span>
              <span aria-hidden="true">{ouvert ? '▾' : '▸'}</span>
            </button>
            {ouvert &&
              liste.map((x) => (
                <button
                  key={x.id}
                  type="button"
                  className="fin-ex-carte fin-ex-vir-ligne"
                  onClick={() => x.etat !== 'paye' && setChoisi(x.id)}
                >
                  <span>
                    <b>{x.nom}</b>
                    <span className="muted">{x.objet}</span>
                  </span>
                  <span className="fin-ex-vir-droite">
                    <b>{eur(x.montant)}</b>
                    {BADGES[x.etat] && (
                      <span className={x.etat === 'paye' ? 'badge badge--success' : 'badge badge--warning'}>{BADGES[x.etat]}</span>
                    )}
                  </span>
                </button>
              ))}
          </div>
        )
      })}
    </>
  )
}

function AideAuVirement({ virement: v, onRetour, onFait, onFairePayer, onRib }) {
  return (
    <>
      <button type="button" className="btn btn--link fin-ex-vir-retour" onClick={onRetour}>
        ← Virements
      </button>
      <h3 className="fin-ex-vir-h">Virement à faire</h3>
      {v.rib ? (
        <>
          <p>Dans l’appli de la banque, Virement, recopiez :</p>
          <Copier label="Bénéficiaire" valeur={v.rib.titulaire} />
          <Copier label="IBAN" valeur={v.rib.iban} />
          <Copier label="Montant" valeur={eur(v.montant).replace(/\s?€/, '')} />
          <Copier label="Libellé" valeur={v.libelle} />
        </>
      ) : (
        <div className="fin-ex-carte fin-ex-vir-copier">
          <span>
            <span className="muted">RIB de {v.nom}</span>
            <b>Pas encore de RIB</b>
          </span>
          <button type="button" className="btn btn--secondary" onClick={onRib}>
            Photographier
          </button>
        </div>
      )}
      <p className="muted">
        Depuis le {v.compte} · pièce : {v.piece}
        {v.rib && ` · RIB enregistré par ${v.rib.par}`}. La première fois, la banque demande d’ajouter le bénéficiaire.
      </p>
      <div className="fin-ex-boutons fin-ex-vir-boutons">
        <button type="button" className="btn btn--primary" disabled={!v.rib} onClick={onFait}>
          J’ai fait le virement
        </button>
        {v.etat === 'a_payer' && (
          <button type="button" className="btn btn--secondary" disabled={!v.rib} onClick={onFairePayer}>
            Faire payer par la trésorière adjointe
          </button>
        )}
      </div>
    </>
  )
}

function Copier({ label, valeur }) {
  const [copie, setCopie] = useState(false)
  async function copier() {
    try {
      await navigator.clipboard.writeText(valeur)
    } catch {
      // Presse-papier refusé : la valeur reste sélectionnable à l'écran.
    }
    setCopie(true)
  }
  return (
    <div className="fin-ex-carte fin-ex-vir-copier">
      <span>
        <span className="muted">{label}</span>
        <b>{valeur}</b>
      </span>
      <button type="button" className={copie ? 'btn btn--secondary fin-ex-vir-copie' : 'btn btn--secondary'} onClick={copier}>
        {copie ? 'Copié' : 'Copier'}
      </button>
    </div>
  )
}
