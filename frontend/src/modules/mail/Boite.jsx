import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
import * as api from './api.js'
import { NOUVEAU } from './brouillon.js'
import Ecrire from './Ecrire.jsx'
import { dateListe, initiales, nom } from './format.js'
import UnMail from './UnMail.jsx'

// La boîte du club (spec/modules/mail.md §5) : dossier et recherche, une
// ligne par mail, rond qui coche, étoile, « Mails plus anciens ». Ranger et
// supprimer partent au bout de 10 s, sauf Annuler (§8) : le mail disparaît
// tout de suite de la liste, la demande à Gmail attend.

const ANNULER_MS = 10000
const RELIRE_MS = 60000
const RANGE = {
  archive: 'Archivé',
  trash: 'Mis à la corbeille',
  spam: 'Mis dans le spam',
  inbox: 'Remis dans la boîte de réception',
  delete: 'Supprimé définitivement',
  send: 'Mail envoyé',
}
const DOSSIERS = [{ key: 'inbox', label: 'Boîte de réception' }]

// `boite` : la boîte affichée (`etat.boxes`), `boites` : toutes, pour « De »
// quand on écrit (spec §4 bis).
export default function Boite({ ecoleId, boite, boites, menuBoite, onCoupee }) {
  const [dossiers, setDossiers] = useState(DOSSIERS)
  const [dossier, setDossier] = useState('inbox')
  const [recherche, setRecherche] = useState('')
  const [cherche, setCherche] = useState('')
  const [mails, setMails] = useState(null)
  const [encore, setEncore] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [coches, setCoches] = useState(() => new Set())
  const [ouvert, setOuvert] = useState(null)
  const [toast, setToast] = useState(null)
  // Écrire (§7) : { brouillon, fichiers } ouvert, ou null.
  const [ecrire, setEcrire] = useState(null)
  // Rangement ou envoi en attente (Annuler 10 s) : { dossier, uids, action,
  // minuteur } ou { action: 'send', brouillon, fichiers, minuteur }.
  const attente = useRef(null)
  const [cachés, setCachés] = useState(() => new Set())

  const echec = useCallback(
    (e) => {
      if (e.status === 409) onCoupee()
      else setErreur(e.message)
    },
    [onCoupee],
  )

  const charger = useCallback(
    (silencieux = false) => {
      if (!silencieux) setMails(null)
      setErreur(null)
      return api.lister(ecoleId, boite.id, dossier, { recherche: cherche }).then((r) => {
        setMails(r.messages)
        setEncore(r.hasMore)
      }, echec)
    },
    [ecoleId, boite.id, dossier, cherche, echec],
  )

  useEffect(() => {
    api.dossiers(ecoleId, boite.id).then((r) => setDossiers(r.folders), echec)
  }, [ecoleId, boite.id, echec])

  useEffect(() => {
    charger()
  }, [charger])

  // Nouveaux mails : liste relue chaque minute tant que l'écran est affiché.
  useEffect(() => {
    if (ouvert) return undefined
    const minuteur = setInterval(() => !document.hidden && charger(true), RELIRE_MS)
    return () => clearInterval(minuteur)
  }, [charger, ouvert])

  // Envoie à Gmail le rangement en attente (au bout des 10 s, ou avant d'en
  // lancer un autre).
  const envoyer = useCallback(() => {
    const a = attente.current
    if (!a) return
    attente.current = null
    clearTimeout(a.minuteur)
    setToast(null)
    if (a.action === 'send') {
      // Envoi refusé : le mail revient à l'écran pour ne pas le perdre.
      api.envoyer(ecoleId, a.de, a.brouillon, a.fichiers).catch((e) => {
        setEcrire({ brouillon: a.brouillon, fichiers: a.fichiers, de: a.de })
        echec(e)
      })
      return
    }
    api
      .cocher(ecoleId, a.boite, a.dossier, a.uids, a.action)
      .then(() => api.signalerNonLus())
      .catch((e) => {
        setCachés((c) => new Set([...c].filter((u) => !a.uids.includes(u))))
        echec(e)
      })
  }, [ecoleId, echec])

  // Quitter l'écran n'annule pas : la demande part tout de suite.
  useEffect(() => envoyer, [envoyer])

  function ranger(uids, action) {
    envoyer()
    const d = dossier
    setCachés((c) => new Set([...c, ...uids]))
    setCoches(new Set())
    setOuvert(null)
    attente.current = { boite: boite.id, dossier: d, uids, action, minuteur: setTimeout(envoyer, ANNULER_MS) }
    setToast(uids.length > 1 ? `${RANGE[action]} (${uids.length})` : RANGE[action])
  }

  // Envoyer : l'écran se ferme, le mail part au bout de 10 s (§8).
  function envoyerPlusTard(brouillon, fichiers, de) {
    envoyer()
    setEcrire(null)
    attente.current = { action: 'send', brouillon, fichiers, de, minuteur: setTimeout(envoyer, ANNULER_MS) }
    setToast(RANGE.send)
  }

  function annuler() {
    const a = attente.current
    if (!a) return
    clearTimeout(a.minuteur)
    attente.current = null
    if (a.action === 'send') {
      setToast(null)
      setEcrire({ brouillon: a.brouillon, fichiers: a.fichiers, de: a.de })
      return
    }
    setCachés((c) => new Set([...c].filter((u) => !a.uids.includes(u))))
    setToast(null)
  }

  function changer(uids, changes) {
    setMails((liste) => liste.map((m) => (uids.includes(m.uid) ? { ...m, ...changes } : m)))
  }

  async function marquer(uids, lu) {
    setCoches(new Set())
    changer(uids, { seen: lu })
    try {
      await api.cocher(ecoleId, boite.id, dossier, uids, lu ? 'read' : 'unread')
      api.signalerNonLus()
    } catch (e) {
      changer(uids, { seen: !lu })
      echec(e)
    }
  }

  async function suivre(mail) {
    changer([mail.uid], { starred: !mail.starred })
    try {
      await api.drapeaux(ecoleId, boite.id, dossier, mail.uid, { starred: !mail.starred })
    } catch (e) {
      changer([mail.uid], { starred: mail.starred })
      echec(e)
    }
  }

  async function plusAnciens() {
    const dernier = mails[mails.length - 1]
    try {
      const r = await api.lister(ecoleId, boite.id, dossier, { avant: dernier.uid, recherche: cherche })
      setMails((liste) => [...liste, ...r.messages])
      setEncore(r.hasMore)
    } catch (e) {
      echec(e)
    }
  }

  function basculer(uid) {
    setCoches((c) => {
      const n = new Set(c)
      if (n.has(uid)) n.delete(uid)
      else n.add(uid)
      return n
    })
  }

  const toastPortail =
    toast &&
    createPortal(
      <div className="admin-groupes__toast" role="status">
        <span>{toast}</span>
        <button type="button" onClick={annuler}>
          Annuler
        </button>
      </div>,
      document.body,
    )

  const ecran = ecrire && (
    <Ecrire
      ecoleId={ecoleId}
      brouillon={ecrire.brouillon}
      fichiersInitiaux={ecrire.fichiers}
      boites={boites}
      de={ecrire.de ?? boite.id}
      onFermer={() => setEcrire(null)}
      onEnvoyer={envoyerPlusTard}
    />
  )

  if (ouvert) {
    return (
      <>
        <UnMail
          ecoleId={ecoleId}
          dossier={dossier}
          uid={ouvert}
          boite={boite.id}
          adresseBoite={boite.address}
          onRetour={() => {
            setOuvert(null)
            charger(true)
          }}
          onRanger={(action) => ranger([ouvert], action)}
          onNonLu={() => {
            changer([ouvert], { seen: false })
            setOuvert(null)
          }}
          onSuivi={(starred) => changer([ouvert], { starred })}
          onErreur={echec}
          onEcrire={(brouillon) => setEcrire({ brouillon, fichiers: [] })}
        />
        {ecran}
        {toastPortail}
      </>
    )
  }

  const visibles = (mails ?? []).filter((m) => !cachés.has(m.uid))
  const choisis = [...coches]
  const dansCorbeille = dossier === 'trash' || dossier === 'spam'
  const envoyes = dossier === 'sent' || dossier === 'drafts'

  return (
    <div className="mail__boite">
      {choisis.length > 0 ? (
        <div className="mail__selection">
          <button type="button" className="icon-btn" aria-label="Tout décocher" onClick={() => setCoches(new Set())}>
            <Icon name="x" />
          </button>
          <strong>{choisis.length}</strong>
          {dansCorbeille ? (
            <>
              {dossier === 'spam' && (
                <button type="button" className="btn btn--secondary" onClick={() => ranger(choisis, 'inbox')}>
                  Ce n'est pas du spam
                </button>
              )}
              <button type="button" className="btn btn--danger" onClick={() => ranger(choisis, 'delete')}>
                Supprimer définitivement
              </button>
            </>
          ) : (
            <>
              <button type="button" className="icon-btn" aria-label="Archiver" onClick={() => ranger(choisis, 'archive')}>
                <Icon name="archive" />
              </button>
              <button type="button" className="icon-btn" aria-label="Corbeille" onClick={() => ranger(choisis, 'trash')}>
                <Icon name="trash" />
              </button>
              <button type="button" className="icon-btn" aria-label="Marquer comme non lu" onClick={() => marquer(choisis, false)}>
                <Icon name="mail" />
              </button>
              <MenuEntete
                label="Plus d'actions"
                actions={[
                  { label: 'Marquer comme lu', icon: 'check', onClick: () => marquer(choisis, true) },
                  { label: 'Spam', icon: 'x', onClick: () => ranger(choisis, 'spam') },
                ]}
              />
            </>
          )}
        </div>
      ) : (
        menuBoite
      )}

      <form
        className="mail__outils"
        role="search"
        onSubmit={(e) => {
          e.preventDefault()
          setCoches(new Set())
          setCherche(recherche.trim())
        }}
      >
        <select aria-label="Dossier" value={dossier} onChange={(e) => {
            setCoches(new Set())
            setDossier(e.target.value)
          }}>
          {dossiers.map((d) => (
            <option key={d.key} value={d.key}>
              {d.label}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Rechercher"
          aria-label="Rechercher dans les mails"
          value={recherche}
          onChange={(e) => {
            setRecherche(e.target.value)
            if (!e.target.value) setCherche('')
          }}
        />
      </form>

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {mails === null && !erreur && <p className="mail__discret">Chargement…</p>}
      {mails !== null && visibles.length === 0 && <p className="mail__vide">Aucun mail ici.</p>}
      <ul className="mail__liste">
        {visibles.map((m) => {
          const qui = envoyes ? `À : ${m.to.map(nom).join(', ')}` : m.from.map(nom).join(', ')
          const coche = coches.has(m.uid)
          return (
            <li key={m.uid} className={`mail__ligne-mail${m.seen ? '' : ' mail__ligne-mail--non-lu'}${coche ? ' mail__ligne-mail--coche' : ''}`}>
              <button
                type="button"
                className="mail__rond"
                aria-label={`${coche ? 'Décocher' : 'Cocher'} le mail « ${m.subject || 'sans objet'} »`}
                onClick={() => basculer(m.uid)}
              >
                {coche ? <Icon name="check" /> : initiales(envoyes ? nom(m.to[0]) : nom(m.from[0]))}
              </button>
              <button
                type="button"
                className="mail__resume"
                onClick={() => (choisis.length ? basculer(m.uid) : setOuvert(m.uid))}
              >
                <span className="mail__l1">
                  <span className="mail__qui">{qui || '(inconnu)'}</span>
                  <span className="mail__date">{dateListe(m.date)}</span>
                </span>
                <span className="mail__objet">
                  {m.hasAttachments && <Icon name="paperclip" size={16} />}
                  {m.subject || '(sans objet)'}
                </span>
                <span className="mail__apercu">{m.snippet}</span>
              </button>
              <button
                type="button"
                className={`mail__etoile${m.starred ? ' mail__etoile--oui' : ''}`}
                aria-pressed={m.starred}
                aria-label={m.starred ? 'Ne plus suivre' : 'Suivre'}
                onClick={() => suivre(m)}
              >
                <Icon name="star" />
              </button>
            </li>
          )
        })}
      </ul>
      {encore && (
        <button type="button" className="mail__plus" onClick={plusAnciens}>
          Mails plus anciens
        </button>
      )}
      <button type="button" className="fab mail__nouveau" onClick={() => setEcrire({ brouillon: NOUVEAU, fichiers: [] })}>
        <Icon name="edit" /> Nouveau message
      </button>
      {ecran}
      {toastPortail}
    </div>
  )
}
