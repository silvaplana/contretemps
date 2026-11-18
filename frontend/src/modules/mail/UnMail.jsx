import { useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
import * as api from './api.js'
import { brouillon } from './brouillon.js'
import { adresse, dateComplete, initiales, nom, taille } from './format.js'

// Un mail (spec/modules/mail.md §6) : ← retour, Archiver, Corbeille, ⋮ ;
// objet, expéditeur, « À : », date, étoile, texte, pièces jointes. L'ouvrir
// le marque lu. En bas : Répondre (bouton principal) et Transférer ; ⋮ :
// Répondre à tous (§7).

export default function UnMail({ ecoleId, dossier, uid, adresseBoite, onRetour, onRanger, onNonLu, onSuivi, onErreur, onEcrire }) {
  const [mail, setMail] = useState(null)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let actif = true
    api.lire(ecoleId, dossier, uid).then(
      (m) => {
        if (!actif) return
        setMail(m)
        api.signalerNonLus()
      },
      (e) => {
        if (!actif) return
        if (e.status === 409) onErreur(e)
        else setErreur(e.message)
      },
    )
    return () => {
      actif = false
    }
    // onErreur change à chaque rendu du parent : seul le mail compte.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId, dossier, uid])

  async function suivre() {
    const starred = !mail.starred
    setMail({ ...mail, starred })
    onSuivi(starred)
    try {
      await api.drapeaux(ecoleId, dossier, uid, { starred })
    } catch (e) {
      setMail({ ...mail, starred: !starred })
      onSuivi(!starred)
      onErreur(e)
    }
  }

  async function nonLu() {
    try {
      await api.drapeaux(ecoleId, dossier, uid, { seen: false })
      api.signalerNonLus()
      onNonLu()
    } catch (e) {
      onErreur(e)
    }
  }

  async function piece(p) {
    try {
      await api.telecharger(ecoleId, dossier, uid, p)
    } catch (e) {
      onErreur(e)
    }
  }

  const corbeille = dossier === 'trash'
  const spam = dossier === 'spam'
  const ecrire = (mode) => onEcrire(brouillon(mode, mail, adresseBoite))
  const menu = [
    ...(mail ? [{ label: 'Répondre à tous', icon: 'reply', onClick: () => ecrire('replyAll') }] : []),
    { label: 'Marquer comme non lu', icon: 'mail', onClick: nonLu },
    spam
      ? { label: "Ce n'est pas du spam", icon: 'check', onClick: () => onRanger('inbox') }
      : { label: 'Spam', icon: 'x', onClick: () => onRanger('spam') },
  ]

  return (
    <article className="mail__un">
      <MenuEntete label="Plus d'actions" actions={menu} />
      <div className="mail__barre">
        <button type="button" className="icon-btn" aria-label="Retour" onClick={onRetour}>
          <Icon name="chevronLeft" />
        </button>
        <span className="mail__espace" />
        {corbeille || spam ? (
          <button type="button" className="btn btn--danger" onClick={() => onRanger('delete')}>
            Supprimer définitivement
          </button>
        ) : (
          <>
            <button type="button" className="icon-btn" aria-label="Archiver" onClick={() => onRanger('archive')}>
              <Icon name="archive" />
            </button>
            <button type="button" className="icon-btn" aria-label="Corbeille" onClick={() => onRanger('trash')}>
              <Icon name="trash" />
            </button>
          </>
        )}
      </div>

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!mail && !erreur && <p className="mail__discret">Chargement…</p>}
      {mail && (
        <>
          <h2 className="mail__sujet">{mail.subject || '(sans objet)'}</h2>
          <div className="mail__entete">
            <span className="mail__rond" aria-hidden="true">
              {initiales(nom(mail.from[0]))}
            </span>
            <div className="mail__de">
              <strong>{mail.from.map(nom).join(', ')}</strong>
              <span className="mail__discret">{mail.from[0]?.address}</span>
              <span className="mail__discret">
                À : {mail.to.map(adresse).join(', ') || '—'}
                {mail.cc.length > 0 && <> · Cc : {mail.cc.map(adresse).join(', ')}</>}
              </span>
              <span className="mail__discret">{dateComplete(mail.date)}</span>
            </div>
            <button
              type="button"
              className={`mail__etoile${mail.starred ? ' mail__etoile--oui' : ''}`}
              aria-pressed={mail.starred}
              aria-label={mail.starred ? 'Ne plus suivre' : 'Suivre'}
              onClick={suivre}
            >
              <Icon name="star" />
            </button>
          </div>
          {mail.html ? <CorpsHtml html={mail.html} /> : <pre className="mail__texte">{mail.text}</pre>}
          {mail.attachments.length > 0 && (
            <div className="mail__pieces">
              {mail.attachments.map((p) => (
                <button type="button" key={p.index} className="mail__piece" onClick={() => piece(p)}>
                  <Icon name="paperclip" />
                  <span>
                    {p.filename}
                    <small>{taille(p.size)}</small>
                  </span>
                </button>
              ))}
            </div>
          )}
          <div className="mail__repondre">
            <button type="button" className="btn btn--primary" onClick={() => ecrire('reply')}>
              <Icon name="reply" /> Répondre
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => ecrire('forward')}>
              <Icon name="forward" /> Transférer
            </button>
          </div>
        </>
      )}
    </article>
  )
}

// Corps HTML dans un cadre isolé, comme Sambo Admin : aucun script (sandbox
// sans allow-scripts), liens dans un nouvel onglet ; allow-same-origin sert
// seulement à mesurer la hauteur du contenu. Le mail garde le fond clair pour
// lequel il a été écrit.
const STYLE =
  'html,body{margin:0;background:#fff;color:#202124}body{padding:12px;font:16px/1.5 Arial,Helvetica,sans-serif;overflow-wrap:anywhere}img{max-width:100%;height:auto}table{max-width:100%}'

function CorpsHtml({ html }) {
  const cadre = useRef(null)
  const doc = `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: https: http:; style-src 'unsafe-inline' https:; font-src https: data:">
<base target="_blank"><style>${STYLE}</style></head><body>${html}</body></html>`

  function ajuster() {
    const el = cadre.current
    const body = el?.contentDocument?.body
    if (body) el.style.height = `${Math.max(body.offsetHeight, body.scrollHeight) + 4}px`
  }

  useEffect(() => {
    // Images chargées après coup : la hauteur change.
    const minuteurs = [400, 1500, 4000].map((d) => setTimeout(ajuster, d))
    return () => minuteurs.forEach(clearTimeout)
  }, [html])

  return (
    <iframe
      ref={cadre}
      className="mail__html"
      title="Contenu du mail"
      sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
      srcDoc={doc}
      onLoad={ajuster}
    />
  )
}
