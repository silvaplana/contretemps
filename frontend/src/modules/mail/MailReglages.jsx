import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import Connexion from './Connexion.jsx'
import { FOURNISSEURS } from './fournisseurs.js'
import './mail.css'

// Ligne « Boîte mail du club » de Connexions (spec/modules/mail.md §2, §4,
// §4 bis ; Seb, 18 novembre) : les boîtes connectées, chacune avec « Voir »,
// « Connecter » sans boîte, « Ajouter une boîte mail » ensuite. Écrans hors de
// la ligne (portail). Cocher la case sans boîte ouvre le choix du fournisseur.

const ANNULER_MS = 10000
const SEULES = 'Seules les boîtes Gmail et Infomaniak peuvent être connectées pour l’instant.'
const date = (iso) => new Date(iso).toLocaleDateString('fr-FR')

function Fournisseur({ ajout, nomInitial, onChoix }) {
  const [nom, setNom] = useState(nomInitial)
  return (
    <div className="mail__pile">
      {ajout && (
        <>
          <label className="mail__champ">
            <span>Nom de la boîte</span>
            <input value={nom} maxLength={30} onChange={(e) => setNom(e.target.value)} placeholder="Trésorerie" />
          </label>
          <p className="mail__discret">C’est le nom de son onglet dans Messages quand le club a plusieurs boîtes.</p>
        </>
      )}
      <p>Quelle boîte connecter ?</p>
      {Object.entries(FOURNISSEURS).map(([cle, f]) => (
        <button
          key={cle}
          type="button"
          className="btn btn--secondary btn--block mail__fournisseur"
          disabled={ajout && !nom.trim()}
          onClick={() => onChoix(cle, nom.trim())}
        >
          {f.nom}
        </button>
      ))}
      <p className="mail__discret">{SEULES}</p>
    </div>
  )
}

function Connectee({ boite, onReconnecter, onRenommer, onChanger, onDeconnecter }) {
  const [nom, setNom] = useState(null) // null : pas en train de renommer
  return (
    <div className="mail__pile">
      {boite.cut ? (
        <div className="mail__alerte" role="alert">
          <strong>La boîte mail n’est plus connectée</strong>
          {FOURNISSEURS[boite.provider]?.nom ?? 'Le fournisseur'} a refusé l’accès, souvent après un changement du mot
          de passe du compte.
          <button type="button" className="btn btn--primary" onClick={onReconnecter}>
            Reconnecter
          </button>
        </div>
      ) : (
        <div className="helloasso__resultat helloasso__resultat--ok">
          <strong>✓ Boîte connectée</strong>
          <dl>
            <dt>Nom</dt>
            <dd>{boite.name}</dd>
            <dt>Adresse</dt>
            <dd>{boite.address}</dd>
            <dt>Boîte</dt>
            <dd>{FOURNISSEURS[boite.provider]?.nom}</dd>
            <dt>Depuis le</dt>
            <dd>{date(boite.connected_at)}</dd>
          </dl>
        </div>
      )}
      <p className="mail__discret">
        Seuls les administrateurs cochés dans « Boîte mail du club » (Administrateurs) voient les mails.
      </p>
      {nom === null ? (
        <button type="button" className="mail__lien" onClick={() => setNom(boite.name)}>
          Renommer
        </button>
      ) : (
        <form
          className="mail__ligne"
          onSubmit={(e) => {
            e.preventDefault()
            if (nom.trim()) onRenommer(nom.trim()).then(() => setNom(null))
          }}
        >
          <input aria-label="Nom de la boîte" value={nom} maxLength={30} onChange={(e) => setNom(e.target.value)} />
          <button type="submit" className="btn btn--secondary" disabled={!nom.trim()}>
            Enregistrer
          </button>
        </form>
      )}
      <button type="button" className="mail__lien" onClick={onChanger}>
        Remplacer par une autre boîte
      </button>
      <button type="button" className="btn btn--secondary btn--block" onClick={onDeconnecter}>
        Déconnecter la boîte
      </button>
    </div>
  )
}

