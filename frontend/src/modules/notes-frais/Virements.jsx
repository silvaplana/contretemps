import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import { BadgeEtat, ChampsRib, PaiementVu, qui, ribVide } from './commun.jsx'
import { DemanderRib } from './Exterieurs.jsx'

// Puce Virements de Financier › Pièces (spec/modules/financier.md §8.3 bis) :
// ce qui attend d'être payé, en quatre états, et l'aide au virement (copier
// chaque ligne dans l'appli de la banque, ou faire payer par quelqu'un).
// L'appli ne paie pas.
const ETATS = [
  { id: 'validee', label: 'À payer' },
  { id: 'preparee', label: 'Préparés, en attente d’envoi' },
  { id: 'viree', label: 'Envoyés' },
  { id: 'remboursee', label: 'Payés' },
]

const GUIDE_VU = 'nf-guide-virement-vu'

function guideDejaVu() {
  try {
    return localStorage.getItem(GUIDE_VU) === '1'
  } catch {
    return true
  }
}

export default function Virements({ onChange }) {
  const [donnees, setDonnees] = useState(null)
  const [ouverts, setOuverts] = useState({ validee: true })
  const [choisi, setChoisi] = useState(null)
  const [message, setMessage] = useState('')
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api
      .virements()
      .then((d) => {
        setDonnees(d)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
  }, [])
  useEffect(charger, [charger])

  async function agir(action, etat, texte) {
    setErreur('')
    try {
      await action()
      setOuverts((o) => ({ ...o, [etat]: true }))
      setChoisi(null)
      setMessage(texte)
      charger()
      onChange()
    } catch (err) {
      setErreur(err.message)
    }
  }

  const v = donnees?.virements.find((x) => x.id === choisi)
  if (v) {
    const autres = donnees.payeurs.filter((p) => p.person_id !== donnees.moi)
    return (
      <AideAuVirement
        virement={v}
        payeurs={autres}
        erreur={erreur}
        onErreur={setErreur}
        onRetour={() => setChoisi(null)}
        onRib={async (rib) => {
          setErreur('')
          try {
            await api.ribNote(v.id, rib)
            charger()
          } catch (err) {
            setErreur(err.message)
          }
        }}
        onPaye={(op) => agir(() => api.payee(v.id, op.id), 'remboursee', 'Payé : la pièce est rattachée à l’opération du compte.')}
        onFait={() =>
          agir(() => api.virementFait(v.id), 'viree', 'Noté comme envoyé : il passera en Payés quand l’appli le verra sur le compte.')
        }
        onFairePayer={(p) =>
          agir(() => api.preparer(v.id, p.person_id), 'preparee', `Notification « Virement à faire » envoyée à ${p.nom}.`)
        }
        onRevenir={() => agir(() => api.revenir(v.id), 'validee', 'De retour en À payer.')}
      />
    )
  }

  return (
    <>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!donnees && !erreur && <p className="muted">Chargement…</p>}
      {donnees && donnees.virements.length === 0 && (
        <p className="muted">Rien à payer. Les notes de frais et les honoraires validés arrivent ici tout seuls.</p>
      )}
      {message && <p className="history-report">{message}</p>}
      {ETATS.map((e) => {
        const liste = (donnees?.virements ?? []).filter((x) => x.statut === e.id)
        if (liste.length === 0) return null
        const ouvert = !!ouverts[e.id]
        return (
          <div key={e.id} className="nf-vir-partie">
            <button
              type="button"
              className="nf-vir-titre"
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
                  className="nf-ligne"
                  onClick={() => x.statut !== 'remboursee' && setChoisi(x.id)}
                >
                  <span className="nf-ligne__corps">
                    <span className="nf-ligne__titre">{qui(x)}</span>
                    <span className="muted">
                      {x.nature === 'achat' ? x.depenses[0]?.description || 'Facture' : x.titre}
                      {x.statut === 'preparee' && x.payeur ? ` · chez ${x.payeur.nom}` : ''}
                      {x.statut !== 'remboursee' && !x.rib ? ' · RIB à demander' : ''}
                      {x.paiement_propose ? ' · vu sur le compte' : ''}
                    </span>
                  </span>
                  <span className="nf-ligne__droite">
                    <span className="nf-ligne__montant">{api.euros(x.total_centimes)}</span>
                    <BadgeEtat note={x} />
                  </span>
                </button>
              ))}
          </div>
        )
      })}
    </>
  )
}

