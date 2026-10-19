import { useCallback, useEffect, useRef, useState } from 'react'
import Assistant from '../Assistant.jsx'
import { BubbleIcon, FamilyDot, StatusIcon } from '../icons.jsx'
import { FAMILIES, STATUSES } from '../kinds.js'
import Diffuser from './Diffuser.jsx'
import Editor from './Editor.jsx'
import Page from './Page.jsx'
import Results, { exampleRows } from './Results.jsx'
import FamilyCards from './FamilyCards.jsx'
import { dropForFamily, openingTab, questions, resultBlocks, tabReason } from './blocks.js'
import './app.css'

// Le fichier de base ouvert en plein écran (spec fichier-de-base.md) :
// onglets Préparer | Aperçu | Diffuser | Résultats, grisés selon l'état ;
// formulaire d'entrée et formulaire de résultat ; état et nature dans
// l'en-tête, Partager toujours visible. La bulle ouvre le même assistant que
// dans Docs, qui voit le fichier et peut écrire ses formulaires (§2.1).

const TABS = [
  ['prep', 'Préparer'],
  ['preview', 'Aperçu'],
  ['diffuse', 'Diffuser'],
  ['results', 'Résultats'],
]
const SAVE_DELAY = 800

function ShareIcon() {
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M16 14c2.4 0 4.1 1.5 4.6 4" />
    </svg>
  )
}

function Seg({ value, options, onChange, label }) {
  return (
    <div className="dx-seg" role="group" aria-label={label}>
      {options.map(([cle, texte]) => (
        <button key={cle} type="button" className={value === cle ? 'on' : ''} aria-pressed={value === cle} onClick={() => onChange(cle)}>
          {texte}
        </button>
      ))}
    </div>
  )
}

