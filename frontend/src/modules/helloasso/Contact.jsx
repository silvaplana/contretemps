import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Modal from '../../components/Modal.jsx'
import * as api from './api.js'

// Contact et résiliation depuis le tableau des adhérents
// (spec/modules/helloasso.md §7.6, §7.7, maquette « Adhérents ASC »), repris
// de Sambo Admin : ✉ Mail, 💬 SMS (téléphone seulement), Résilier.

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })

// Le SMS part de l'appli SMS du téléphone : pas de bouton sur ordinateur.
const surTelephone = () => window.matchMedia?.('(pointer: coarse)').matches ?? false

const remplir = (texte, eleve) => texte.replaceAll('{prénom}', eleve.prenom).replaceAll('{nom}', eleve.nom)

// Le choix d'un message préenregistré, « Garder ce message » et « Retirer ».
function useMessages(ecoleId, kind) {
  const [liste, setListe] = useState([])
  useEffect(() => {
    api
      .messages(ecoleId, kind)
      .then(setListe)
      .catch(() => setListe([]))
  }, [ecoleId, kind])
  return [liste, setListe]
}

function Preenregistres({ ecoleId, kind, liste, setListe, choisi, onChoisir, sujet, texte }) {
  const [erreur, setErreur] = useState('')
  async function garder() {
    setErreur('')
    try {
      const liste = await api.garderMessage(ecoleId, kind, sujet, texte)
      setListe(liste)
      const garde = liste.find((t) => t.body === texte.trim() && (kind === 'sms' || t.subject === sujet.trim()))
      if (garde) onChoisir(String(garde.id))
    } catch (e) {
      setErreur(e.message)
    }
  }
  async function retirer() {
    setListe(await api.retirerMessage(ecoleId, kind, Number(choisi)))
    onChoisir('')
  }
  return (
    <>
      <label className="contact__lab" htmlFor={`${kind}-modele`}>
        Message préenregistré
      </label>
      <select
        id={`${kind}-modele`}
        className="field-input"
        value={choisi}
        onChange={(e) => onChoisir(e.target.value)}
      >
        <option value="">Aucun</option>
        {liste.map((t) => (
          <option key={t.id} value={t.id}>
            {kind === 'mail' ? t.subject : t.body.slice(0, 40)}
          </option>
        ))}
      </select>
      <div className="contact__liens">
        {texte.trim() && (
          <button type="button" className="btn btn--link" onClick={garder}>
            Garder ce message
          </button>
        )}
        {choisi && (
          <button type="button" className="btn btn--link" onClick={retirer}>
            Retirer ce message préenregistré
          </button>
        )}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </>
  )
}

function MailModal({ ecoleId, eleve, ligne, onClose, onEnvoye }) {
  const [liste, setListe] = useMessages(ecoleId, 'mail')
  const [choisi, setChoisi] = useState('')
  const [sujet, setSujet] = useState('')
  const [texte, setTexte] = useState('')
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)

  function choisir(id) {
    setChoisi(id)
    const t = liste.find((x) => String(x.id) === id)
    if (t) {
      setSujet(remplir(t.subject, eleve))
      setTexte(remplir(t.body, eleve))
    }
  }

  async function envoyer() {
    setErreur('')
    setEnvoi(true)
    try {
      await api.envoyerMail(ecoleId, eleve.id, sujet, texte)
      onEnvoye('Mail envoyé')
    } catch (e) {
      setErreur(e.message)
      setEnvoi(false)
    }
  }

  const deja = ligne?.mails ?? 0
  return (
    <Modal
      title={`Mail à ${eleve.prenom} ${eleve.nom}`}
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={envoyer}
            disabled={envoi || !sujet.trim() || !texte.trim()}
          >
            {envoi ? 'Envoi…' : 'Envoyer'}
          </button>
        </div>
      }
    >
      <Preenregistres
        ecoleId={ecoleId}
        kind="mail"
        liste={liste}
        setListe={setListe}
        choisi={choisi}
        onChoisir={choisir}
        sujet={sujet}
        texte={texte}
      />
      <label className="contact__lab" htmlFor="mail-objet">
        Objet
      </label>
      <input id="mail-objet" className="field-input" value={sujet} onChange={(e) => setSujet(e.target.value)} />
      <label className="contact__lab" htmlFor="mail-message">
        Message
      </label>
      <textarea
        id="mail-message"
        className="field-input contact__message"
        value={texte}
        onChange={(e) => setTexte(e.target.value)}
      />
      <p className="muted">
        {deja
          ? `${deja} mail${deja > 1 ? 's' : ''} déjà envoyé${deja > 1 ? 's' : ''} à cette personne.`
          : 'Premier mail à cette personne.'}{' '}
        L’école est en copie et reçoit les réponses.
      </p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