export default function MailReglages({ ecole, enabled }) {
  const [etat, setEtat] = useState(null)
  // L'état n'a pas pu être lu : la raison s'affiche sous la ligne.
  const [erreur, setErreur] = useState(null)
  // null | { vue: 'fournisseur' | 'gmail' | 'infomaniak' | 'connectee', boite, nom }
  // boite : la boîte vue, reconnectée ou remplacée ; null : une boîte à ajouter.
  const [ecran, setEcran] = useState(null)
  const [toast, setToast] = useState(null)
  const avant = useRef(enabled)
  const minuteur = useRef(null)

  async function relire() {
    try {
      const lu = await api.etat(ecole.id)
      setEtat(lu)
      setErreur(null)
      return lu
    } catch (e) {
      setEtat(null)
      setErreur(e.message)
      return null
    }
  }

  // Sous-module éteint : ses routes répondent « introuvable », rien à lire.
  useEffect(() => {
    const vientDEtreCoche = enabled && !avant.current
    avant.current = enabled
    if (!enabled) {
      setEtat(null)
      return
    }
    relire().then((lu) => {
      if (vientDEtreCoche && lu && !lu.boxes?.length) setEcran({ vue: 'fournisseur', boite: null })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, enabled])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const boites = etat?.boxes ?? []
  const vue = ecran && boites.find((b) => b.id === ecran.boite)

  function montrer(texte, ancien = null) {
    clearTimeout(minuteur.current)
    setToast({ texte, ancien })
    if (!ancien) minuteur.current = setTimeout(() => setToast(null), 4000)
  }

  function connectee(nouveau) {
    setEtat(nouveau)
    setEcran(null)
    montrer('Boîte connectée')
  }

  async function renommer(nom) {
    try {
      setEtat(await api.renommer(ecole.id, vue.id, nom))
    } catch (e) {
      setErreur(e.message)
    }
  }

  // « Déconnecter la boîte » : effacée au bout de 10 s, sauf Annuler.
  function deconnecter() {
    const ancien = etat
    const id = vue.id
    setEtat({ ...etat, boxes: boites.filter((b) => b.id !== id) })
    setEcran(null)
    montrer('Boîte déconnectée', ancien)
    minuteur.current = setTimeout(() => {
      setToast(null)
      api.deconnecter(ecole.id, id).catch(() => setEtat(ancien))
    }, ANNULER_MS)
  }

  function annuler() {
    clearTimeout(minuteur.current)
    setEtat(toast.ancien)
    setToast(null)
  }

  // Le bouton est dans l'étiquette de la case : ne pas la décocher.
  const sansDecocher = (action) => (e) => {
    e.preventDefault()
    action()
  }
  const etatBoite = (b) => (b.cut ? `${b.address} : à reconnecter` : `Connectée : ${b.address}`)
  const titre =
    ecran?.vue === 'connectee'
      ? vue?.name ?? 'Boîte mail du club'
      : ecran?.boite == null && boites.length > 0
        ? 'Ajouter une boîte mail'
        : 'Connecter la boîte mail du club'

  return (
    <>
      {!enabled && (
        <small className="helloasso__etat">La boîte mail du club (Gmail ou Infomaniak), lue et envoyée depuis Messages</small>
      )}
      {enabled && etat && boites.length === 0 && (
        <small className="helloasso__etat">Pas encore connectée. {SEULES}</small>
      )}
      {enabled &&
        boites.map((b) => (
          <span key={b.id} className="mail__reglage-boite">
            <small className="helloasso__etat">
              {boites.length > 1 && <strong>{b.name} · </strong>}
              {etatBoite(b)}
            </small>
            <button
              type="button"
              className="helloasso__lien"
              onClick={sansDecocher(() => setEcran({ vue: 'connectee', boite: b.id }))}
            >
              Voir
            </button>
          </span>
        ))}
      <small className="helloasso__etat">
        Seuls les administrateurs cochés dans « Boîte mail du club » (Administrateurs) voient les mails.
      </small>
      {enabled && erreur && <small className="helloasso__etat login-screen__erreur">{erreur}</small>}
      {enabled && boites.length === 0 && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={sansDecocher(async () => {
            const lu = etat ?? (await relire())
            if (lu?.boxes?.length) return
            if (lu) setEcran({ vue: 'fournisseur', boite: null })
          })}
        >
          Connecter
        </button>
      )}
      {enabled && boites.length > 0 && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={sansDecocher(() => setEcran({ vue: 'fournisseur', boite: null }))}
        >
          Ajouter une boîte mail
        </button>
      )}
      {ecran &&
        createPortal(
          <div className="creer-saison" role="dialog" aria-label={titre}>
            <div className="thread-screen__header">
              <button type="button" className="icon-btn" onClick={sansDecocher(() => setEcran(null))} aria-label="Retour">
                <Icon name="chevronLeft" size={22} />
              </button>
              <h2 className="creer-saison__titre">{titre}</h2>
            </div>
            <div className="creer-saison__corps mail">
              {ecran.vue === 'fournisseur' && (
                <Fournisseur
                  ajout={ecran.boite == null}
                  nomInitial={boites.length === 0 ? 'Club' : ''}
                  onChoix={(cle, nom) => setEcran({ ...ecran, vue: cle, nom })}
                />
              )}
              {ecran.vue === 'connectee' && vue && (
                <Connectee
                  boite={vue}
                  onReconnecter={() => setEcran({ ...ecran, vue: vue.provider })}
                  onRenommer={renommer}
                  onChanger={() => setEcran({ ...ecran, vue: 'fournisseur' })}
                  onDeconnecter={deconnecter}
                />
              )}
              {FOURNISSEURS[ecran.vue] && (
                <Connexion
                  key={ecran.vue}
                  ecoleId={ecole.id}
                  fournisseur={ecran.vue}
                  boite={ecran.boite}
                  nom={ecran.nom}
                  adresseInitiale={vue?.cut && vue.provider === ecran.vue ? vue.address : ''}
                  onConnecte={connectee}
                />
              )}
            </div>
          </div>,
          document.body,
        )}
      {toast &&
        createPortal(
          <div className="admin-groupes__toast" role="status">
            <span>{toast.texte}</span>
            {toast.ancien && (
              <button type="button" onClick={annuler}>
                Annuler
              </button>
            )}
          </div>,
          document.body,
        )}
    </>
  )
}
