import { useEffect, useRef, useState } from 'react'
import * as tarifsApi from '../../api/tarifs.js'
import Icon from '../../components/Icon.jsx'

// Tarifs de la saison (spec/core.md §9, maquette « Tarifs de la saison ») :
// Admin > École > Tarifs. Une formule = un nom, un tarif, une ou plusieurs
// échéances (date et montant, la somme fait le tarif). Puis une seule liste
// « Options et codes promo » : en plus ou en moins, en € ou en %, obtenu en
// cochant, avec un code (montré ou secret) ou par une règle écrite en
// français, que l'assistant écrit en calcul. Chaque OK enregistre.

const ANNULER_MS = 10000

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 2 })
const prix = (centimes) => (centimes === 0 ? 'Gratuit' : euros(centimes))
const enCentimes = (texte) => Math.round((Number(String(texte).replace(',', '.')) || 0) * 100)

const dateCourte = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR')

// « +15 € », « −10 % » (montant en centimes ou en centièmes de %).
const montantOption = (o) =>
  o.mode === 'rule'
    ? 'Calculé'
    : `${o.amount > 0 ? '+' : '−'}${(Math.abs(o.amount) / 100).toLocaleString('fr-FR')} ${o.unit === 'pct' ? '%' : '€'}`

function resumeOption(o, formules) {
  const morceaux = [o.mode === 'check' ? 'À cocher' : o.mode === 'rule' ? o.rule : null]
  const seule = o.plan_ids.length === 1 && formules.find((f) => f.id === o.plan_ids[0])
  if (seule) morceaux.push(seule.name)
  if (o.until) morceaux.push(`jusqu’au ${dateCourte(o.until)}`)
  if (o.quantity) morceaux.push(`${o.quantity} max`)
  if (o.max_uses) morceaux.push(`${o.max_uses} max`)
  const suite = morceaux.filter(Boolean).join(' · ')
  if (o.mode !== 'code') return suite
  return (
    <>
      Code <b className="tarifs__code">{o.code}</b> · {o.shown ? 'montré' : 'secret'}
      {suite && ` · ${suite}`}
    </>
  )
}

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

function Segments({ nom, choix, valeur, onChange }) {
  return (
    <div className="champs__seg" role="group" aria-label={nom}>
      {choix.map(([v, libelle]) => (
        <button key={v} type="button" aria-pressed={valeur === v} onClick={() => onChange(v)}>
          {libelle}
        </button>
      ))}
    </div>
  )
}