function SmsModal({ ecoleId, eleve, onClose, onEnvoye }) {
  const [liste, setListe] = useMessages(ecoleId, 'sms')
  const [choisi, setChoisi] = useState('')
  const [texte, setTexte] = useState('')
  const [erreur, setErreur] = useState('')

  function choisir(id) {
    setChoisi(id)
    const t = liste.find((x) => String(x.id) === id)
    if (t) setTexte(remplir(t.body, eleve))
  }

  async function ouvrir() {
    setErreur('')
    try {
      const { phone } = await api.preparerSms(ecoleId, eleve.id, texte)
      window.location.href = `sms:${phone}?body=${encodeURIComponent(texte)}`
      onEnvoye('SMS préparé dans ton téléphone')
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <Modal
      title={`SMS à ${eleve.prenom} ${eleve.nom}`}
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--secondary" onClick={onClose}>
            Annuler
          </button>
          <button type="button" className="btn btn--primary" onClick={ouvrir} disabled={!texte.trim()}>
            Ouvrir mes SMS
          </button>
        </div>
      }
    >
      <Preenregistres
        ecoleId={ecoleId}
        kind="sms"
        liste={liste}
        setListe={setListe}
        choisi={choisi}
        onChoisir={choisir}
        sujet=""
        texte={texte}
      />
      <label className="contact__lab" htmlFor="sms-message">
        Message
      </label>
      <textarea
        id="sms-message"
        className="field-input contact__message"
        value={texte}
        onChange={(e) => setTexte(e.target.value)}
      />
      <p className="muted">Le SMS part de ton téléphone : l’appli sait qu’il a été préparé, pas qu’il est parti.</p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Ici pas d'« Annuler 10 s » : HelloAsso ne revient pas en arrière (§7.7).
function ResilierModal({ ecoleId, eleve, onClose, onEnvoye }) {
  const [apercu, setApercu] = useState(null)
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)
  useEffect(() => {
    api
      .resiliation(ecoleId, eleve.id)
      .then(setApercu)
      .catch((e) => setErreur(e.message))
  }, [ecoleId, eleve.id])

  async function resilier() {
    setErreur('')
    setEnvoi(true)
    try {
      await api.resilier(ecoleId, eleve.id)
      onEnvoye(apercu.members.length > 1 ? 'Adhésions résiliées sur HelloAsso' : 'Adhésion résiliée sur HelloAsso')
    } catch (e) {
      setErreur(e.message)
      setEnvoi(false)
    }
  }

  const n = apercu?.members.length ?? 0
  return (
    <Modal
      title="Résilier l’adhésion"
      onClose={onClose}
      footer={
        <div className="contact__pied">
          <button type="button" className="btn btn--primary" onClick={onClose}>
            Annuler
          </button>
          {apercu && !apercu.cancelled && (
            <button type="button" className="btn btn--danger" onClick={resilier} disabled={envoi}>
              {envoi ? 'Résiliation…' : n > 1 ? `Résilier les ${n} adhésions` : 'Résilier l’adhésion'}
            </button>
          )}
        </div>
      }
    >
      {apercu && (
        <>
          <p>
            HelloAsso résilie une <strong>commande entière</strong>, pas une personne. Celle-ci contient{' '}
            {n > 1 ? `${n} adhérents, qui seront tous résiliés` : 'un seul adhérent'} :
          </p>
          <ul>
            {apercu.members.map((m, i) => (
              <li key={i}>
                <strong>
                  {m.first_name} {m.last_name}
                </strong>
                , {euros(m.amount)}
              </li>
            ))}
          </ul>
          <p className="contact__alerte">
            <strong>{euros(apercu.paid)} déjà encaissés ne seront pas remboursés.</strong> Le remboursement se fait
            dans l’espace HelloAsso du club.
          </p>
          <p>
            {apercu.scheduled_count
              ? `${apercu.scheduled_count} échéance${apercu.scheduled_count > 1 ? 's' : ''} à venir (${euros(apercu.scheduled)}) ${apercu.scheduled_count > 1 ? 'seront annulées' : 'sera annulée'}.`
              : 'Aucune échéance à venir.'}
          </p>
          <p>
            <strong>Cette action est définitive :</strong> HelloAsso ne permet pas de revenir en arrière.
          </p>
        </>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Le petit message du bas après un envoi, 4 s.
function useToast() {
  const [texte, setTexte] = useState(null)
  const minuteur = useRef(null)
  useEffect(() => () => clearTimeout(minuteur.current), [])
  const montrer = (t) => {
    clearTimeout(minuteur.current)
    setTexte(t)
    minuteur.current = setTimeout(() => setTexte(null), 4000)
  }
  const toast =
    texte &&
    createPortal(
      <div className="admin-groupes__toast" role="status">
        <span>{texte}</span>
      </div>,
      document.body,
    )
  return [toast, montrer]
}

// Les écrans hors du tableau (portail) : un clic dedans n'ouvre pas la fiche.
const dehors = (ecran) => createPortal(ecran, document.body)

// Colonne « Contact » : ✉ Mail et 💬 SMS avec leur compteur.
export function CelluleContact({ ecoleId, eleve, ligne, relire }) {
  const [ouvert, setOuvert] = useState(null) // null | 'mail' | 'sms'
  const [toast, montrer] = useToast()
  if (!ligne) return null
  const fini = (texte) => {
    setOuvert(null)
    montrer(texte)
    relire?.()
  }
  const compteur = (n) => (n ? <span className="contact__compteur">{n}</span> : null)
  return (
    <div className="contact__boutons" onClick={(e) => e.stopPropagation()}>
      <button type="button" className="btn btn--secondary" onClick={() => setOuvert('mail')}>
        ✉ Mail{compteur(ligne.mails)}
      </button>
      {ligne.has_phone && surTelephone() && (
        <button type="button" className="btn btn--secondary" onClick={() => setOuvert('sms')}>
          💬 SMS{compteur(ligne.sms)}
        </button>
      )}
      {ouvert === 'mail' &&
        dehors(
          <MailModal ecoleId={ecoleId} eleve={eleve} ligne={ligne} onClose={() => setOuvert(null)} onEnvoye={fini} />,
        )}
      {ouvert === 'sms' &&
        dehors(<SmsModal ecoleId={ecoleId} eleve={eleve} onClose={() => setOuvert(null)} onEnvoye={fini} />)}
      {toast}
    </div>
  )
}

// Colonne « Adhésion » : « Résilier » (Accès au Financier) ou « Résiliée ».
export function CelluleAdhesion({ ecoleId, eleve, ligne, relire }) {
  const [ouvert, setOuvert] = useState(false)
  const [toast, montrer] = useToast()
  if (!ligne) return null
  return (
    <div onClick={(e) => e.stopPropagation()}>
      {ligne.cancelled ? (
        <span className="muted">Résiliée</span>
      ) : (
        ligne.can_cancel && (
          <button type="button" className="btn btn--danger" onClick={() => setOuvert(true)}>
            Résilier
          </button>
        )
      )}
      {ouvert &&
        dehors(
          <ResilierModal
            ecoleId={ecoleId}
            eleve={eleve}
            onClose={() => setOuvert(false)}
            onEnvoye={(texte) => {
              setOuvert(false)
              montrer(texte)
              relire?.()
            }}
          />,
        )}
      {toast}
    </div>
  )
}