function AideAuVirement({ virement: v, payeurs, erreur, onErreur, onRetour, onRib, onPaye, onFait, onFairePayer, onRevenir }) {
  const [rib, setRib] = useState(() => ribVide(v.rib))
  const [changerRib, setChangerRib] = useState(!v.rib)
  const [guide, setGuide] = useState(() => !guideDejaVu())
  useEffect(() => {
    try {
      localStorage.setItem(GUIDE_VU, '1')
    } catch {
      // Pas retenu : le guide se remontrera.
    }
  }, [])

  return (
    <div className="nf-vir-aide">
      <button type="button" className="btn btn--link nf-retour" onClick={onRetour}>
        ← Virements
      </button>
      <h3 className="nf-vir-h">{v.statut === 'viree' ? 'Virement envoyé' : 'Virement à faire'}</h3>
      {v.statut === 'viree' && (
        <p className="muted">
          Envoyé le {api.dateCourte(v.vire_le)} : il passe en Payés quand l’appli le voit sur le compte, après la
          lecture de la banque ou l’import du relevé.
        </p>
      )}
      <PaiementVu note={v} onConfirme={onPaye} />
      {(v.statut === 'viree' || v.statut === 'preparee') && (
        <button type="button" className="btn btn--link" onClick={onRevenir}>
          Revenir en arrière : À payer
        </button>
      )}
      {v.statut === 'preparee' && v.prepare_par && (
        <p className="muted">
          Préparé par {v.prepare_par.nom} le {api.dateCourte(v.prepare_le)}
          {v.payeur ? `, pour ${v.payeur.nom}` : ''}.
        </p>
      )}
      {changerRib ? (
        <>
          <p>RIB de {qui(v)} :</p>
          <ChampsRib rib={rib} onChange={setRib} />
          {v.personne?.role === 'extérieur' && !v.rib && (
            <DemanderRib onDemander={() => api.demanderRib(-v.personne.person_id)} onErreur={onErreur} />
          )}
          <button
            type="button"
            className="btn btn--primary"
            disabled={!rib.iban.trim()}
            onClick={async () => {
              await onRib(rib)
              setChangerRib(false)
            }}
          >
            Enregistrer le RIB
          </button>
        </>
      ) : (
        <>
          <p>Dans l’appli de la banque, Virement, recopiez :</p>
          <Copier label="Bénéficiaire" valeur={v.beneficiaire} />
          <Copier label="IBAN" valeur={v.rib.iban} affiche={v.rib.iban.replace(/(.{4})/g, '$1 ').trim()} />
          <Copier label="Montant" valeur={api.versTexteMontant(v.total_centimes)} />
          <Copier label="Libellé" valeur={v.libelle_virement} />
          <button type="button" className="btn btn--link nf-retour" onClick={() => setChangerRib(true)}>
            Changer le RIB
          </button>
        </>
      )}
      <button type="button" className="btn btn--link nf-retour" onClick={() => setGuide((g) => !g)}>
        Comment faire
      </button>
      {guide && (
        <ol className="nf-vir-guide">
          <li>Ouvrez l’appli CIC, Virements, Nouveau virement.</li>
          <li>Choisissez le compte à débiter, puis le bénéficiaire. La première fois, ajoutez-le : collez son nom et son IBAN.</li>
          <li>Collez le montant, puis le libellé.</li>
          <li>Validez avec Confirmation Mobile, puis revenez ici : « J’ai fait le virement ».</li>
        </ol>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <div className="nf-vir-boutons" hidden={v.statut === 'viree'}>
        <button type="button" className="btn btn--primary" disabled={!v.rib || changerRib} onClick={onFait}>
          J’ai fait le virement
        </button>
        {payeurs.map((p) => (
          <button
            key={p.person_id}
            type="button"
            className="btn btn--secondary"
            disabled={!v.rib || changerRib}
            onClick={() => onFairePayer(p)}
          >
            Faire payer par {p.nom}
          </button>
        ))}
      </div>
    </div>
  )
}

function Copier({ label, valeur, affiche = valeur }) {
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
    <div className="nf-ligne nf-vir-copier">
      <span className="nf-ligne__corps">
        <span className="muted">{label}</span>
        <span className="nf-vir-valeur">{affiche}</span>
      </span>
      <button type="button" className={copie ? 'btn btn--secondary nf-vir-copie' : 'btn btn--secondary'} onClick={copier}>
        {copie ? 'Copié' : 'Copier'}
      </button>
    </div>
  )
}
