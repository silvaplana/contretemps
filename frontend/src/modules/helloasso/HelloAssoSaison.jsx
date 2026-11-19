import { useEffect, useState } from 'react'
import * as api from './api.js'
import { mots } from '../../api/mots.js'

// Comment la saison en cours utilise HelloAsso (spec/modules/helloasso.md
// §8.1, maquette « réglages HelloAsso ») : trois cartes, une seule cochée.
// « HelloAsso fait tout » se fixe en choisissant la campagne ; les deux
// autres tout de suite. Quitter une campagne la retire (Annuler 10 s,
// `onToast`).

const NATURES = { Membership: 'Adhésion', Event: 'Événement' }

export function resumeSaison(lu) {
  if (lu.mode === 'master') return `HelloAsso fait tout${lu.form ? ` · campagne « ${lu.form.name} »` : ''}`
  if (lu.mode === 'payment') return 'L’appli fait tout, HelloAsso encaisse'
  return 'HelloAsso n’est pas encore utilisé pour cette saison'
}

function Carte({ coche, titre, texte, onClick, children }) {
  return (
    <>
      <button type="button" className="helloasso__carte" role="radio" aria-checked={coche} onClick={onClick}>
        <span className="helloasso__carte-titre">
          <span className="helloasso__radio" aria-hidden="true" />
          {titre}
        </span>
        <span className="helloasso__carte-texte">{texte}</span>
      </button>
      {coche && children && <div className="helloasso__detail">{children}</div>}
    </>
  )
}

