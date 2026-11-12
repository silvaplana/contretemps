import { useCallback, useEffect, useRef, useState } from 'react'
import { Capacitor, registerPlugin } from '@capacitor/core'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import * as api from './api.js'

// Fights › Tournage (spec/modules/video-combats.md §4 et §6.3, Seb 12/11) :
// tout le tournage est ici. Un sélecteur Caméra | Éteint | Télécommande et un
// seul bouton Filmer / Arrêter. En Caméra (appli Android « Tournage »
// seulement), ce téléphone filme ; en Télécommande, le bouton envoie l'ordre à
// la caméra de l'école. Le serveur garde l'ordre : la caméra obéit au dernier.

const RELIRE_MS = 5000
// Le film en tâche de fond de l'appli Tournage (frontend/android, camera/TournagePlugin.kt).
const Natif = registerPlugin('Tournage')
const DANS_L_APPLI = Capacitor.isNativePlatform()
const APPLI = 'https://github.com/silvaplana/contretemps/releases/tag/tournage-latest'
// Le rôle de ce téléphone et le jeton de la caméra, gardés sur l'appareil.
const ROLE = 'sc-tournage-role'
const JETON = 'sc-tournage-jeton'

function lire(cle) {
  try {
    return localStorage.getItem(cle)
  } catch {
    return null
  }
}

function garder(cle, valeur) {
  try {
    if (valeur == null) localStorage.removeItem(cle)
    else localStorage.setItem(cle, valeur)
  } catch {
    // stockage refusé : valable pour cette fois
  }
}

function useCamera() {
  const [camera, setCamera] = useState(null)
  const relire = useCallback(() => api.camera().then(setCamera, () => {}), [])
  useEffect(() => {
    relire()
    const minuteur = setInterval(relire, RELIRE_MS)
    return () => clearInterval(minuteur)
  }, [relire])
  return [camera, setCamera]
}

// L'état du film sur ce téléphone, relu chaque seconde.
function useEtatNatif(actif) {
  const [etat, setEtat] = useState(null)
  useEffect(() => {
    if (!actif) return undefined
    const relire = () => Natif.status().then(setEtat, () => {})
    relire()
    const minuteur = setInterval(relire, 1000)
    return () => clearInterval(minuteur)
  }, [actif])
  return actif ? etat : null
}

