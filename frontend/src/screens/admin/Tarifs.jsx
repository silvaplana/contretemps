import { useEffect, useRef, useState } from 'react'
import * as tarifsApi from '../../api/tarifs.js'
import Icon from '../../components/Icon.jsx'

// Tarifs de la saison (spec/core.md §9, maquette « Tarifs de la saison ») :
// Admin > École > Tarifs. Une formule = un nom, un tarif, une ou plusieurs
// échéances (date et montant, la somme fait le tarif). Chaque OK enregistre.

const ANNULER_MS = 10000

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 2 })
const prix = (centimes) => (centimes === 0 ? 'Gratuit' : euros(centimes))
const enCentimes = (texte) => Math.round((Number(String(texte).replace(',', '.')) || 0) * 100)

function resumeEcheances(formule) {
  const e = formule.installments
  return e.length <= 1 ? 'En 1 fois' : `${e.length} échéances : ${e.map((x) => euros(x.amount)).join(' + ')}`
}

// Le tarif réparti en parts égales, la dernière prend l'arrondi.
function repartir(tarif, echeances) {
  const n = echeances.length
  const part = Math.round(tarif / n)
  return echeances.map((e, i) => ({ ...e, amount: i === n - 1 ? tarif - part * (n - 1) : part }))
}

// Date proposée pour une nouvelle échéance : trois mois après la dernière.
function dateSuivante(echeances) {
  const derniere = [...echeances].reverse().find((e) => e.due_on)?.due_on
  const d = derniere ? new Date(`${derniere}T12:00:00`) : new Date()
  d.setMonth(d.getMonth() + 3)
  if (!derniere) d.setDate(15)
  return d.toISOString().slice(0, 10)
}

function Formule({ formule, onNom, onOk, onDupliquer, onRetirer }) {
  const [nom, setNom] = useState(formule.name)
  const [tarif, setTarif] = useState(formule.price / 100)
  const [echeances, setEcheances] = useState(formule.installments)
  const [proposee, setProposee] = useState(formule.active)
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const centimes = enCentimes(tarif)
  const somme = echeances.reduce((a, e) => a + e.amount, 0)
  const juste = somme === centimes

  function changerTarif(valeur) {
    setTarif(valeur)
    setEcheances((e) => repartir(enCentimes(valeur), e))
  }

  async function valider() {
    if (!nom.trim() || !juste) return
    setErreur(null)
    setEnCours(true)
    try {
      await onOk({ name: nom.trim(), price: centimes, active: proposee, installments: echeances })
    } catch (e) {
      setErreur(e.message)
      setEnCours(false)
    }
  }

  return (
    <>
      <div className="form-fields">
        <label htmlFor="formule-nom">Nom</label>
        <input
          id="formule-nom"
          className="field-input"
          value={nom}
          placeholder="ex. Adulte, en 3 fois"
          onChange={(e) => {
            setNom(e.target.value)
            onNom(e.target.value)
          }}
        />
        <label htmlFor="formule-tarif">Tarif</label>
        <div className="tarifs__montant">
          <input
            id="formule-tarif"
            className="field-input"
            type="number"
            min="0"
            step="0.5"
            inputMode="decimal"
            value={tarif}
            onChange={(e) => changerTarif(e.target.value)}
          />
          <span>€</span>
        </div>
        <label>Échéances</label>
      </div>
      {echeances.map((e, j) => (
        <div key={j} className="tarifs__echeance">
          {e.due_on === null ? (
            <input className="field-input" value="À l’inscription" readOnly aria-label={`Date de l’échéance ${j + 1}`} />
          ) : (
            <input
              className="field-input"
              type="date"
              value={e.due_on}
              aria-label={`Date de l’échéance ${j + 1}`}
              onChange={(ev) =>
                setEcheances((l) => l.map((x, k) => (k === j ? { ...x, due_on: ev.target.value || x.due_on } : x)))
              }
            />
          )}
          <div className="tarifs__montant">
            <input
              className="field-input"
              type="number"
              min="0"
              step="0.5"
              inputMode="decimal"
              value={e.amount / 100}
              aria-label={`Montant de l’échéance ${j + 1}`}
              onChange={(ev) =>
                setEcheances((l) => l.map((x, k) => (k === j ? { ...x, amount: enCentimes(ev.target.value) } : x)))
              }
            />
            <span>€</span>
            {echeances.length > 1 && (
              <button
                type="button"
                className="icon-btn"
                aria-label={`Retirer l’échéance ${j + 1}`}
                onClick={() => setEcheances((l) => repartir(centimes, l.filter((_, k) => k !== j)))}
              >
                <Icon name="x" size={20} />
              </button>
            )}
          </div>
        </div>
      ))}
      <button
        type="button"
        className="creer-saison__lien"
        onClick={() => setEcheances((l) => repartir(centimes, [...l, { due_on: dateSuivante(l), amount: 0 }]))}
      >
        + Ajouter une échéance
      </button>
      {!juste && (
        <p className="tarifs__ecart">
          Les échéances font {euros(somme)}, le tarif {euros(centimes)}.
        </p>
      )}
      {juste && echeances.length > 1 && (
        <p className="creer-saison__note">
          {echeances.length} × {euros(echeances[0].amount)}
          {echeances.some((x) => x.amount !== echeances[0].amount) ? ' environ' : ''}
          {echeances[0].due_on === null ? ', la première à l’inscription.' : '.'}
        </p>
      )}
      <label className="champs__case">
        <input type="checkbox" checked={proposee} onChange={(e) => setProposee(e.target.checked)} />
        <span>Proposée cette saison</span>
      </label>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button
        type="button"
        className="btn btn--primary btn--block creer-saison__principal"
        disabled={enCours || !nom.trim() || !juste}
        onClick={valider}
      >
        OK
      </button>
      {formule.id && (
        <>
          <button type="button" className="creer-saison__lien" onClick={onDupliquer}>
            Dupliquer cette formule
          </button>
          <button type="button" className="creer-saison__lien" onClick={onRetirer}>
            Retirer cette formule
          </button>
        </>
      )}
    </>
  )
}

