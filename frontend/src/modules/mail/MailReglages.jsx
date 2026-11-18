import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import Connexion from './Connexion.jsx'
import { FOURNISSEURS } from './fournisseurs.js'
import './mail.css'

// Ligne Mail de Fonctionnalités (spec/modules/mail.md §2, §4 ; Seb,
// 18 novembre) : la boîte connectée, « Connecter » ou « Voir », comme FFST et
// HelloAsso. Écrans hors de la ligne (portail) : la ligne est l'étiquette de
// la case. Cocher la case sans boîte ouvre le choix du fournisseur.

const ANNULER_MS = 10000
const SEULES = 'Seules les boîtes Gmail et Infomaniak peuvent être connectées pour l’instant.'
const date = (iso) => new Date(iso).toLocaleDateString('fr-FR')

function Fournisseur({ onChoix }) {
  return (
    <div className="mail__pile">
      <p>Quelle boîte connecter ?</p>
      {Object.entries(FOURNISSEURS).map(([cle, f]) => (
        <button key={cle} type="button" className="btn btn--secondary btn--block mail__fournisseur" onClick={() => onChoix(cle)}>
          {f.nom}
        </button>
      ))}
      <p className="mail__discret">{SEULES}</p>
    </div>
  )
}

function Connectee({ etat, onReconnecter, onChanger, onDeconnecter }) {
  return (
    <div className="mail__pile">
      {etat.cut ? (
        <div className="mail__alerte" role="alert">
          <strong>La boîte mail n’est plus connectée</strong>
          {FOURNISSEURS[etat.provider]?.nom ?? 'Le fournisseur'} a refusé l’accès, souvent après un changement du mot
          de passe du compte.
          <button type="button" className="btn btn--primary" onClick={onReconnecter}>
            Reconnecter
          </button>
        </div>
      ) : (
        <div className="helloasso__resultat helloasso__resultat--ok">
          <strong>✓ Boîte connectée</strong>
          <dl>
            <dt>Adresse</dt>
            <dd>{etat.address}</dd>
            <dt>Boîte</dt>
            <dd>{FOURNISSEURS[etat.provider]?.nom}</dd>
            <dt>Depuis le</dt>
            <dd>{date(etat.connected_at)}</dd>
          </dl>
        </div>
      )}
      <p className="mail__discret">
        Elle se lit dans Messages, puce Mail, par les personnes cochées dans « Boîte mail du club » (Administrateurs).
      </p>
      <button type="button" className="mail__lien" onClick={onChanger}>
        Connecter une autre boîte
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
  const [ecran, setEcran] = useState(null) // null | 'fournisseur' | 'gmail' | 'infomaniak' | 'connectee'
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
      if (vientDEtreCoche && lu && !lu.connected) setEcran('fournisseur')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, enabled])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  function connectee(nouveau) {
    setEtat(nouveau)
    setEcran(null)
    clearTimeout(minuteur.current)
    setToast({ texte: 'Boîte connectée' })
    minuteur.current = setTimeout(() => setToast(null), 4000)
  }

  // « Déconnecter la boîte » : effacée au bout de 10 s, sauf Annuler.
  function deconnecter() {
    const ancien = etat
    setEtat({ ...etat, connected: false, address: null, cut: false })
    setEcran(null)
    clearTimeout(minuteur.current)
    minuteur.current = setTimeout(() => {
      setToast(null)
      api.deconnecter(ecole.id).catch(() => setEtat(ancien))
    }, ANNULER_MS)
    setToast({ texte: 'Boîte déconnectée', ancien })
  }

  function annuler() {
    clearTimeout(minuteur.current)
    setEtat(toast.ancien)
    setToast(null)
  }

  const connecte = etat?.connected
  const petit = connecte
    ? etat.cut
      ? `${etat.address} : à reconnecter`
      : `Connectée : ${etat.address}`
    : enabled
      ? `Pas encore connectée. ${SEULES}`
      : 'La boîte mail du club (Gmail ou Infomaniak), lue et envoyée depuis Messages'
  const titre = ecran === 'connectee' ? 'Boîte mail du club' : 'Connecter la boîte mail du club'

  return (
    <>
      <small className="helloasso__etat">{petit}</small>
      {enabled && erreur && <small className="helloasso__etat login-screen__erreur">{erreur}</small>}
      {enabled && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={async (e) => {
            // Le bouton est dans l'étiquette de la case : ne pas la décocher.
            e.preventDefault()
            const lu = etat ?? (await relire())
            if (lu) setEcran(lu.connected ? 'connectee' : 'fournisseur')
          }}
        >
          {connecte ? 'Voir la boîte' : 'Connecter la boîte'}
        </button>
      )}
      {ecran &&
        createPortal(
          <div className="creer-saison" role="dialog" aria-label={titre}>
            <div className="thread-screen__header">
              <button
                type="button"
                className="icon-btn"
                onClick={(e) => {
                  e.preventDefault()
                  setEcran(null)
                }}
                aria-label="Retour"
              >
                <Icon name="chevronLeft" size={22} />
              </button>
              <h2 className="creer-saison__titre">{titre}</h2>
            </div>
            <div className="creer-saison__corps mail">
              {ecran === 'fournisseur' && <Fournisseur onChoix={setEcran} />}
              {ecran === 'connectee' && (
                <Connectee
                  etat={etat}
                  onReconnecter={() => setEcran(etat.provider)}
                  onChanger={() => setEcran('fournisseur')}
                  onDeconnecter={deconnecter}
                />
              )}
              {FOURNISSEURS[ecran] && (
                <Connexion
                  key={ecran}
                  ecoleId={ecole.id}
                  fournisseur={ecran}
                  adresseInitiale={etat?.cut && etat.provider === ecran ? etat.address : ''}
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
