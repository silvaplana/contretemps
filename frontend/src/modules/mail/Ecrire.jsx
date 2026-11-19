import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import ChampAdresses from './ChampAdresses.jsx'
import ChoisirAdherents from './ChoisirAdherents.jsx'
import { taille } from './format.js'

// Écrire (spec/modules/mail.md §7) : écran plein, « De : » l'adresse du club
// (au choix quand l'école a plusieurs boîtes, celle qu'on regarde d'abord, §4 bis),
// À, Cc, Cci (toujours affichés, Seb 18 novembre), Objet, message, pièces jointes (18 Mo au plus), Envoyer. Le
// mail part au bout des 10 s d'Annuler (§8, Boite.jsx).

const MAX = 18 * 1024 * 1024
const TITRES = { new: 'Nouveau message', reply: 'Répondre', replyAll: 'Répondre à tous', forward: 'Transférer' }

export default function Ecrire({ ecoleId, brouillon, fichiersInitiaux = [], boites, de, onFermer, onEnvoyer }) {
  const [deId, setDeId] = useState(de)
  const [contacts, setContacts] = useState([])
  const [to, setTo] = useState(brouillon.to)
  const [cc, setCc] = useState(brouillon.cc)
  const [bcc, setBcc] = useState(brouillon.bcc ?? '')
  const [subject, setSubject] = useState(brouillon.subject)
  const [body, setBody] = useState(brouillon.body)
  const [fichiers, setFichiers] = useState(fichiersInitiaux)
  // « Écrire aux adhérents » (§7 bis) : le choix fait, ou null ; un mail
  // chacun par Brevo, sans Cc, Cci ni pièce jointe.
  const [adherents, setAdherents] = useState(brouillon.adherents ?? null)
  const [choisir, setChoisir] = useState(false)
  const [erreur, setErreur] = useState(null)
  const texte = useRef(null)
  const total = fichiers.reduce((s, f) => s + f.size, 0)

  useEffect(() => {
    api.contacts(ecoleId, deId).then((r) => setContacts(r.contacts), () => null)
  }, [ecoleId, deId])

  // Réponse : curseur tout en haut, au-dessus du mail cité.
  useEffect(() => {
    if (brouillon.mode === 'reply' || brouillon.mode === 'replyAll') {
      texte.current?.focus()
      texte.current?.setSelectionRange(0, 0)
    }
  }, [brouillon.mode])

  function envoyer(e) {
    e.preventDefault()
    if (adherents) {
      if (!body.trim()) {
        setErreur('Écrivez le message')
        return
      }
      onEnvoyer({ ...brouillon, to: '', cc: '', bcc: '', subject, body, adherents }, [], deId)
      return
    }
    if (!to.trim() && !cc.trim() && !bcc.trim()) {
      setErreur('Indiquez à qui envoyer le mail')
      return
    }
    onEnvoyer({ ...brouillon, to, cc, bcc, subject, body }, fichiers, deId)
  }

  return createPortal(
    <div className="creer-saison" role="dialog" aria-label={TITRES[brouillon.mode]}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onFermer} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{TITRES[brouillon.mode]}</h2>
      </div>
      <form className="creer-saison__corps mail mail__ecrire" onSubmit={envoyer}>
        {boites.length > 1 ? (
          <label className="mail__champ-ligne">
            <span>De</span>
            <select value={deId} onChange={(e) => setDeId(Number(e.target.value))}>
              {boites.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} · {b.address}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <div className="mail__champ-ligne">
            <span>De</span>
            <span className="mail__discret">{boites.find((b) => b.id === deId)?.address}</span>
          </div>
        )}
        {adherents ? (
          <>
            <div className="mail__champ-ligne">
              <span>À</span>
              <span className="mail__adherents">
                <span>
                  {adherents.label}
                  {adherents.people != null && ` · ${adherents.people}`}
                </span>
                <button type="button" className="icon-btn" aria-label="Retirer" onClick={() => setAdherents(null)}>
                  <Icon name="x" />
                </button>
              </span>
            </div>
            <p className="mail__discret">
              Chacun reçoit son propre mail : personne ne voit l’adresse des autres. Les réponses arrivent dans cette
              boîte, et le mail est rangé dans ses Envoyés.
              {adherents.without > 0 &&
                ` ${adherents.without} personne${adherents.without > 1 ? 's n’ont' : ' n’a'} pas d’adresse mail.`}
            </p>
          </>
        ) : (
          <>
            <ChampAdresses
              label="À"
              value={to}
              onChange={setTo}
              contacts={contacts}
              autoFocus={brouillon.mode === 'new' || brouillon.mode === 'forward'}
            />
            {brouillon.mode === 'new' && (
              <button type="button" className="mail__lien-adherents" onClick={() => setChoisir(true)}>
                👥 Écrire à un groupe
              </button>
            )}
            <ChampAdresses label="Cc" value={cc} onChange={setCc} contacts={contacts} />
            <ChampAdresses label="Cci" value={bcc} onChange={setBcc} contacts={contacts} />
          </>
        )}
        <label className="mail__champ-ligne">
          <span>Objet</span>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <textarea
          ref={texte}
          className="mail__corps"
          aria-label="Message"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
        />

        {!adherents && (brouillon.forwardAttachments?.length > 0 || fichiers.length > 0) && (
          <div className="mail__pieces">
            {brouillon.forwardAttachments?.map((p) => (
              <span key={`t${p.index}`} className="mail__piece">
                <Icon name="paperclip" />
                <span>
                  {p.filename}
                  <small>{taille(p.size)}</small>
                </span>
              </span>
            ))}
            {fichiers.map((f, i) => (
              <span key={`${f.name}-${i}`} className="mail__piece">
                <Icon name="paperclip" />
                <span>
                  {f.name}
                  <small>{taille(f.size)}</small>
                </span>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Retirer ${f.name}`}
                  onClick={() => setFichiers((liste) => liste.filter((_, j) => j !== i))}
                >
                  <Icon name="x" />
                </button>
              </span>
            ))}
          </div>
        )}
        {total > MAX && <p className="login-screen__erreur">Pièces jointes trop lourdes : 18 Mo au total au maximum.</p>}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        {adherents && <p className="mail__discret">Pas de pièce jointe dans un mail à un groupe pour l’instant.</p>}
        {!adherents && (
          <label className="btn btn--secondary mail__joindre">
            <Icon name="paperclip" /> Joindre un fichier
            <input
              type="file"
              multiple
              hidden
              onChange={(e) => {
                const choisis = [...e.target.files]
                setFichiers((liste) => [...liste, ...choisis])
                e.target.value = ''
              }}
            />
          </label>
        )}
        <button type="submit" className="btn btn--primary btn--block mail__principal" disabled={!adherents && total > MAX}>
          {adherents
            ? adherents.people != null
              ? `Envoyer à ${adherents.people} personne${adherents.people > 1 ? 's' : ''}`
              : 'Envoyer au groupe'
            : 'Envoyer'}
        </button>
      </form>
      {choisir && (
        <ChoisirAdherents
          ecoleId={ecoleId}
          onFermer={() => setChoisir(false)}
          onChoix={(choix) => {
            setAdherents(choix)
            setFichiers([])
            setChoisir(false)
          }}
        />
      )}
    </div>,
    document.body,
  )
}