export default function HelloAssoSaison({ ecoleId, onChange, onToast }) {
  const [lu, setLu] = useState(null)
  // La carte cochée à l'écran : « master » peut l'être avant sa campagne.
  const [mode, setMode] = useState(null)
  const [formulaires, setFormulaires] = useState(null)
  const [erreur, setErreur] = useState('')
  // La liste des campagnes n'a pas pu être lue chez HelloAsso.
  const [erreurListe, setErreurListe] = useState('')
  const [synchro, setSynchro] = useState('')

  async function relire() {
    const etat = await api.saison(ecoleId)
    setLu(etat)
    setMode(etat.mode)
    onChange?.(etat)
    return etat
  }

  // La liste des campagnes, gardée 10 minutes par le serveur ; « Relire la
  // liste » la redemande à HelloAsso (Seb, 19 novembre 2026).
  function chargerListe(relireListe = false) {
    return api
      .campagne(ecoleId, relireListe)
      .then((c) => {
        setFormulaires(c.can_change ? c.forms : null)
        setErreurListe(c.error ?? '')
      })
      .catch((e) => {
        setFormulaires([])
        setErreurListe(e.message)
      })
  }

  useEffect(() => {
    relire().catch((e) => setErreur(e.message))
    chargerListe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])

  if (!lu) return erreur ? <p className="login-screen__erreur">{erreur}</p> : null

  async function agir(action) {
    setErreur('')
    try {
      await action()
      await relire()
    } catch (e) {
      setErreur(e.message)
      await relire().catch(() => null)
    }
  }

  // Quitter « HelloAsso fait tout » retire la campagne : Annuler la remet.
  function annulerRetrait(ancienne) {
    if (!ancienne) return
    onToast('Campagne retirée, les réponses restent', () =>
      agir(() => api.choisirCampagne(ecoleId, { form_type: ancienne.form_type, form_slug: ancienne.form_slug })),
    )
  }

  function choisir(nouveau) {
    if (nouveau === mode) return
    const ancienne = lu.mode === 'master' ? lu.form : null
    setMode(nouveau)
    setSynchro('')
    if (nouveau === 'master') return // la campagne fixera le choix
    agir(() => api.choisirSaison(ecoleId, nouveau)).then(() => annulerRetrait(ancienne))
  }

  function choisirCampagne(valeur) {
    const form = formulaires.find((f) => `${f.form_type}/${f.form_slug}` === valeur)
    if (!form) return
    setSynchro('')
    agir(() => api.choisirCampagne(ecoleId, { form_type: form.form_type, form_slug: form.form_slug })).then(() =>
      onToast('Campagne choisie'),
    )
  }

  async function synchroniser() {
    setSynchro('Synchronisation…')
    try {
      const r = await api.synchroniser(ecoleId)
      setSynchro(`Synchronisé à l’instant : ${r.created} nouvelle${r.created > 1 ? 's' : ''} fiche${r.created > 1 ? 's' : ''}.`)
    } catch (e) {
      setSynchro(e.message)
    }
  }

  const choisie = lu.form ? `${lu.form.form_type}/${lu.form.form_slug}` : ''
  return (
    <div role="radiogroup" aria-label={`Saison ${lu.season_name ?? ''}`}>
      <p>Comment cette saison utilise HelloAsso ?</p>
      <Carte
        coche={mode === 'master'}
        titre="HelloAsso fait tout"
        texte="Les gens s’inscrivent et paient sur HelloAsso. L’appli recopie les adhérents, leurs réponses et leurs paiements."
        onClick={() => choisir('master')}
      >
        <label htmlFor="helloasso-campagne">Campagne HelloAsso</label>
        <select
          id="helloasso-campagne"
          className="field-input"
          value={choisie}
          onChange={(e) => choisirCampagne(e.target.value)}
        >
          <option value="">Choisir une campagne</option>
          {(formulaires ?? []).map((f) => (
            <option key={`${f.form_type}/${f.form_slug}`} value={`${f.form_type}/${f.form_slug}`}>
              {f.name} ({NATURES[f.form_type] ?? f.form_type})
            </option>
          ))}
        </select>
        <button type="button" className="btn btn--secondary" onClick={() => chargerListe(true)}>
          Relire la liste
        </button>
        {erreurListe && <p className="login-screen__erreur">{erreurListe}</p>}
        {!erreurListe && formulaires?.length === 0 && (
          <p className="muted">Aucune campagne d’adhésion ou d’événement trouvée sur HelloAsso.</p>
        )}
        {lu.form && (
          <>
            <ul className="helloasso__liste">
              <li>Les {mots().eleves} viennent de HelloAsso : plus de création à la main.</li>
              <li>Les tarifs sont ceux de la campagne, en lecture seule.</li>
              <li>Ses questions passent sur la fiche, verrouillées.</li>
              <li>Vous pouvez ajouter vos propres champs à côté.</li>
            </ul>
            <button type="button" className="btn btn--secondary" onClick={synchroniser}>
              Synchroniser maintenant
            </button>
            <p className="creer-saison__note">
              {synchro ||
                (lu.current
                  ? 'Synchronisé toutes les 5 minutes.'
                  : 'Saison passée : pas de recopie automatique. Cliquez sur « Synchroniser maintenant » pour recopier.')}
            </p>
          </>
        )}
      </Carte>
      <Carte
        coche={mode === 'payment'}
        titre="L’appli fait tout, HelloAsso encaisse"
        texte={`Les gens s’inscrivent dans l’appli et vous validez. HelloAsso sert seulement à payer par carte, ${mots().eleve} par ${mots().eleve}.`}
        onClick={() => choisir('payment')}
      >
        <ul className="helloasso__liste">
          <li>Vos champs, vos tarifs, votre formulaire d’inscription.</li>
          <li>Vous créez et modifiez vos {mots().eleves} librement.</li>
          <li>Pas de campagne à choisir : chaque paiement arrive sur le compte HelloAsso de l’association.</li>
          <li>Chèque, espèces et virement restent possibles à côté.</li>
        </ul>
      </Carte>
      <Carte
        coche={mode === 'none'}
        titre="Sans HelloAsso"
        texte="Vous gérez les inscriptions dans l’appli et vous encaissez vous-mêmes."
        onClick={() => choisir('none')}
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <p className="creer-saison__note">
        Le choix vaut pour la saison {lu.season_name}. Il se refait à chaque nouvelle saison.
      </p>
    </div>
  )
}