export default function Tarifs({ ecoleId, onClose }) {
  const [donnees, setDonnees] = useState(null)
  const [ouverte, setOuverte] = useState(null) // formule ouverte (id absent = nouvelle)
  const [nomOuverte, setNomOuverte] = useState('') // le titre suit le nom tapé
  const [erreur, setErreur] = useState(null)
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  async function relire() {
    try {
      setDonnees(await tarifsApi.lister(ecoleId))
    } catch (e) {
      setErreur(e.message)
    }
  }

  useEffect(() => {
    relire()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  function montrerToast(texte, annuler) {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

  async function reprendre() {
    try {
      const repris = await tarifsApi.reprendre(ecoleId)
      await relire()
      montrerToast(`Tarifs de ${donnees.previous.name} repris`, async () => {
        await Promise.all(repris.map((f) => tarifsApi.retirer(f.id)))
        await relire()
      })
    } catch (e) {
      setErreur(e.message)
    }
  }

  async function enregistrer(formule) {
    if (ouverte.id) await tarifsApi.modifier(ouverte.id, formule)
    else await tarifsApi.creer(ecoleId, formule)
    setOuverte(null)
    await relire()
  }

  async function dupliquer() {
    try {
      const copie = await tarifsApi.dupliquer(ouverte.id)
      await relire()
      ouvrir(copie)
      montrerToast('Formule dupliquée')
    } catch (e) {
      setErreur(e.message)
    }
  }

  async function retirer() {
    const formule = ouverte
    try {
      await tarifsApi.retirer(formule.id)
      setOuverte(null)
      await relire()
      montrerToast(`« ${formule.name} » retirée`, async () => {
        const { name, price, active, position, installments } = formule
        await tarifsApi.creer(ecoleId, { name, price, active, position, installments })
        await relire()
      })
    } catch (e) {
      setErreur(e.message)
    }
  }

  function ouvrir(formule) {
    setOuverte(formule)
    setNomOuverte(formule?.name ?? '')
  }

  const lectureSeule = donnees?.read_only
  let titre = `Tarifs ${donnees?.season ?? ''}`.trim()
  let retour = onClose
  let corps = null
  if (ouverte) {
    titre = nomOuverte || 'Nouvelle formule'
    retour = () => setOuverte(null)
    corps = (
      <Formule
        key={ouverte.id ?? 'nouvelle'}
        formule={ouverte}
        onNom={setNomOuverte}
        onOk={enregistrer}
        onDupliquer={dupliquer}
        onRetirer={retirer}
      />
    )
  } else if (donnees) {
    corps = (
      <>
        {donnees.previous && !lectureSeule && (
          <div className="creer-saison__cadre">
            <strong>Repartir des tarifs de {donnees.previous.name} ?</strong>
            <p className="creer-saison__note">
              {donnees.previous.plans} formule{donnees.previous.plans > 1 ? 's' : ''}, que vous pourrez modifier.
            </p>
            <button type="button" className="btn btn--secondary btn--block tarifs__secondaire" onClick={reprendre}>
              Reprendre ceux de {donnees.previous.name}
            </button>
          </div>
        )}
        <div className="creer-saison__partie">Formules</div>
        {donnees.plans.length === 0 && <p className="creer-saison__note">Aucune.</p>}
        {donnees.plans.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`tarifs__ligne${f.active ? '' : ' tarifs__ligne--off'}`}
            disabled={lectureSeule}
            onClick={() => ouvrir(f)}
          >
            <span className="tarifs__nom">
              {f.name}
              <small>{resumeEcheances(f)}</small>
            </span>
            <span className="tarifs__prix">{prix(f.price)}</span>
            {!lectureSeule && <Icon name="chevronRight" size={18} />}
          </button>
        ))}
        {!lectureSeule && (
          <>
            <button
              type="button"
              className="btn btn--secondary btn--block tarifs__secondaire"
              onClick={() => ouvrir({ name: '', price: 0, active: true, installments: [{ due_on: null, amount: 0 }] })}
            >
              + Ajouter une formule
            </button>
            <button type="button" className="btn btn--primary btn--block creer-saison__principal" onClick={onClose}>
              Valider les tarifs
            </button>
          </>
        )}
      </>
    )
  }

  return (
    <div className="creer-saison" role="dialog" aria-label={titre}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={retour} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{titre}</h2>
      </div>
      <div className="creer-saison__corps">
        {erreur && !ouverte && <p className="login-screen__erreur">{erreur}</p>}
        {corps}
      </div>
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          {toast.annuler && (
            <button
              type="button"
              onClick={() => {
                clearTimeout(minuteur.current)
                setToast(null)
                toast.annuler().catch((e) => setErreur(e.message))
              }}
            >
              Annuler
            </button>
          )}
        </div>
      )}
    </div>
  )
}
