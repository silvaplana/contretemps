import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import * as api from './api.js'

// La caméra de la salle (spec/modules/video-combats.md §6.3, étape 3), pour
// les coachs : la pastille en haut à droite, le panneau qui descend et la
// bande rouge pendant le film. L'état est relu toutes les 5 s, au rythme du
// téléphone.

const RELIRE_MS = 5000

export function useCamera(actif) {
  const [camera, setCamera] = useState(null)
  const relire = useCallback(() => api.camera().then(setCamera, () => {}), [])
  useEffect(() => {
    if (!actif) return undefined
    relire()
    const minuteur = setInterval(relire, RELIRE_MS)
    return () => clearInterval(minuteur)
  }, [actif, relire])
  return [camera, setCamera]
}

const MOTS = { ready: 'Prête', recording: 'Filme', offline: 'Hors service', none: 'Installer' }

// Dans la barre du haut de l'appli (components/Header.jsx : #entete-onglet).
export function PastilleCamera({ camera, onOpen }) {
  const [enTete, setEnTete] = useState(null)
  useEffect(() => {
    const id = requestAnimationFrame(() => setEnTete(document.getElementById('entete-onglet')))
    return () => cancelAnimationFrame(id)
  }, [])
  if (!camera || !enTete) return null
  return createPortal(
    <button type="button" className={`sc-cam sc-cam--${camera.state}`} onClick={onOpen} aria-label="Caméra de la salle">
      <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h7A2.5 2.5 0 0 1 16 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 4 17.5z" />
        <path d="M17 9.5l4-2.6c.5-.3 1 .1 1 .6v9c0 .5-.5.9-1 .6l-4-2.6z" />
      </svg>
      <span>{MOTS[camera.state]}</span>
    </button>,
    enTete,
  )
}

// « 00:12:34 » depuis le début du film, à la seconde.
function useChrono(depuis) {
  const [maintenant, setMaintenant] = useState(() => Date.now())
  useEffect(() => {
    if (!depuis) return undefined
    const minuteur = setInterval(() => setMaintenant(Date.now()), 1000)
    return () => clearInterval(minuteur)
  }, [depuis])
  if (!depuis) return ''
  const s = Math.max(0, Math.floor((maintenant - new Date(`${depuis}Z`).getTime()) / 1000))
  return [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map((x) => String(x).padStart(2, '0')).join(':')
}

export function BandeCamera({ camera, onOpen }) {
  const chrono = useChrono(camera?.state === 'recording' ? camera.started_at : null)
  if (camera?.state !== 'recording') return null
  return (
    <button type="button" className="sc-bande" onClick={onOpen}>
      <span className="sc-led sc-led--on" />
      Enregistrement{chrono && ` · ${chrono}`}
      <span className="sc-bande__ouvrir">Ouvrir</span>
    </button>
  )
}

function go(octets) {
  return octets == null ? null : `${Math.round(octets / 1e9)} Go libres`
}

export function PanneauCamera({ camera, setCamera, cours, montrer, onClose, rafraichir }) {
  const [titre, setTitre] = useState(cours?.[0]?.nom ?? '')
  const [enCours, setEnCours] = useState(false)
  const chrono = useChrono(camera.state === 'recording' ? camera.started_at : null)

  async function faire(action) {
    if (enCours) return
    setEnCours(true)
    try {
      setCamera(await action())
      rafraichir()
    } catch (e) {
      montrer(e.message)
    } finally {
      setEnCours(false)
    }
  }

  const batterie = camera.battery_percent != null ? `batterie ${camera.battery_percent} %` : null
  const signal = (
    <>
      <span className="sc-meta">Signal « compris » au début et à la fin d’un combat</span>
      <SegmentedTabs
        options={[
          { value: 'beep', label: 'Bip' },
          { value: 'light', label: 'Lampe' },
          { value: 'both', label: 'Les deux' },
        ]}
        value={camera.signal}
        onChange={(v) => faire(() => api.signalCamera(v))}
      />
    </>
  )

  let carte
  if (camera.state === 'none') {
    carte = (
      <>
        <div className="sc-rec">
          <span className="sc-led sc-led--off" />
          Installer la caméra
        </div>
        {camera.pairing_code ? (
          <>
            <p className="sc-meta">Sur le téléphone de la salle, ouvrez l’appli caméra et tapez ce code :</p>
            <p className="sc-code">
              {camera.pairing_code.slice(0, 4)} {camera.pairing_code.slice(4)}
            </p>
            <p className="sc-meta">Valable 10 minutes.</p>
          </>
        ) : (
          <>
            <p className="sc-meta">Installez l’appli caméra sur le téléphone de la salle, puis affichez un code à y taper.</p>
            <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => faire(api.codeCamera)}>
              Afficher un code
            </button>
          </>
        )}
      </>
    )
  } else if (camera.state === 'ready') {
    const envoi = camera.last_upload_at ? `dernier envoi ${api.jour(camera.last_upload_at.slice(0, 10)).toLowerCase()}` : null
    carte = (
      <>
        <div className="sc-rec">
          <span className="sc-led" />
          Caméra prête
        </div>
        <p className="sc-meta">
          {[camera.battery_percent != null && `Batterie ${camera.battery_percent} %`, go(camera.free_bytes), envoi]
            .filter(Boolean)
            .join(' · ')}
        </p>
        <label htmlFor="sc-cam-cours" className="sc-meta">
          Cours
        </label>
        <input
          id="sc-cam-cours"
          className="field-input"
          list="sc-cam-cours-liste"
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
        />
        <datalist id="sc-cam-cours-liste">
          {cours?.map((c) => (
            <option key={c.id} value={c.nom} />
          ))}
        </datalist>
        {signal}
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => faire(() => api.demarrerCamera(titre))}>
          Démarrer la séance
        </button>
      </>
    )
  } else if (camera.state === 'recording') {
    carte = (
      <>
        <div className="sc-rec">
          <span className="sc-led sc-led--on" />
          Enregistrement en cours
        </div>
        <p className="sc-meta">{[camera.session_title, chrono, batterie].filter(Boolean).join(' · ')}</p>
        {signal}
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => faire(api.arreterCamera)}>
          Fin de séance
        </button>
      </>
    )
  } else {
    carte = (
      <>
        <div className="sc-rec">
          <span className="sc-led sc-led--off" />
          Caméra hors service
        </div>
        <p className="sc-meta">Coupure ou redémarrage du téléphone. Rouvrez l’appli caméra sur le téléphone de la salle.</p>
      </>
    )
  }

  // Le panneau descend de sous la barre du haut, comme sur la maquette.
  const haut = document.querySelector('.app-header')?.getBoundingClientRect().bottom ?? 0
  return (
    <div className="sc-panneau-fond" style={{ top: haut }} onClick={onClose}>
      <div className="sc-panneau" role="dialog" aria-label="Caméra de la salle" onClick={(e) => e.stopPropagation()}>
        <div className="sc-panneau__carte">{carte}</div>
        {camera.paired && camera.state !== 'recording' && (
          <button type="button" className="sc-lien" onClick={() => faire(api.codeCamera)}>
            {camera.pairing_code ? `Code pour un autre téléphone : ${camera.pairing_code.slice(0, 4)} ${camera.pairing_code.slice(4)}` : 'Changer de téléphone'}
          </button>
        )}
        <button type="button" className="sc-lien" onClick={onClose}>
          Fermer
        </button>
      </div>
    </div>
  )
}