function Option({ option, formules, onNom, onOk, onRetirer, onComprendre }) {
  const [nom, setNom] = useState(option.name)
  const [mode, setMode] = useState(option.mode)
  const [signe, setSigne] = useState(option.amount > 0 ? 1 : -1)
  const [valeur, setValeur] = useState(Math.abs(option.amount) / 100)
  const [unite, setUnite] = useState(option.unit)
  const [code, setCode] = useState(option.code ?? '')
  const [montre, setMontre] = useState(option.shown)
  const [utilisations, setUtilisations] = useState(option.max_uses ?? '')
  const [jusquau, setJusquau] = useState(option.until ?? '')
  const [quantite, setQuantite] = useState(option.quantity ?? '')
  const [formule, setFormule] = useState(option.plan_ids.length === 1 ? String(option.plan_ids[0]) : '')
  const [proposee, setProposee] = useState(option.active)
  const [regle, setRegle] = useState(option.rule ?? '')
  // Ce que l'assistant a compris de la règle : { understood, calculation, example }.
  const [compris, setCompris] = useState(
    option.calculation ? { understood: option.understood, calculation: option.calculation, example: null } : null,
  )
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const pret = nom.trim() && (mode !== 'rule' || compris?.calculation)
  const nombre = (texte) => (texte === '' ? null : Math.max(1, Math.round(Number(texte))))

  function changerMode(m) {
    setMode(m)
    if (m === 'check') setSigne(1)
  }

  async function comprendre() {
    setErreur(null)
    setEnCours(true)
    try {
      setCompris(await onComprendre({ rule: regle.trim(), plan_ids: formule ? [Number(formule)] : [] }))
    } catch (e) {
      setErreur(e.message)
    }
    setEnCours(false)
  }

  async function valider() {
    if (!pret) return
    setErreur(null)
    setEnCours(true)
    try {
      await onOk({
        name: nom.trim(),
        amount: signe * enCentimes(valeur),
        unit: unite,
        mode,
        code: mode === 'code' ? code.trim().toUpperCase() : null,
        shown: montre,
        max_uses: mode === 'code' ? nombre(utilisations) : null,
        until: mode === 'code' && jusquau ? jusquau : null,
        quantity: mode === 'check' ? nombre(quantite) : null,
        plan_ids: formule ? [Number(formule)] : [],
        rule: mode === 'rule' ? regle.trim() : null,
        understood: mode === 'rule' ? compris.understood : null,
        calculation: mode === 'rule' ? compris.calculation : null,
        active: proposee,
      })
    } catch (e) {
      setErreur(e.message)
      setEnCours(false)
    }
  }

  return (
    <>
      <div className="form-fields">
        <label htmlFor="option-nom">Nom</label>
        <input
          id="option-nom"
          className="field-input"
          value={nom}
          placeholder="ex. T-shirt, Bienvenue"
          onChange={(e) => {
            setNom(e.target.value)
            onNom(e.target.value)
          }}
        />
        <label>Comment l’obtenir</label>
        <Segments
          nom="Comment l’obtenir"
          choix={[['check', 'La personne coche'], ['code', 'Avec un code'], ['rule', 'Règle']]}
          valeur={mode}
          onChange={changerMode}
        />
        {mode !== 'rule' && (
          <>
            <label>Montant</label>
            <Segments nom="Montant" choix={[[1, 'En plus'], [-1, 'En moins']]} valeur={signe} onChange={setSigne} />
            <div className="tarifs__echeance">
              <input
                className="field-input"
                type="number"
                min="0"
                step="0.1"
                inputMode="decimal"
                value={valeur}
                aria-label="Valeur"
                onChange={(e) => setValeur(e.target.value)}
              />
              <Segments nom="Unité" choix={[['eur', '€'], ['pct', '%']]} valeur={unite} onChange={setUnite} />
            </div>
          </>
        )}
        {mode === 'rule' && (
          <>
            <label htmlFor="option-regle">La règle, en français</label>
            <textarea
              id="option-regle"
              className="field-input tarifs__regle"
              rows={2}
              value={regle}
              placeholder="ex. Enlever 10 € par année d’ancienneté"
              onChange={(e) => {
                setRegle(e.target.value)
                setCompris(null)
              }}
            />
          </>
        )}
        {mode === 'code' && (
          <>
            <label htmlFor="option-code">Code à saisir</label>
            <input
              id="option-code"
              className="field-input tarifs__code"
              value={code}
              placeholder="ex. BIENVENUE"
              onChange={(e) => setCode(e.target.value.toUpperCase())}
            />
          </>
        )}
      </div>
      {mode === 'rule' && (
        <>
          <button
            type="button"
            className="btn btn--secondary btn--block tarifs__secondaire"
            disabled={enCours || !regle.trim()}
            onClick={comprendre}
          >
            Faire comprendre la règle
          </button>
          {compris && (
            <div className="creer-saison__cadre">
              <b>Compris :</b> {compris.understood}
              {compris.example && <p className="creer-saison__note">Exemple : {compris.example}</p>}
              {compris.calculation && (
                <p className="creer-saison__note tarifs__calcul">
                  Appliquée toute seule au paiement, à partir de la fiche. Calcul : <code>{compris.calculation}</code>
                </p>
              )}
            </div>
          )}
        </>
      )}
      {mode === 'code' && (
        <>
          <label className="champs__case">
            <input type="checkbox" checked={montre} onChange={(e) => setMontre(e.target.checked)} />
            <span>
              Montrer dans le formulaire
              <small className="tarifs__aide">Montré : la personne le coche. Secret : elle doit le taper.</small>
            </span>
          </label>
          <div className="tarifs__echeance">
            <div className="form-fields">
              <label htmlFor="option-max">Utilisations</label>
              <input
                id="option-max"
                className="field-input"
                type="number"
                min="1"
                inputMode="numeric"
                value={utilisations}
                placeholder="Sans limite"
                onChange={(e) => setUtilisations(e.target.value)}
              />
            </div>
            <div className="form-fields">
              <label htmlFor="option-jusquau">Jusqu’au</label>
              <input
                id="option-jusquau"
                className="field-input"
                type="date"
                value={jusquau}
                onChange={(e) => setJusquau(e.target.value)}
              />
            </div>
          </div>
        </>
      )}
      {mode === 'check' && (
        <>
          <label className="champs__case">
            <input
              type="checkbox"
              checked={quantite !== ''}
              onChange={(e) => setQuantite(e.target.checked ? 20 : '')}
            />
            <span>Quantité limitée</span>
          </label>
          {quantite !== '' && (
            <input
              className="field-input tarifs__sous"
              type="number"
              min="1"
              inputMode="numeric"
              value={quantite}
              aria-label="Quantité"
              onChange={(e) => setQuantite(e.target.value)}
            />
          )}
        </>
      )}
      <div className="form-fields">
        <label htmlFor="option-formules">Sur quelles formules</label>
        <select
          id="option-formules"
          className="field-input"
          value={formule}
          onChange={(e) => setFormule(e.target.value)}
        >
          <option value="">Tous les tarifs</option>
          {formules.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </div>
      <label className="champs__case">
        <input type="checkbox" checked={proposee} onChange={(e) => setProposee(e.target.checked)} />
        <span>Proposée cette saison</span>
      </label>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button
        type="button"
        className="btn btn--primary btn--block creer-saison__principal"
        disabled={enCours || !pret}
        onClick={valider}
      >
        OK
      </button>
      {option.id && (
        <button type="button" className="creer-saison__lien" onClick={onRetirer}>
          Retirer
        </button>
      )}
    </>
  )
}

export default function Tarifs({ ecoleId, onClose }) {
  const [donnees, setDonnees] = useState(null)
  const [ouverte, setOuverte] = useState(null) // formule ouverte (id absent = nouvelle)
  const [optionOuverte, setOptionOuverte] = useState(null) // option ou code promo ouvert
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
        await Promise.all(repris.adjustments.map((o) => tarifsApi.retirerOption(o.id)))
        await Promise.all(repris.plans.map((f) => tarifsApi.retirer(f.id)))
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

  function ouvrirOption(option) {
    setOptionOuverte(option)
    setNomOuverte(option.name)
  }

  async function enregistrerOption(option) {
    if (optionOuverte.id) await tarifsApi.modifierOption(optionOuverte.id, option)
    else await tarifsApi.creerOption(ecoleId, option)
    setOptionOuverte(null)
    await relire()
  }

  async function retirerOption() {
    const option = optionOuverte
    try {
      await tarifsApi.retirerOption(option.id)
      setOptionOuverte(null)
      await relire()
      montrerToast(`« ${option.name} » retiré`, async () => {
        // eslint-disable-next-line no-unused-vars
        const { id, ...reste } = option
        await tarifsApi.creerOption(ecoleId, reste)
        await relire()
      })
    } catch (e) {
      setErreur(e.message)
    }
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
  } else if (optionOuverte) {
    titre = nomOuverte || 'Nouvelle option ou code promo'
    retour = () => setOptionOuverte(null)
    corps = (
      <Option
        key={optionOuverte.id ?? 'nouvelle'}
        option={optionOuverte}
        formules={donnees.plans}
        onNom={setNomOuverte}
        onOk={enregistrerOption}
        onRetirer={retirerOption}
        onComprendre={(regle) => tarifsApi.comprendre(ecoleId, regle)}
      />
    )
  } else if (donnees) {
    corps = (
      <>
        {donnees.previous && !lectureSeule && (
          <div className="creer-saison__cadre">
            <strong>Repartir des tarifs de {donnees.previous.name} ?</strong>
            <p className="creer-saison__note">
              {donnees.previous.plans} formule{donnees.previous.plans > 1 ? 's' : ''}
              {donnees.previous.adjustments > 0 &&
                `, ${donnees.previous.adjustments} option${donnees.previous.adjustments > 1 ? 's' : ''} et codes promo`}
              , que vous pourrez modifier.
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
          </>
        )}
        <div className="creer-saison__partie">Options et codes promo</div>
        {donnees.adjustments.length === 0 && <p className="creer-saison__note">Aucune.</p>}
        {donnees.adjustments.map((o) => (
          <button
            key={o.id}
            type="button"
            className={`tarifs__ligne${o.active ? '' : ' tarifs__ligne--off'}`}
            disabled={lectureSeule}
            onClick={() => ouvrirOption(o)}
          >
            <span className="tarifs__nom">
              {o.name}
              <small>{resumeOption(o, donnees.plans)}</small>
            </span>
            <span className="tarifs__prix">{montantOption(o)}</span>
            {!lectureSeule && <Icon name="chevronRight" size={18} />}
          </button>
        ))}
        {!lectureSeule && (
          <>
            <button
              type="button"
              className="btn btn--secondary btn--block tarifs__secondaire"
              onClick={() =>
                ouvrirOption({
                  name: '', amount: -1000, unit: 'pct', mode: 'code', code: '', shown: false,
                  max_uses: null, until: null, quantity: null, active: true, plan_ids: [],
                })
              }
            >
              + Ajouter une option ou un code promo
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
        {erreur && !ouverte && !optionOuverte && <p className="login-screen__erreur">{erreur}</p>}
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
