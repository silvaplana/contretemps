import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import '../mail/mail.css'

// Ligne « Drives du club » de Connexions (spec/core.md §3 ; Seb, 19 novembre :
// « fais exactement comme les mails ») : les drives connectés, chacun avec
// « Voir », « Connecter » sans drive, « Ajouter un drive » ensuite. Écrans
// hors de la ligne (portail), comme MailReglages.jsx.

const ANNULER_MS = 10000
const SEULS = 'Seuls kDrive et Google Drive peuvent être connectés pour l’instant.'
const NOMS = { kdrive: 'kDrive', gdrive: 'Google Drive' }
const date = (iso) => new Date(iso).toLocaleDateString('fr-FR')

function Fournisseur({ ajout, nomInitial, google, onChoix }) {
  const [nom, setNom] = useState(nomInitial)
  return (
    <div className="mail__pile">
      {ajout && (
        <>
          <label className="mail__champ">
            <span>Nom du drive</span>
            <input value={nom} maxLength={30} onChange={(e) => setNom(e.target.value)} placeholder="Trésorerie" />
          </label>
          <p className="mail__discret">C’est le nom qui le désigne dans l’appli quand le club a plusieurs drives.</p>
        </>
      )}
      <p>Quel drive connecter ?</p>
      <button
        type="button"
        className="btn btn--secondary btn--block mail__fournisseur"
        disabled={ajout && !nom.trim()}
        onClick={() => onChoix('kdrive', nom.trim())}
      >
        kDrive
      </button>
      <button
        type="button"
        className="btn btn--secondary btn--block mail__fournisseur"
        disabled={(ajout && !nom.trim()) || !google}
        onClick={() => onChoix('gdrive', nom.trim())}
      >
        Google Drive
      </button>
      <p className="mail__discret">
        {google ? SEULS : 'Google Drive n’est pas encore proposé sur ce serveur. Seul kDrive peut être connecté.'}
      </p>
    </div>
  )
}

