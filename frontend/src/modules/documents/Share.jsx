import { useEffect, useRef, useState } from 'react'
import { levelLabel } from './format.js'
import { Cadenas } from './icons.jsx'

// « Qui a accès ? » (spec documents.md §4.4 bis) : comme le dossier, ou
// restreint ; les accès hérités grisés ; « En plus » avec Voir | Modifier ;
// chaque changement s'applique tout de suite, avec Annuler pendant 10 s.

function Avatar({ p }) {
  if (p.type === 'group') return <div className="dx-av">{p.id === 'role:admin' ? '★' : '👥'}</div>
  return <div className="dx-av">{(p.label ?? '?').slice(0, 1).toUpperCase()}</div>
}

export default function Share({ api, item, onClose, onToast }) {
  const [acces, setAcces] = useState(null)
  const [erreur, setErreur] = useState('')
  const [ajout, setAjout] = useState(false)
  const [recherche, setRecherche] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const champ = useRef(null)

  useEffect(() => {
    api.getAccess(item.id).then(setAcces, (e) => setErreur(e.message))
  }, [api, item.id])

  useEffect(() => {
    if (!ajout) return undefined
    let annule = false
    const t = setTimeout(() => {
      api.principals(recherche).then((liste) => !annule && setSuggestions(liste), () => {})
    }, 200)
    return () => {
      annule = true
      clearTimeout(t)
    }
  }, [api, ajout, recherche])

  useEffect(() => {
    if (ajout) champ.current?.focus()
  }, [ajout])

  const entrees = (a) => a.direct.map((d) => ({ type: d.type, id: d.id, level: d.level }))

  async function appliquer(restricted, entries, message) {
    const avant = acces
    setErreur('')
    try {
      const apres = await api.setAccess(item.id, restricted, entries)
      setAcces(apres)
      onToast(message, async () => {
        const remis = await api.setAccess(item.id, avant.restricted, entrees(avant))
        setAcces(remis)
      })
    } catch (e) {
      setErreur(e.message)
    }
  }

  if (!acces) {
    return (
      <div className="dx-panel" role="dialog" aria-label="Qui a accès ?">
        <div className="dx-top">
          <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
          <h2>Qui a accès ?</h2>
        </div>
        <div className="dx-body">{erreur ? <p className="dx-error">{erreur}</p> : <p className="dx-muted">Chargement…</p>}</div>
      </div>
    )
  }

  if (acces.personal) {
    return (
      <div className="dx-panel" role="dialog" aria-label="Qui a accès ?">
        <div className="dx-top">
          <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
          <h2>Qui a accès ?</h2>
        </div>
        <div className="dx-body">
          <p className="dx-note">
            Votre espace Personnel n’est visible que par vous. Pour partager « {item.name} », déplacez-le dans Privé
            ou Public.
          </p>
        </div>
      </div>
    )
  }

  const gerer = acces.can_manage
  const restreint = acces.restricted
  const dejaLa = new Set(acces.direct.map((d) => `${d.type}:${d.id}`))

  return (
    <div className="dx-panel" role="dialog" aria-label="Qui a accès ?">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2>Qui a accès ?</h2>
      </div>
      <div className="dx-body">
        <div className="dx-muted dx-share__name">« {item.name} »</div>
        {erreur && <p className="dx-error">{erreur}</p>}

        <button
          type="button"
          className={`dx-opt${!restreint ? ' dx-opt--on' : ''}`}
          disabled={!acces.can_restrict}
          onClick={() => restreint && appliquer(false, entrees(acces), 'Accès comme le dossier')}
        >
          <span className="dx-opt__rad" />
          <span>
            <span className="dx-opt__t">Comme le dossier « {acces.inherited_from} »</span>
            <span className="dx-opt__d">Ceux qui ont accès au dossier au-dessus ont accès ici. Vous pouvez en ajouter.</span>
          </span>
        </button>
        <button
          type="button"
          className={`dx-opt${restreint ? ' dx-opt--on' : ''}`}
          disabled={!acces.can_restrict}
          onClick={() => !restreint && appliquer(true, entrees(acces), item.kind === 'folder' ? 'Dossier restreint' : 'Fichier restreint')}
        >
          <span className="dx-opt__rad" />
          <span>
            <span className="dx-opt__t">
              <Cadenas className="dx-cadenas-texte" /> Restreint
            </span>
            <span className="dx-opt__d">
              Seulement les personnes ci-dessous, et les admins.
              {!acces.can_restrict && ' Réservé aux admins.'}
            </span>
          </span>
        </button>

        <div className="dx-sec">{restreint ? 'Ont toujours accès' : 'Ont accès par le dossier'}</div>
        {acces.inherited.map((p) => (
          <div key={`${p.type}:${p.id}`} className="dx-who dx-who--inh">
            <Avatar p={p} />
            <div className="dx-meta">
              <div className="dx-n">{p.label}</div>
              <div className="dx-s">{p.from === 'toujours' ? 'toujours' : p.detail || p.from}</div>
            </div>
            <span className="dx-lvl">{levelLabel(p.level)}</span>
          </div>
        ))}

        <div className="dx-sec">{restreint ? 'Seulement' : 'En plus'}</div>
        {acces.direct.length === 0 && <p className="dx-muted">Personne pour l’instant.</p>}
        {acces.direct.map((p, k) => (
          <div key={`${p.type}:${p.id}`} className="dx-who">
            <Avatar p={p} />
            <div className="dx-meta">
              <div className="dx-n">{p.label}</div>
              <div className="dx-s">{p.detail}</div>
            </div>
            {gerer ? (
              <>
                <div className="dx-lv" role="group" aria-label={`Accès de ${p.label}`}>
                  {[
                    ['view', 'Voir'],
                    ['edit', 'Modifier'],
                  ].map(([niveau, libelle]) => (
                    <button
                      key={niveau}
                      type="button"
                      className={p.level === niveau ? 'on' : ''}
                      aria-pressed={p.level === niveau}
                      onClick={() => {
                        if (p.level === niveau) return
                        const liste = entrees(acces)
                        liste[k] = { ...liste[k], level: niveau }
                        appliquer(restreint, liste, `${p.label} : ${niveau === 'edit' ? 'peut modifier' : 'peut voir'}`)
                      }}
                    >
                      {libelle}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="dx-rm"
                  aria-label={`Retirer ${p.label}`}
                  onClick={() => appliquer(restreint, entrees(acces).filter((_, i) => i !== k), `${p.label} retiré`)}
                >
                  ✕
                </button>
              </>
            ) : (
              <span className="dx-lvl">{levelLabel(p.level)}</span>
            )}
          </div>
        ))}

        {gerer ? (
          <>
            <button type="button" className="dx-add" onClick={() => setAjout((v) => !v)}>
              ＋ Ajouter une personne ou un groupe
            </button>
            {ajout && (
              <div className="dx-sugg">
                <input
                  ref={champ}
                  className="dx-input"
                  placeholder="Nom, cours, rôle…"
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                />
                <div className="dx-sugg__list">
                  {suggestions
                    .filter((p) => p.id !== 'role:admin' && !dejaLa.has(`${p.type}:${p.id}`))
                    .map((p) => (
                      <button
                        key={`${p.type}:${p.id}`}
                        type="button"
                        onClick={() => {
                          setAjout(false)
                          setRecherche('')
                          appliquer(restreint, [...entrees(acces), { type: p.type, id: p.id, level: 'view' }], `${p.label} ajouté : peut voir`)
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
              </div>
            )}
          </>
        ) : (
          <p className="dx-note">Seuls les admins changent les accès.</p>
        )}
      </div>
    </div>
  )
}
