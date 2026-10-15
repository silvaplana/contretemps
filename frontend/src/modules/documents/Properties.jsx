import { useEffect, useRef, useState } from 'react'
import { StatusBadge } from './icons.jsx'
import { formatDate, formatSize, historyText, levelLabel } from './format.js'

// Propriétés (spec documents.md §6.3 bis) : Infos | Accès | Historique, un
// seul écran pour fichier et dossier. Les actions impossibles restent
// visibles, grisées, avec la raison.

const SPACE_LABELS = { public: 'Public', private: 'Privé', personal: 'Personnel' }

const YOU = {
  view: 'Vous pouvez ouvrir et télécharger.',
  edit: 'Vous pouvez modifier. Les accès, c’est les admins.',
  manage: 'Vous pouvez tout faire, y compris changer les accès.',
}

export default function Properties({ api, itemId, initialTab = 'Infos', onClose, onShare, onChanged, onDownload, onToast }) {
  const [tab, setTab] = useState(initialTab)
  const [d, setD] = useState(null)
  const [acces, setAcces] = useState(null)
  const [erreur, setErreur] = useState('')
  const fichier = useRef(null)

  async function recharger() {
    try {
      setD(await api.detail(itemId))
    } catch (e) {
      setErreur(e.message)
    }
  }

  useEffect(() => {
    let annule = false
    api.detail(itemId).then((x) => !annule && setD(x), (e) => !annule && setErreur(e.message))
    return () => {
      annule = true
    }
  }, [api, itemId])

  useEffect(() => {
    if (tab === 'Accès') api.getAccess(itemId).then(setAcces, () => {})
  }, [api, itemId, tab])

  async function statut(nouveau, message) {
    const avant = d.status
    setErreur('')
    try {
      await api.setStatus(itemId, nouveau)
      await recharger()
      onChanged()
      onToast(message, async () => {
        await api.setStatus(itemId, avant)
        await recharger()
        onChanged()
      })
    } catch (e) {
      setErreur(e.message)
    }
  }

  async function nouvelleVersion(f) {
    setErreur('')
    try {
      await api.newVersion(itemId, f)
      await recharger()
      onChanged()
      onToast('Nouvelle version envoyée')
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="dx-panel" role="dialog" aria-label="Propriétés">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2>Propriétés</h2>
      </div>
      <div className="dx-seg" role="tablist">
        {['Infos', 'Accès', 'Historique'].map((t) => (
          <button key={t} type="button" role="tab" aria-selected={t === tab} className={t === tab ? 'on' : ''} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>
      <div className="dx-body">
        {erreur && <p className="dx-error">{erreur}</p>}
        {!d && !erreur && <p className="dx-muted">Chargement…</p>}

        {d && tab === 'Infos' && (
          <>
            <div className="dx-kv"><span>Nom</span><span>{d.name}</span></div>
            <div className="dx-kv">
              <span>Emplacement</span>
              <span>{[SPACE_LABELS[d.space], ...d.path.map((p) => p.name)].join(' › ')}</span>
            </div>
            <div className="dx-kv"><span>Statut</span><span>{d.status ? <StatusBadge status={d.status} /> : '—'}</span></div>
            {d.kind === 'file' && <div className="dx-kv"><span>Taille</span><span>{formatSize(d.size)}</span></div>}
            {d.kind === 'folder' && <div className="dx-kv"><span>Contenu</span><span>{d.child_count} élément{d.child_count > 1 ? 's' : ''}</span></div>}
            <div className="dx-kv"><span>Créé</span><span>{[formatDate(d.created_at), d.created_by && `par ${d.created_by}`].filter(Boolean).join(' ')}</span></div>
            <div className="dx-kv"><span>Modifié</span><span>{[formatDate(d.updated_at), d.updated_by && `par ${d.updated_by}`].filter(Boolean).join(' ')}</span></div>
            {d.closed_period && <p className="dx-note">Cette saison est terminée : son dossier est en lecture seule.</p>}
            {!d.closed_period && d.frozen && d.status !== 'official' && <p className="dx-note">Il est dans un dossier officiel : il ne se modifie plus.</p>}

            {d.system_kind == null && !d.closed_period && (
              <div className="dx-statuts">
                {d.status !== 'draft' && d.status !== 'official' && (
                  <button type="button" className="dx-btn dx-btn--ghost" disabled={!d.can_edit} onClick={() => statut('draft', 'Passé en Brouillon')}>
                    Marquer en Brouillon
                  </button>
                )}
                {d.status !== 'validated' && d.status !== 'official' && (
                  <button type="button" className="dx-btn dx-btn--ghost" disabled={!d.can_manage} onClick={() => statut('validated', 'Passé en Validé')}>
                    Passer en Validé
                  </button>
                )}
                {d.status !== 'official' ? (
                  <button type="button" className="dx-btn dx-btn--ghost" disabled={!d.can_manage || d.frozen} onClick={() => statut('official', 'Passé en Officiel')}>
                    Passer en Officiel
                  </button>
                ) : (
                  <button type="button" className="dx-btn dx-btn--ghost" disabled={!d.can_manage} onClick={() => statut('validated', 'N’est plus officiel')}>
                    Retirer le statut Officiel
                  </button>
                )}
                {!d.can_manage && <p className="dx-muted dx-small">Valider ou rendre officiel : réservé aux admins.</p>}
              </div>
            )}

            {d.kind === 'file' && (
              <>
                <div className="dx-sec">Versions</div>
                {d.versions.map((v) => (
                  <div key={v.id} className="dx-h">
                    <span className="dx-h__d">v{v.number}</span>
                    <div>
                      {v.filename} · {formatSize(v.size)}
                      <div className="dx-muted dx-small">
                        {formatDate(v.created_at)} {v.created_by && `par ${v.created_by}`} {v.current && '· actuelle'}
                      </div>
                      <button type="button" className="dx-link" onClick={() => onDownload(d, v.current ? undefined : v)}>
                        Télécharger
                      </button>
                    </div>
                  </div>
                ))}
                <input
                  ref={fichier}
                  type="file"
                  hidden
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    e.target.value = ''
                    if (f) nouvelleVersion(f)
                  }}
                />
                <button type="button" className="dx-btn" disabled={!d.can_edit} onClick={() => fichier.current?.click()}>
                  Envoyer une nouvelle version
                </button>
              </>
            )}
          </>
        )}

        {d && tab === 'Accès' && (
          <>
            <div className="dx-you">
              <b>Vous : {levelLabel(d.level)}</b>
              <br />
              <span className="dx-muted dx-small">{d.closed_period ? 'Saison terminée : lecture seule.' : YOU[d.level]}</span>
            </div>
            {acces && !acces.personal && (
              <>
                {acces.direct.length > 0 && <div className="dx-sec">Sur {d.kind === 'folder' ? 'ce dossier' : 'ce fichier'}</div>}
                {acces.direct.map((p) => (
                  <div key={`${p.type}:${p.id}`} className="dx-who">
                    <div className="dx-av">{p.type === 'group' ? '👥' : p.label.slice(0, 1)}</div>
                    <div className="dx-meta"><div className="dx-n">{p.label}</div><div className="dx-s">{p.detail}</div></div>
                    <span className="dx-lvl">{levelLabel(p.level)}</span>
                  </div>
                ))}
                <div className="dx-sec">{acces.restricted ? '🔒 Restreint' : `Hérité de « ${acces.inherited_from} »`}</div>
                {acces.inherited.map((p) => (
                  <div key={`${p.type}:${p.id}`} className="dx-who dx-who--inh">
                    <div className="dx-av">{p.id === 'role:admin' ? '★' : '👥'}</div>
                    <div className="dx-meta"><div className="dx-n">{p.label}</div><div className="dx-s">{p.from === 'toujours' ? 'toujours' : p.detail}</div></div>
                    <span className="dx-lvl">{levelLabel(p.level)}</span>
                  </div>
                ))}
              </>
            )}
            {acces?.personal && <p className="dx-note">Espace Personnel : visible par vous seul.</p>}
            <button type="button" className="dx-btn" onClick={() => onShare(d)}>
              {d.can_manage ? 'Modifier les accès' : 'Voir qui a accès'}
            </button>
          </>
        )}

        {d && tab === 'Historique' && (
          <>
            {d.history.length === 0 && <p className="dx-muted">Rien pour l’instant.</p>}
            {d.history.map((h, i) => (
              <div key={i} className="dx-h">
                <span className="dx-h__d">{formatDate(h.at)}</span>
                <div>{historyText(h)}</div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