function Connexion({ ecoleId, fournisseur, drive, nom, google, onConnecte }) {
  const [adresse, setAdresse] = useState('')
  const [code, setCode] = useState('')
  const [numero, setNumero] = useState('')
  const [erreur, setErreur] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const kdrive = fournisseur === 'kdrive'
  const pret = /^\S+@\S+\.\S+$/.test(adresse.trim()) && (!kdrive || (code.trim() && /^\d+$/.test(numero.trim())))

  async function connecter() {
    setErreur(null)
    setEnCours(true)
    try {
      onConnecte(
        await api.connecter(ecoleId, { drive, name: nom, provider: fournisseur, address: adresse, code, driveRef: numero }),
      )
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  async function copier() {
    try {
      await navigator.clipboard.writeText(google)
    } catch {
      setErreur('Copiez l’adresse avec un appui long.')
    }
  }

  return (
    <div className="mail__pile">
      <label className="mail__champ">
        <span>Adresse {kdrive ? 'Infomaniak' : 'Google'} du club</span>
        <input type="email" value={adresse} onChange={(e) => setAdresse(e.target.value)} autoComplete="off" />
      </label>
      {kdrive ? (
        <>
          <ol className="mail__etapes">
            <li>Infomaniak s’ouvre sur les jetons d’API : touchez « Créer un jeton », application « Default application », droit « drive ».</li>
            <li>Copiez le jeton donné.</li>
            <li>Revenez ici et collez-le.</li>
          </ol>
          <button
            type="button"
            className="mail__lien"
            onClick={() => window.open('https://manager.infomaniak.com/v3/ng/profile/user/token/list', '_blank', 'noopener')}
          >
            Ouvrir Infomaniak
          </button>
          <label className="mail__champ">
            <span>Jeton Infomaniak</span>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" autoCapitalize="none" spellCheck={false} />
          </label>
          <label className="mail__champ">
            <span>Numéro du kDrive</span>
            <input value={numero} inputMode="numeric" onChange={(e) => setNumero(e.target.value)} placeholder="812345" />
          </label>
          <p className="mail__discret">
            Le numéro est dans l’adresse du kDrive ouvert dans le navigateur, après « /drive/ ». Infomaniak ne montre le
            jeton qu’une fois : s’il est perdu, créez-en un autre.
          </p>
        </>
      ) : (
        <>
          <ol className="mail__etapes">
            <li>Google Drive s’ouvre : sur le dossier du club, touchez Partager.</li>
            <li>Collez l’adresse ci-dessous, en « Lecteur » (« Éditeur » si l’appli doit y déposer des fichiers).</li>
            <li>Revenez ici et touchez Connecter.</li>
          </ol>
          <p className="mail__ligne">
            <span className="mail__discret" style={{ wordBreak: 'break-all' }}>{google}</span>
            <button type="button" className="btn btn--secondary" onClick={copier}>
              Copier
            </button>
          </p>
          <button
            type="button"
            className="mail__lien"
            onClick={() => window.open('https://drive.google.com', '_blank', 'noopener')}
          >
            Ouvrir Google Drive
          </button>
          <p className="mail__discret">L’appli ne voit que les dossiers partagés avec cette adresse.</p>
        </>
      )}
      <p className="mail__discret">L’appli n’efface jamais rien sur un drive.</p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button type="button" className="btn btn--primary mail__principal" onClick={connecter} disabled={!pret || enCours}>
        {enCours ? 'Connexion…' : 'Connecter'}
      </button>
    </div>
  )
}

function Connecte({ drive, onRenommer, onChanger, onDeconnecter }) {
  const [nom, setNom] = useState(null) // null : pas en train de renommer
  return (
    <div className="mail__pile">
      {drive.cut ? (
        <div className="mail__alerte" role="alert">
          <strong>Le drive n’est plus connecté</strong>
          {NOMS[drive.provider]} a refusé l’accès, souvent après un changement de mot de passe ou un partage retiré.
          <button type="button" className="btn btn--primary" onClick={onChanger}>
            Reconnecter
          </button>
        </div>
      ) : (
        <div className="helloasso__resultat helloasso__resultat--ok">
          <strong>✓ Drive connecté</strong>
          <dl>
            <dt>Nom</dt>
            <dd>{drive.name}</dd>
            <dt>Adresse</dt>
            <dd>{drive.address}</dd>
            <dt>Drive</dt>
            <dd>{NOMS[drive.provider]}</dd>
            <dt>Depuis le</dt>
            <dd>{date(drive.connected_at)}</dd>
          </dl>
        </div>
      )}
      {nom === null ? (
        <button type="button" className="mail__lien" onClick={() => setNom(drive.name)}>
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
          <input aria-label="Nom du drive" value={nom} maxLength={30} onChange={(e) => setNom(e.target.value)} />
          <button type="submit" className="btn btn--secondary" disabled={!nom.trim()}>
            Enregistrer
          </button>
        </form>
      )}
      <button type="button" className="mail__lien" onClick={onChanger}>
        Remplacer par un autre drive
      </button>
      <button type="button" className="btn btn--secondary btn--block" onClick={onDeconnecter}>
        Déconnecter le drive
      </button>
    </div>
  )
}

export default function DrivesReglages({ ecole, enabled }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState(null)
  // null | { vue: 'fournisseur' | 'kdrive' | 'gdrive' | 'connecte', drive, nom }
  // drive : le drive vu ou remplacé ; null : un drive à ajouter.
  const [ecran, setEcran] = useState(null)
  const [toast, setToast] = useState(null)
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

  useEffect(() => {
    if (!enabled) {
      setEtat(null)
      return
    }
    relire()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, enabled])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const drives = etat?.drives ?? []
  const vu = ecran && drives.find((d) => d.id === ecran.drive)

  function montrer(texte, ancien = null) {
    clearTimeout(minuteur.current)
    setToast({ texte, ancien })
    if (!ancien) minuteur.current = setTimeout(() => setToast(null), 4000)
  }

  function connecte(nouveau) {
    setEtat(nouveau)
    setEcran(null)
    montrer('Drive connecté')
  }

  async function renommer(nom) {
    try {
      setEtat(await api.renommer(ecole.id, vu.id, nom))
    } catch (e) {
      setErreur(e.message)
    }
  }

  // « Déconnecter le drive » : effacé au bout de 10 s, sauf Annuler.
  function deconnecter() {
    const ancien = etat
    const id = vu.id
    setEtat({ ...etat, drives: drives.filter((d) => d.id !== id) })
    setEcran(null)
    montrer('Drive déconnecté', ancien)
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

  const sansDecocher = (action) => (e) => {
    e.preventDefault()
    action()
  }
  const etatDrive = (d) => (d.cut ? `${d.address} : à reconnecter` : `Connecté : ${NOMS[d.provider]}, ${d.address}`)
  const titre =
    ecran?.vue === 'connecte'
      ? vu?.name ?? 'Drive du club'
      : ecran?.drive == null && drives.length > 0
        ? 'Ajouter un drive'
        : 'Connecter le drive du club'

  return (
    <>
      {!enabled && <small className="helloasso__etat">Les drives du club (kDrive ou Google Drive)</small>}
      {enabled && etat && drives.length === 0 && <small className="helloasso__etat">Pas encore connecté. {SEULS}</small>}
      {enabled &&
        drives.map((d) => (
          <span key={d.id} className="mail__reglage-boite">
            <small className="helloasso__etat">
              {drives.length > 1 && <strong>{d.name} · </strong>}
              {etatDrive(d)}
            </small>
            <button
              type="button"
              className="helloasso__lien"
              onClick={sansDecocher(() => setEcran({ vue: 'connecte', drive: d.id }))}
            >
              Voir
            </button>
          </span>
        ))}
      {enabled && erreur && <small className="helloasso__etat login-screen__erreur">{erreur}</small>}
      {enabled && etat && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={sansDecocher(() => setEcran({ vue: 'fournisseur', drive: null }))}
        >
          {drives.length ? 'Ajouter un drive' : 'Connecter'}
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
                  ajout={ecran.drive == null}
                  nomInitial={drives.length === 0 ? 'Club' : ''}
                  google={etat?.google_address}
                  onChoix={(cle, nom) => setEcran({ ...ecran, vue: cle, nom })}
                />
              )}
              {ecran.vue === 'connecte' && vu && (
                <Connecte
                  drive={vu}
                  onRenommer={renommer}
                  onChanger={() => setEcran({ ...ecran, vue: 'fournisseur' })}
                  onDeconnecter={deconnecter}
                />
              )}
              {(ecran.vue === 'kdrive' || ecran.vue === 'gdrive') && (
                <Connexion
                  key={ecran.vue}
                  ecoleId={ecole.id}
                  fournisseur={ecran.vue}
                  drive={ecran.drive}
                  nom={ecran.nom}
                  google={etat?.google_address}
                  onConnecte={connecte}
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
