import { useCallback, useEffect, useRef, useState } from 'react'

// Diffuser > Des personnes choisies (fichier-de-base.md §2.3) : un email par
// personne avec son lien personnel, puis le suivi envoyé / ouvert / répondu.
// En Validé : aux relecteurs seulement, choisis un par un, réponses d'essai ;
// en Officiel : aux cours, aux rôles, à qui l'on veut (décision de Seb du
// 16 octobre). Le récapitulatif s'affiche avant « Envoyer ».

function Avatar({ p }) {
  return <div className="dx-av">{p.type === 'group' ? '👥' : (p.label ?? '?').slice(0, 1).toUpperCase()}</div>
}

function etape(s) {
  if (s.status === 'failed') return { texte: 'Échec', classe: 'ad-suivi--ko', detail: s.error }
  if (s.status === 'pending') return { texte: 'En cours d’envoi', classe: '' }
  if (s.answered_at) return { texte: 'A répondu', classe: 'ad-suivi--ok' }
  if (s.opened_at) return { texte: 'A ouvert', classe: '' }
  return { texte: 'Envoyé', classe: '' }
}

export default function DiffuserChoisis({ file, api, onToast }) {
  const relecture = file.status === 'validated'
  const ouvert = file.status === 'validated' || file.status === 'official'
  const raison = !file.can_manage
    ? 'Un admin diffuse le fichier'
    : file.space === 'personal'
      ? 'Un fichier de l’espace Personnel ne se diffuse pas'
      : !ouvert
        ? 'Passez le fichier en Validé pour le faire relire, ou en Officiel pour l’envoyer à tous'
        : null

  const [choisis, setChoisis] = useState([])
  const [recherche, setRecherche] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [message, setMessage] = useState('')
  const [apercu, setApercu] = useState({ cle: '', recap: null, erreur: '' })
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [suivi, setSuivi] = useState(null)
  // Confirmation avant l'envoi, avec la liste nominative (Seb, 16 octobre).
  const [confirmer, setConfirmer] = useState(false)
  const champ = useRef(null)

  const recharger = useCallback(() => {
    if (!file.can_manage) return
    api.sends(file.id).then(setSuivi, () => {})
  }, [api, file.id, file.can_manage])

  useEffect(recharger, [recharger, file.status])

  // Pendant l'envoi (après la réponse du serveur), le suivi se met à jour.
  useEffect(() => {
    if (!suivi?.items.some((s) => s.status === 'pending')) return undefined
    const t = setTimeout(recharger, 1500)
    return () => clearTimeout(t)
  }, [suivi, recharger])

  useEffect(() => {
    if (raison) return undefined
    let annule = false
    const t = setTimeout(() => {
      api.principals(recherche).then((liste) => !annule && setSuggestions(liste), () => {})
    }, 200)
    return () => {
      annule = true
      clearTimeout(t)
    }
  }, [api, recherche, raison])

  // Le récapitulatif suit le choix.
  const cle = `${file.status}|${choisis.map((p) => `${p.type}:${p.id}`).join(',')}`
  useEffect(() => {
    if (!choisis.length) return undefined
    let annule = false
    api.sendPreview(file.id, choisis).then(
      (r) => !annule && setApercu({ cle, recap: r, erreur: '' }),
      (e) => !annule && setApercu({ cle, recap: null, erreur: e.message }),
    )
    return () => {
      annule = true
    }
  }, [api, file.id, cle, choisis])
  const recap = apercu.cle === cle ? apercu.recap : null
  const erreurApercu = apercu.cle === cle ? apercu.erreur : ''

  const dejaLa = new Set(choisis.map((p) => `${p.type}:${p.id}`))
  const proposes = suggestions.filter((p) => !dejaLa.has(`${p.type}:${p.id}`) && !(relecture && p.type === 'group')).slice(0, 8)

  async function envoyer() {
    setEnCours(true)
    setErreur('')
    try {
      const r = await api.send(file.id, choisis, message)
      onToast(`${r.sent} email${r.sent > 1 ? 's' : ''} en route`)
      setConfirmer(false)
      setChoisis([])
      setMessage('')
      recharger()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  const items = suivi?.items ?? []
  const repondu = items.filter((s) => s.answered_at).length

  return (
    <section className="ad-carte">
      <h3>{relecture ? 'Faire relire' : 'Des personnes choisies'}</h3>
      {raison ? (
        <p className="ad-raison">{raison}.</p>
      ) : (
        <>
          <p className="af-hint">
            {relecture
              ? 'Envoyez-le à quelques relecteurs (10 au plus) : chacun reçoit un email avec son lien. Leurs réponses sont des essais, elles ne comptent pas.'
              : 'Un email à chacun, avec son lien personnel : on répond sans compte, une seule réponse par personne (on peut la corriger).'}
          </p>
          {choisis.length > 0 && (
            <div className="ad-choisis">
              {choisis.map((p) => (
                <span key={`${p.type}:${p.id}`} className="ad-puce">
                  {p.label}
                  <button
                    type="button"
                    aria-label={`Retirer ${p.label}`}
                    onClick={() => setChoisis((x) => x.filter((q) => !(q.type === p.type && q.id === p.id)))}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="dx-sugg">
            <input
              ref={champ}
              className="dx-input"
              placeholder={relecture ? 'Nom d’un relecteur…' : 'Nom, cours, rôle…'}
              value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
            />
            {(recherche || choisis.length === 0) && proposes.length > 0 && (
              <div className="dx-sugg__list">
                {proposes.map((p) => (
                  <button
                    key={`${p.type}:${p.id}`}
                    type="button"
                    onClick={() => {
                      setChoisis((x) => [...x, { type: p.type, id: p.id, label: p.label }])
                      setRecherche('')
                      champ.current?.focus()
                    }}
                  >
                    <Avatar p={p} />
                    <span className="dx-meta">
                      <span className="dx-n">{p.label}</span>
                      <span className="dx-s">{p.detail}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {choisis.length > 0 && (
            <>
              <label className="ad-message">
                <span>Un mot en tête du mail (facultatif)</span>
                <textarea rows={2} maxLength={2000} value={message} onChange={(e) => setMessage(e.target.value)} />
              </label>
              {recap && (
                <div className="ad-recap">
                  {recap.count > 0 ? (
                    <>
                      <p>
                        Recevront un email{recap.test ? ' pour relecture' : ''} :{' '}
                        <strong>{recap.count} personne{recap.count > 1 ? 's' : ''}</strong>
                      </p>
                      <ul className="ad-destinataires">
                        {(recap.recipients ?? []).map((d) => (
                          <li key={d.email + d.name}>
                            <span className="ad-destinataires__nom">{d.name}</span>
                            <span className="ad-destinataires__email">{d.email}</span>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p>Personne n’a d’adresse email parmi les personnes choisies.</p>
                  )}
                  {recap.without_email.length > 0 && (
                    <p className="ad-raison">Sans adresse email, ne recevront rien : {recap.without_email.join(', ')}.</p>
                  )}
                  {!recap.available && <p className="ad-raison">L’envoi d’emails n’est pas configuré sur ce serveur.</p>}
                </div>
              )}
              {confirmer && recap ? (
                <div className="ad-attention">
                  <p>
                    <strong>
                      Envoyer « {file.name} » à {recap.count} personne{recap.count > 1 ? 's' : ''} ?
                    </strong>
                  </p>
                  <p>
                    Chacune reçoit un email avec son lien personnel
                    {recap.test ? ' ; ses réponses seront des essais' : ''}. Un email envoyé ne se reprend pas.
                  </p>
                  <div className="ad-boutons">
                    <button type="button" className="dx-btn" disabled={enCours} onClick={envoyer}>
                      {enCours ? 'Envoi…' : `Oui, envoyer à ${recap.count}`}
                    </button>
                    <button type="button" className="dx-btn dx-btn--ghost" disabled={enCours} onClick={() => setConfirmer(false)}>
                      Annuler
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  className="dx-btn"
                  disabled={!recap || recap.count === 0 || !recap.available}
                  onClick={() => setConfirmer(true)}
                >
                  Envoyer…
                </button>
              )}
            </>
          )}
          {(erreur || erreurApercu) && <p className="dx-error" role="alert">{erreur || erreurApercu}</p>}
        </>
      )}

      {items.length > 0 && (
        <div className="ad-suivi">
          <div className="dx-sec">
            Envoyés : {items.length} · {repondu} réponse{repondu > 1 ? 's' : ''}
          </div>
          {items.map((s) => {
            const e = etape(s)
            return (
              <div key={s.id} className="ad-suivi__ligne">
                <span className="ad-suivi__nom">
                  {s.name}
                  {s.trial ? <span className="ad-essai">essai</span> : s.test && <span className="ad-essai">relecture</span>}
                </span>
                <span className={`ad-suivi__etat ${e.classe}`} title={e.detail || s.email || ''}>{e.texte}</span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