export default function AppFile({ api, item, onClose, onToast, onShare, onProperties, onDelete, onChanged, chat }) {
  const [file, setFile] = useState(null)
  const [erreur, setErreur] = useState('')
  const [tab, setTab] = useState(null)
  const [form, setForm] = useState('entry')
  const [size, setSize] = useState('phone')
  const [rows, setRows] = useState([])
  const [sheet, setSheet] = useState(null)
  const [saving, setSaving] = useState('') // '', 'pending', 'saved'
  const [editorKey, setEditorKey] = useState(0)
  const [nom, setNom] = useState('')
  const content = useRef(null)
  const [contenu, setContenu] = useState(null)
  const version = useRef(null)
  const minuteur = useRef(null)
  const enCours = useRef(Promise.resolve())
  // Assistant : gardé monté une fois ouvert (la réponse continue d'arriver
  // si on le ferme pour regarder le fichier).
  const [chatOuvert, setChatOuvert] = useState(false)
  const [chatMonte, setChatMonte] = useState(false)

  const charger = useCallback(
    async (premier = false) => {
      try {
        const f = await api.getApp(item.id)
        content.current = f.content
        setContenu(f.content)
        version.current = f.version?.number ?? null
        setFile(f)
        if (premier) setTab(openingTab(f))
        if (f.can_edit && f.family !== 'inform') setRows((await api.appResponses(item.id)).items)
        setEditorKey((k) => k + 1)
        return f
      } catch (e) {
        setErreur(e.message)
        return null
      }
    },
    [api, item.id],
  )

  useEffect(() => {
    charger(true)
  }, [charger])

  // Les réponses arrivent aussi de la page en ligne : relues en ouvrant
  // Résultats ou l'Aperçu.
  const peutLireReponses = Boolean(file?.can_edit) && file?.family !== 'inform'
  useEffect(() => {
    if (!peutLireReponses || (tab !== 'results' && tab !== 'preview')) return
    let actif = true
    api.appResponses(item.id).then((r) => actif && setRows(r.items), () => {})
    return () => {
      actif = false
    }
  }, [api, item.id, tab, peutLireReponses])

  // Enregistrement automatique, une demande à la fois.
  const enregistrer = useCallback(
    (contenu, famille) => {
      enCours.current = enCours.current.then(async () => {
        try {
          const r = await api.saveApp(item.id, contenu, famille, version.current)
          version.current = r.version.number
          setSaving('saved')
          return r
        } catch (e) {
          onToast(e.message)
          if (e.status === 409) charger()
          throw e
        }
      })
      return enCours.current
    },
    [api, item.id, onToast, charger],
  )

  function modifie(blocs) {
    const c = content.current
    content.current = form === 'entry' ? { ...c, entry: { blocks: blocs } } : { ...c, result: { blocks: blocs } }
    setContenu(content.current)
    setSaving('pending')
    clearTimeout(minuteur.current)
    minuteur.current = setTimeout(() => enregistrer(content.current).catch(() => {}), SAVE_DELAY)
  }

  async function fermer() {
    clearTimeout(minuteur.current)
    if (saving === 'pending') await enregistrer(content.current).catch(() => {})
    onChanged?.()
    onClose()
  }

  async function changerEtat(status) {
    setSheet(null)
    clearTimeout(minuteur.current)
    try {
      if (saving === 'pending') await enregistrer(content.current)
      await api.setStatus(item.id, status)
      const f = await charger()
      if (f) setTab(openingTab(f))
      onToast(`Fichier ${STATUSES[status].label}`)
      onChanged?.()
    } catch (e) {
      onToast(e.message)
    }
  }

  async function changerNature(famille) {
    setSheet(null)
    if (famille === file.family) return
    clearTimeout(minuteur.current)
    const avant = { content: content.current, family: file.family }
    const apres = dropForFamily(content.current, famille)
    const retires = questions(avant.content).length - questions(apres).length
    try {
      await enregistrer(apres, famille)
      await charger()
      setForm('entry')
      setTab('prep')
      onChanged?.()
      const message = retires > 0 ? `${FAMILIES[famille].label} : ${retires} bloc${retires > 1 ? 's' : ''} retiré${retires > 1 ? 's' : ''}` : `Fichier ${FAMILIES[famille].label}`
      onToast(message, async () => {
        await enregistrer(avant.content, avant.family)
        await charger()
        onChanged?.()
      })
    } catch {
      // message déjà affiché
    }
  }

  function ouvrirChat() {
    if (!chat?.autorise) {
      onToast('L’assistant est en essai : réservé au Super User pour l’instant.')
      return
    }
    setChatOuvert(true)
    setChatMonte(true)
  }

  // L'assistant a enregistré une nouvelle version (ou « Annuler » sur sa
  // carte) : on recharge le fichier, l'éditeur repart du nouveau contenu.
  async function surFichier(carte) {
    clearTimeout(minuteur.current)
    if (carte.annuler) {
      await enCours.current.catch(() => {})
      const f = await api.getApp(item.id)
      await api.saveApp(item.id, carte.avant, undefined, f.version?.number ?? null)
    }
    setSaving('')
    setTab('prep')
    await charger()
    onChanged?.()
  }

  async function essayer(values) {
    try {
      await api.tryApp(item.id, values)
      setRows((await api.appResponses(item.id)).items)
      onToast('Réponse d’essai enregistrée : rien n’est créé dans l’appli')
    } catch (e) {
      onToast(e.message)
      throw e
    }
  }

  if (erreur) {
    return (
      <div className="dx-panel" role="dialog" aria-label={item.name}>
        <div className="dx-top">
          <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
          <h2>{item.name}</h2>
        </div>
        <p className="dx-note dx-note--pad">{erreur}</p>
      </div>
    )
  }
  if (!file || !tab || !contenu) {
    return <div className="dx-panel" role="dialog" aria-label={item.name} aria-busy="true" />
  }

  const statut = file.status ?? 'draft'
  const informer = file.family === 'inform'
  const onglets = TABS.filter(([cle]) => cle !== 'results' || !informer)
  const raison = tabReason(tab, statut)
  const c = contenu
  const formOptions = [
    ['entry', 'Formulaire d’entrée'],
    ['result', 'Formulaire de résultat'],
  ]
  const formActif = informer ? 'entry' : form
  const essais = rows.filter((r) => r.is_test).length
  const lienShare = { id: file.id, name: file.name, space: file.space, kind: 'app' }

  let corps
  let bas = null
  if (raison) {
    corps = <p className="dx-note">{raison}.</p>
  } else if (tab === 'prep') {
    corps = (
      <>
        {!informer && <Seg label="Formulaire" value={formActif} options={formOptions} onChange={setForm} />}
        {!file.editable && (
          <p className="dx-note">
            {file.frozen_by ? `Le dossier « ${file.frozen_by} » est officiel : son contenu ne se modifie plus.` : 'Vous pouvez lire ce fichier, pas le modifier.'}
          </p>
        )}
        {formActif === 'result' && <p className="af-hint">Fabriqué tout seul à partir des questions. Déplacez, retirez ou ajoutez des blocs avec « / ».</p>}
        <Editor
          key={`${editorKey}-${formActif}-${file.family}`}
          blocks={formActif === 'entry' ? c.entry.blocks : resultBlocks(c)}
          form={formActif}
          family={file.family}
          entryQuestions={questions(c)}
          editable={file.editable}
          onChange={modifie}
        />
      </>
    )
    bas = (
      <button
        type="button"
        className="dx-btn"
        disabled={!file.can_manage || !c.entry.blocks.length}
        title={!file.can_manage ? 'Un admin valide le fichier' : undefined}
        onClick={() => changerEtat('validated')}
      >
        Valider
      </button>
    )
  } else if (tab === 'preview') {
    corps = (
      <>
        {!informer && <Seg label="Formulaire" value={formActif} options={formOptions} onChange={setForm} />}
        {formActif === 'entry' ? (
          <>
            <Seg
              label="Taille"
              value={size}
              options={[
                ['phone', 'Téléphone'],
                ['desktop', 'Ordinateur'],
                ['a4', 'A4'],
              ]}
              onChange={setSize}
            />
            {!informer && file.can_edit && size !== 'a4' && <p className="af-hint">Remplissez la page pour l’essayer : la réponse est marquée « Essai » et ne crée rien.</p>}
            <Page
              key={`${editorKey}-${size}`}
              content={c}
              size={size}
              onSubmit={!informer && file.can_edit ? essayer : undefined}
              submitLabel="Envoyer ma réponse (essai)"
            />
          </>
        ) : (
          <>
            <p className="af-hint">{rows.length ? 'Avec les réponses reçues.' : 'Avec des réponses d’exemple, en attendant les vraies.'}</p>
            <Results content={c} rows={rows.length ? rows : exampleRows(c)} />
          </>
        )}
      </>
    )
  } else if (tab === 'diffuse') {
    corps = (
      <Diffuser
        file={file}
        api={api}
        onToast={onToast}
        // Après un essai sur soi : les réponses sont dans Résultats en
        // Officiel, sinon sous la page dans Aperçu.
        onVoirReponses={() => {
          if (statut === 'official') setTab('results')
          else {
            setForm('result')
            setTab('preview')
          }
        }}
        onChanged={async () => {
          await charger()
          onChanged?.()
        }}
      />
    )
  } else {
    corps = <Results content={c} rows={rows} />
    bas = essais > 0 && (
      <button
        type="button"
        className="dx-btn dx-btn--ghost"
        onClick={async () => {
          await api.clearTests(item.id)
          setRows((await api.appResponses(item.id)).items)
          onToast(essais > 1 ? `${essais} essais effacés` : 'Essai effacé')
        }}
      >
        Effacer les essais ({essais})
      </button>
    )
  }

  return (
    <div className={`dx-panel af${chatOuvert && chat?.bureau ? ' af--chat' : ''}`} role="dialog" aria-label={file.name}>
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={fermer} aria-label="Retour">←</button>
        <h2 title={file.name}>{file.name}</h2>
        <button type="button" className="dx-ico" onClick={() => onShare(lienShare)} aria-label="Partager : qui a accès ?" disabled={file.space === 'personal'}>
          <ShareIcon />
        </button>
        <button type="button" className="dx-ico" onClick={() => setSheet('more')} aria-label="Plus d’actions">⋯</button>
      </div>
      <div className="af-sub">
        <button type="button" className={`af-status af-status--${statut}`} onClick={() => setSheet('status')} disabled={!file.can_edit && !file.can_manage}>
          <StatusIcon status={statut} />
          {STATUSES[statut].label}
          {file.can_edit && <span className="af-chev" aria-hidden="true">▾</span>}
        </button>
        <button
          type="button"
          className="af-family"
          style={{ color: FAMILIES[file.family].color }}
          disabled={!file.editable}
          onClick={() => setSheet('family')}
          title={file.editable ? 'Changer la nature' : undefined}
        >
          <FamilyDot family={file.family} size={24} />
          {FAMILIES[file.family].label}
          {file.editable && <span className="af-chev" aria-hidden="true">▾</span>}
        </button>
        {saving && tab === 'prep' && <span className="af-saved">{saving === 'pending' ? 'Enregistrement…' : 'Enregistré'}</span>}
      </div>
      {file.can_edit && (
        <div className="af-tabs" role="tablist" style={{ '--n': onglets.length }}>
          {onglets.map(([cle, texte]) => {
            const r = tabReason(cle, statut)
            return (
              <button
                key={cle}
                type="button"
                role="tab"
                aria-selected={tab === cle}
                className={r ? 'af-tab--off' : ''}
                title={r ?? undefined}
                onClick={() => (r ? onToast(r) : setTab(cle))}
              >
                {texte}
              </button>
            )
          })}
        </div>
      )}
      <div className="dx-body af-body">{corps}</div>
      {bas && <div className="dx-footer">{bas}</div>}

      {tab === 'prep' && !chatOuvert && (
        <button type="button" className="af-fab" onClick={ouvrirChat} aria-label="Assistant">
          <BubbleIcon />
        </button>
      )}
      {chatMonte && (
        <div
          className={chat.bureau ? 'af-chat' : 'dx-chat-bas dx-chat-bas--plein'}
          style={{ display: chatOuvert ? undefined : 'none' }}
        >
          <Assistant
            orgId={chat.orgId}
            titre="Assistant du fichier"
            memoire={`app-${file.id}`}
            coutSaisonInitial={chat.coutSaison}
            contexte={{ space: file.space, folder_id: file.parent_id, selection_id: file.id, app_id: file.id, form: formActif }}
            onClose={() => setChatOuvert(false)}
            onFaire={chat.onFaire}
            onFichier={surFichier}
            suggestions={['Rends le texte plus court et plus clair', 'Corrige les fautes']}
          />
        </div>
      )}

      {sheet && (
        <>
          <div className="dx-scrim af-scrim" onClick={() => setSheet(null)} />
          <div className="dx-sheet af-sheet" role="dialog" aria-label="Choix">
            <div className="dx-grab" />
            {sheet === 'status' && (
              <>
                <h3 className="af-sheet__title">État du fichier</h3>
                {Object.entries(STATUSES).map(([cle, s]) => {
                  const interdit = cle !== 'draft' && !file.can_manage ? 'Un admin valide ou rend officiel' : statut === 'official' && !file.can_manage ? 'Un admin peut le rouvrir' : null
                  return (
                    <button
                      key={cle}
                      type="button"
                      className="dx-act"
                      disabled={Boolean(interdit)}
                      onClick={() => (cle === statut ? setSheet(null) : cle === 'official' ? setSheet('official') : changerEtat(cle))}
                    >
                      <span className={`af-status af-status--${cle} af-status--icon`}><StatusIcon status={cle} /></span>
                      <span className="dx-meta">
                        <span className="dx-n">{s.label}{cle === statut && ' ✓'}</span>
                        <span className="dx-s">{interdit ?? { draft: 'On prépare, rien n’est diffusé', validated: 'Relu, prêt à être diffusé', official: 'Contenu figé, on collecte les réponses' }[cle]}</span>
                      </span>
                    </button>
                  )
                })}
              </>
            )}
            {sheet === 'official' && (
              <div className="af-pad">
                <h3 className="af-sheet__title">Passer en Officiel ?</h3>
                <p>Le contenu sera figé. {informer ? '' : 'Les réponses pourront arriver. '}Pour le modifier ensuite, un admin devra le repasser en Brouillon.</p>
                <button type="button" className="dx-btn" onClick={() => changerEtat('official')}>Passer en Officiel</button>
              </div>
            )}
            {sheet === 'family' && (
              <div className="af-pad">
                <h3 className="af-sheet__title">Nature du fichier</h3>
                <FamilyCards value={file.family} onPick={changerNature} />
              </div>
            )}
            {sheet === 'rename' && (
              <form
                className="af-pad"
                onSubmit={async (e) => {
                  e.preventDefault()
                  try {
                    const r = await api.rename(file.id, nom)
                    setFile((f) => ({ ...f, name: r.name }))
                    setSheet(null)
                    onChanged?.()
                  } catch (err) {
                    onToast(err.message)
                  }
                }}
              >
                <h3 className="af-sheet__title">Renommer</h3>
                <input className="af-name" id="af-nom" aria-label="Nom du fichier" value={nom} onChange={(e) => setNom(e.target.value)} autoFocus />
                <button type="submit" className="dx-btn" disabled={!nom.trim()}>Renommer</button>
              </form>
            )}
            {sheet === 'template' && (
              <form
                className="af-pad"
                onSubmit={async (e) => {
                  e.preventDefault()
                  try {
                    const m = await api.makeTemplate(file.id, nom)
                    setSheet(null)
                    onToast(`Modèle « ${m.name} » créé : il est dans le +, section ${FAMILIES[m.family].label}`)
                  } catch (err) {
                    onToast(err.message)
                  }
                }}
              >
                <h3 className="af-sheet__title">Faire un modèle</h3>
                <p className="af-hint">
                  Une tuile apparaîtra dans le +, section {FAMILIES[file.family].label}. La toucher créera une copie de ce fichier, sans les réponses.
                </p>
                <label className="af-label" htmlFor="af-modele">Nom de la tuile, avec un verbe</label>
                <input
                  className="af-name"
                  id="af-modele"
                  placeholder="Organiser la fête de fin d’année"
                  value={nom}
                  onChange={(e) => setNom(e.target.value)}
                  autoFocus
                />
                <button type="submit" className="dx-btn" disabled={!nom.trim()}>Créer le modèle</button>
              </form>
            )}
            {sheet === 'more' && (
              <>
                <button type="button" className="dx-act" onClick={() => (setSheet(null), onShare(lienShare))} disabled={file.space === 'personal'}>
                  <i>👥</i><span>Partager</span>
                </button>
                <button type="button" className="dx-act" onClick={() => (setNom(file.name), setSheet('rename'))}>
                  <i>✎</i><span>Renommer</span>
                </button>
                <button
                  type="button"
                  className="dx-act"
                  disabled={!file.can_manage || !c.entry.blocks.length}
                  onClick={() => (setNom(file.name), setSheet('template'))}
                >
                  <i>⧉</i>
                  <span>
                    Faire un modèle
                    {(!file.can_manage || !c.entry.blocks.length) && (
                      <span className="dx-act__why">{!file.can_manage ? 'Réservé aux admins' : 'Préparez d’abord le fichier'}</span>
                    )}
                  </span>
                </button>
                <button type="button" className="dx-act" onClick={() => (setSheet(null), onProperties(file.id))}>
                  <i>☰</i><span>Propriétés</span>
                </button>
                <button type="button" className="dx-act dx-act--danger" onClick={() => (setSheet(null), onDelete(lienShare))}>
                  <i>🗑</i><span>Supprimer</span>
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