// L'envoi de la vidéo filmée (Seb, 12/11), sans parler de morceaux : une
// barre pour tout ce qui attend, ou pourquoi l'envoi attend.
function Envoi({ natif }) {
  if (!natif) return null
  if (natif.size) {
    const pourcent = Math.min(99, Math.floor((natif.sent / natif.size) * 100))
    return (
      <div className="sc-morceau">
        <span>Envoi de la vidéo : {pourcent} %</span>
        <span className="sc-morceau__barre" role="progressbar" aria-valuenow={pourcent} aria-valuemin={0} aria-valuemax={100}>
          <span style={{ width: `${pourcent}%` }} />
        </span>
      </div>
    )
  }
  if (!natif.pending) return null
  return <p className="sc-meta">Vidéo en attente d’envoi{natif.sendFailure ? ` (${natif.sendFailure})` : ''}</p>
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

function titreDuJour() {
  const d = new Date()
  return `Séance du ${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
}

// L'image de la caméra quand elle ne filme pas, pour cadrer. Le film en
// tâche de fond a besoin de la caméra : l'image la lâche dès qu'il démarre.
function Image({ allumee }) {
  const video = useRef(null)
  useEffect(() => {
    if (!allumee || !navigator.mediaDevices?.getUserMedia) return undefined
    let flux = null
    let fini = false
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment', width: 1920, height: 1080 }, audio: false })
      .then((f) => {
        if (fini) {
          f.getTracks().forEach((t) => t.stop())
          return
        }
        flux = f
        if (video.current) video.current.srcObject = f
        Natif.preview({ on: true }).catch(() => {})
      })
      .catch(() => {})
    return () => {
      fini = true
      flux?.getTracks().forEach((t) => t.stop())
      Natif.preview({ on: false }).catch(() => {})
    }
  }, [allumee])
  return <video ref={video} className="sc-image__video" autoPlay muted playsInline hidden={!allumee} />
}

export default function Tournage({ montrer, rafraichir }) {
  const [role, setRole] = useState(() => lire(ROLE) ?? 'off')
  const [camera, setCamera] = useCamera()
  const [enCours, setEnCours] = useState(false)
  const natif = useEtatNatif(DANS_L_APPLI && role === 'cam')
  const filme = camera?.state === 'recording'
  const chrono = useChrono(filme ? camera.started_at : null)

  // L'appli Tournage rouverte en « Caméra » : le film en tâche de fond repart.
  useEffect(() => {
    const jeton = lire(JETON)
    if (DANS_L_APPLI && role === 'cam' && jeton) {
      Natif.start({ server: api.adresseApi(), token: jeton }).catch(() => {})
    }
  }, [role])

  async function choisir(nouveau) {
    if (nouveau === role || enCours) return
    setEnCours(true)
    try {
      if (role === 'cam' && DANS_L_APPLI) await Natif.stop()
      if (nouveau === 'cam' && DANS_L_APPLI) {
        const { token } = await api.ceTelephoneFilme()
        garder(JETON, token)
        await Natif.start({ server: api.adresseApi(), token })
      }
      if (nouveau !== 'cam') garder(JETON, null)
      garder(ROLE, nouveau)
      setRole(nouveau)
    } catch (e) {
      montrer(e.message || 'La caméra ne démarre pas.')
    } finally {
      setEnCours(false)
    }
  }

  async function filmerOuArreter() {
    if (enCours) return
    setEnCours(true)
    try {
      setCamera(await (filme ? api.arreterCamera() : api.demarrerCamera(titreDuJour())))
      rafraichir()
    } catch (e) {
      montrer(e.message)
    } finally {
      setEnCours(false)
    }
  }

  const selecteur = (
    <SegmentedTabs
      className="sc-tournage__role"
      options={[
        { value: 'cam', label: 'Caméra' },
        { value: 'off', label: 'Éteint' },
        { value: 'remote', label: 'Télécommande' },
      ]}
      value={role}
      onChange={choisir}
    />
  )
  const bouton = (
    <button
      type="button"
      className={`btn btn--primary sc-tournage__bouton${filme ? ' sc-tournage__bouton--stop' : ''}`}
      disabled={enCours || !camera || ['none', 'offline'].includes(camera.state)}
      onClick={filmerOuArreter}
    >
      {filme ? '■ Arrêter' : '● Filmer'}
    </button>
  )

  let corps
  if (role === 'off') {
    corps = <p className="sc-meta">Ce téléphone ne filme ni ne commande rien.</p>
  } else if (role === 'cam' && !DANS_L_APPLI) {
    corps = (
      <>
        <p>Pour filmer, ce téléphone doit ouvrir Contretemps dans l’appli « Tournage ».</p>
        <a className="btn btn--primary sc-tournage__bouton" href={APPLI} target="_blank" rel="noreferrer">
          Installer l’appli Tournage
        </a>
      </>
    )
  } else if (role === 'cam') {
    const tient = !filme && !natif?.recording && !natif?.wanted
    corps = (
      <>
        <div className="sc-image">
          <Image allumee={tient} />
          <span className="sc-image__etat">
            {natif?.recording ? (
              <>
                <span className="sc-led sc-led--on" /> Filme {chrono}
              </>
            ) : natif?.wanted ? (
              'Démarrage…'
            ) : (
              'Prête'
            )}
          </span>
        </div>
        <p className="sc-meta">
          {natif?.error ?? (natif?.online === false ? 'Connexion au serveur…' : 'Fixez le téléphone en paysage, toute la surface dans l’image.')}
        </p>
        <Envoi natif={natif} />
        {bouton}
      </>
    )
  } else {
    let etat
    if (!camera || ['none', 'offline'].includes(camera.state)) {
      etat = (
        <span className="sc-tournage__etat sc-tournage__etat--off">
          <span className="sc-led sc-led--off" /> Caméra éteinte
        </span>
      )
    } else if (filme) {
      etat = (
        <span className="sc-tournage__etat sc-tournage__etat--rec">
          <span className="sc-led sc-led--on" /> La caméra filme · {chrono}
        </span>
      )
    } else {
      const batterie = camera.battery_percent != null ? ` · ${camera.battery_percent} %` : ''
      etat = (
        <span className="sc-tournage__etat">
          <span className="sc-led" /> Caméra de la salle prête{batterie}
        </span>
      )
    }
    corps = (
      <>
        {etat}
        {bouton}
        {(!camera || ['none', 'offline'].includes(camera.state)) && (
          <p className="sc-meta">Mettez le téléphone de la salle sur « Caméra », dans l’appli Tournage.</p>
        )}
      </>
    )
  }

  return (
    <div className="sc-tournage">
      {selecteur}
      {corps}
    </div>
  )
}
