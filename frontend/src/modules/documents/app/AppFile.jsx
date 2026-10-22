import { useCallback, useEffect, useRef, useState } from 'react'
import ActionsEntete, { TitreEntete } from '../../../components/ActionsEntete.jsx'
import { brancherFichier } from '../assistantGlobal.js'
import { FamilyDot, StatusIcon } from '../icons.jsx'
import { FAMILIES, STATUSES } from '../kinds.js'
import AssemblySend from './AssemblySend.jsx'
import MinutesSign from './MinutesSign.jsx'
import Diffuser from './Diffuser.jsx'
import Editor from './Editor.jsx'
import AssemblyRemind from './AssemblyRemind.jsx'
import Emargement from './Emargement.jsx'
import Page from './Page.jsx'
import SignPrepare from './SignPrepare.jsx'
import SignPreview from './SignPreview.jsx'
import SignResults from './SignResults.jsx'
import SignSend from './SignSend.jsx'
import Results, { exampleRows } from './Results.jsx'
import FamilyCards from './FamilyCards.jsx'
import { assemblyBlock, avecTexte, dropForFamily, minutesBlock, openingTab, questions, resultBlocks, signBlock, tabReason, telecharger } from './blocks.js'
import './app.css'

// Le fichier de base ouvert en plein écran (spec fichier-de-base.md) :
// onglets Préparer | Aperçu | Diffuser | Résultats, grisés selon l'état ;
// formulaire d'entrée et formulaire de résultat ; état et nature dans
// l'en-tête, Partager toujours visible. La bulle ouvre le même assistant que
// dans Docs, qui voit le fichier et peut écrire ses formulaires (§2.1).

// Trois étapes (Seb, 21 octobre). « 1. Préparer » a ses modes, choisis dans
// le bandeau du haut : Édition (`prep`) ou Aperçu (`preview`, par défaut),
// en taille smartphone (par défaut) ou ordinateur.
const TABS = [
  ['etape1', '1. Préparer'],
  ['diffuse', '2. Diffuser'],
  ['results', '3. Voir les résultats'],
]
// Le menu « Mode » (Seb, 21 octobre) : l'aperçu choisit aussi sa taille.
const MODES = [
  ['prep', 'Édition'],
  ['phone', 'Aperçu smartphone'],
  ['desktop', 'Aperçu ordinateur'],
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

export default function AppFile({ api, item, onClose, onToast, onShare, onProperties, onDelete, onChanged }) {
  const [file, setFile] = useState(null)
  const [erreur, setErreur] = useState('')
  const [tab, setTab] = useState(null)
  // L'onglet demandé à l'ouverture (`item.tab`), pris une seule fois.
  const premierOnglet = useRef(item.tab ?? null)
  const [form, setForm] = useState('entry')
  const [size, setSize] = useState('phone')
  const [rows, setRows] = useState([])
  // Le fichier commence sous l'en-tête de l'appli (qui porte son titre).
  const [hautEntete] = useState(() => Math.round(document.querySelector('.app-header')?.getBoundingClientRect().bottom ?? 0))
  const [sheet, setSheet] = useState(null)
  const [saving, setSaving] = useState('') // '', 'pending', 'saved'
  const [editorKey, setEditorKey] = useState(0)
  const [nom, setNom] = useState('')
  const content = useRef(null)
  const [contenu, setContenu] = useState(null)
  const version = useRef(null)
  const minuteur = useRef(null)
  const enCours = useRef(Promise.resolve())
  // Convocation d'AG (procurations.md) : décompte et destinataires par
  // défaut ; « Changer » ramène au Diffuser habituel.
  const [ag, setAg] = useState(null)
  const [diffuserTout, setDiffuserTout] = useState(false)
  const [emargement, setEmargement] = useState(false)
  // Document à signer (signature-documents.md) : le document choisi, ses pages, s'il est figé.
  const [sign, setSign] = useState(null)

  const charger = useCallback(
    // `ouvrir` : choisir l'onglet d'après l'état (ouverture, changement d'état).
    async (ouvrir = false) => {
      try {
        const f = await api.getApp(item.id)
        content.current = f.content
        setContenu(f.content)
        version.current = f.version?.number ?? null
        setFile(f)
        const convocation = Boolean(assemblyBlock(f.content)) && f.can_edit
        const vue = convocation ? await api.assembly(item.id).catch(() => null) : null
        setAg(vue)
        const signe = signBlock(f.content) ? await api.signing(item.id).catch(() => null) : null
        setSign(signe)
        // Une convocation officielle pas encore envoyée s'ouvre sur l'envoi.
        // `item.tab` : l'onglet demandé (ex. l'Aperçu d'une convocation tout juste préparée).
        // Un document à signer encore sans document s'ouvre sur l'Édition ;
        // déjà envoyé pour signature, sur le suivi.
        const aDeposer = f.can_edit && f.status === 'draft' && !signBlock(f.content)?.props?.source && Boolean(signBlock(f.content))
        const suivi = f.can_edit && ['validated', 'official'].includes(f.status) && signe?.signers > 0
        if (ouvrir) {
          setTab(
            premierOnglet.current ??
              (vue && f.status === 'official' && !vue.summary.convoked ? 'diffuse' : aDeposer ? 'prep' : suivi ? 'results' : openingTab(f)),
          )
          premierOnglet.current = null
        }
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
    if (assemblyBlock(content.current)) api.assembly(item.id).then((v) => actif && setAg(v), () => {})
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

  // Un texte corrigé dans l'Aperçu : même enregistrement que Préparer ;
  // l'éditeur de Préparer repartira du nouveau contenu.
  function modifieTexte(id, texte) {
    const c = content.current
    content.current = { ...c, entry: { blocks: avecTexte(c.entry.blocks, id, texte) } }
    setContenu(content.current)
    setEditorKey((k) => k + 1)
    setSaving('pending')
    clearTimeout(minuteur.current)
    minuteur.current = setTimeout(() => enregistrer(content.current).catch(() => {}), SAVE_DELAY)
  }

  // Les réglages du document à signer (SignPrepare) : les props de son bloc.
  function modifieBloc(id, props) {
    const c = content.current
    const blocs = c.entry.blocks.map((b) => (b.id === id ? { ...b, props: { ...b.props, ...props } } : b))
    content.current = { ...c, entry: { blocks: blocs } }
    setContenu(content.current)
    setSaving('pending')
    clearTimeout(minuteur.current)
    minuteur.current = setTimeout(() => enregistrer(content.current).catch(() => {}), SAVE_DELAY)
  }

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
      await charger(true)
      onToast(`Fichier ${STATUSES[status].label}`)
      onChanged?.()
      return true
    } catch (e) {
      onToast(e.message)
      return false
    }
  }

  // « Valider pour passer à l'étape de diffusion » (Seb, 21 octobre) : une
  // convocation passe en Officiel, le reste en Validé, puis on va à Diffuser.
  async function valider() {
    if (await changerEtat(assemblyBlock(content.current) ? 'official' : 'validated')) setTab('diffuse')
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

  // Le fichier ouvert se branche sur l'assistant de l'appli (Seb,
  // 21 octobre) : il le lit, le corrige, et « Annuler » sous sa carte
  // revient à la version d'avant.
  const pourAssistant = useRef(null)
  useEffect(() => {
    pourAssistant.current = {
      contexte: () =>
        file && {
          space: file.space,
          folder_id: file.parent_id,
          selection_id: file.id,
          app_id: file.id,
          form: file.family === 'inform' ? 'entry' : form,
        },
      surFichier,
    }
  })
  useEffect(
    () =>
      brancherFichier({
        contexte: () => pourAssistant.current.contexte(),
        surFichier: (carte) => pourAssistant.current.surFichier(carte),
      }),
    [],
  )

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
  const c = contenu
  // Document à signer : « Voir les résultats » s'ouvre dès le premier envoi (§2.5).
  const raisonOnglet = (cle) =>
    signBlock(c) && cle === 'diffuse' && statut === 'official'
      ? 'Le document est signé par tous'
      : cle === 'results' && signBlock(c) && statut === 'validated' && sign?.signers
        ? null
        : tabReason(cle, statut)
  const raison = raisonOnglet(tab)
  const formOptions = [
    ['entry', 'Formulaire d’entrée'],
    ['result', 'Formulaire de résultat'],
  ]
  const formActif = informer ? 'entry' : form
  const essais = rows.filter((r) => r.is_test).length
  const signe = signBlock(c)
  const boutonValider = (
    <button
      type="button"
      className="dx-btn"
      disabled={!file.can_manage || !c.entry.blocks.length || (signe && !sign?.source)}
      title={!file.can_manage ? 'Un admin valide le fichier' : undefined}
      // Une convocation passe directement en Officiel (procurations.md §1.3).
      onClick={valider}
    >
      Valider pour passer à l’étape de diffusion
    </button>
  )
  const lienShare = { id: file.id, name: file.name, space: file.space, kind: 'app' }

  let corps
  let bas = null
  if (raison) {
    corps = <p className="dx-note">{raison}.</p>
  } else if (signe && tab === 'prep') {
    corps = (
      <SignPrepare
        file={file}
        block={signe}
        sign={sign}
        api={api}
        onToast={onToast}
        onProps={(props) => modifieBloc(signe.id, props)}
        onDocument={async () => {
          clearTimeout(minuteur.current)
          await enCours.current.catch(() => {})
          await charger()
          onChanged?.()
        }}
      />
    )
    bas = boutonValider
  } else if (signe && tab === 'preview') {
    corps = (
      <SignPreview
        file={file}
        content={c}
        block={signe}
        sign={sign}
        api={api}
        size={size}
        onTexte={file.editable && statut === 'draft' ? modifieTexte : undefined}
      />
    )
    if (statut === 'draft' && file.editable) bas = boutonValider
  } else if (signe && tab === 'diffuse') {
    corps = (
      <SignSend
        file={file}
        api={api}
        onToast={onToast}
        onSent={async () => {
          await charger()
          setTab('results')
        }}
      />
    )
  } else if (signe && tab === 'results') {
    corps = <SignResults file={file} api={api} onToast={onToast} onProduced={() => (charger(), onChanged?.())} onDelete={onDelete} />
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
        {/* WYSIWYG (Seb, 21 octobre) : l'éditeur a l'allure de la page reçue
            par les membres (même carte, largeur, texte et titres). */}
        <div className={formActif === 'entry' ? 'af-wysiwyg' : undefined}>
        <Editor
          key={`${editorKey}-${formActif}-${file.family}`}
          blocks={formActif === 'entry' ? c.entry.blocks : resultBlocks(c)}
          form={formActif}
          family={file.family}
          entryQuestions={questions(c)}
          editable={file.editable}
          onChange={modifie}
        />
        </div>
      </>
    )
    bas = (
      <button
        type="button"
        className="dx-btn"
        disabled={!file.can_manage || !c.entry.blocks.length}
        title={!file.can_manage ? 'Un admin valide le fichier' : undefined}
        // Une convocation passe directement en Officiel (procurations.md §1.3).
        onClick={valider}
      >
        Valider pour passer à l’étape de diffusion
      </button>
    )
  } else if (tab === 'preview') {
    // Aperçu modifiable d'un brouillon : on peut valider d'ici (procurations.md §1.3).
    if (statut === 'draft' && file.editable) {
      bas = (
        <button
          type="button"
          className="dx-btn"
          disabled={!file.can_manage || !c.entry.blocks.length}
          title={!file.can_manage ? 'Un admin valide le fichier' : undefined}
          onClick={valider}
        >
          Valider pour passer à l’étape de diffusion
        </button>
      )
    }
    corps = (
      <>
        {!informer && <Seg label="Formulaire" value={formActif} options={formOptions} onChange={setForm} />}
        {formActif === 'entry' ? (
          <>
            {file.editable && statut === 'draft' && (
              <p className="af-hint af-hint--fort">
                Touchez un texte pour le corriger directement, ou demandez à l’assistant ce qu’il faut changer.
              </p>
            )}
            <Page
              key={`${editorKey}-${size}`}
              content={c}
              size={size}
              // On clique les questions comme un membre, rien n'est enregistré ;
              // la vraie réponse d'essai passe par Diffuser (Seb, 21 octobre).
              interactif
              onTexte={file.editable && statut === 'draft' ? modifieTexte : undefined}
              assembly={
                ag && {
                  candidates: ag.recipients.map((r) => ({ id: r.person_id, name: r.name })),
                }
              }
            />
          </>
        ) : (
          <>
            <p className="af-hint">{rows.length ? 'Avec les réponses reçues.' : 'Avec des réponses d’exemple, en attendant les vraies.'}</p>
            <Results content={c} rows={rows.length ? rows : exampleRows(c)} summary={ag?.summary.convoked ? ag.summary : null} />
          </>
        )}
      </>
    )
  } else if (tab === 'diffuse' && ag && statut === 'official' && !diffuserTout) {
    corps = (
      <AssemblySend
        file={file}
        api={api}
        onToast={onToast}
        onChanger={() => setDiffuserTout(true)}
        onSent={async () => {
          setAg(await api.assembly(item.id))
          onChanged?.()
        }}
      />
    )
  } else if (tab === 'diffuse' && minutesBlock(c) && statut !== 'draft' && !diffuserTout) {
    // Procès-verbal d'AG : signatures du bureau, puis envoi aux membres.
    corps = <MinutesSign file={file} api={api} onToast={onToast} onChanger={() => setDiffuserTout(true)} />
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
  } else if (ag) {
    const fichier = async (quoi, nom) => {
      try {
        telecharger(await api.assemblyFile(item.id, quoi), nom)
      } catch (e) {
        onToast(e.message)
      }
    }
    const titre = file.name.replace(/^Convocation /, '')
    const produireFeuille = async () => {
      // Fenêtre ouverte tout de suite (sinon bloquée), le PDF y arrive ensuite.
      const fenetre = window.open('', '_blank')
      try {
        const blob = await api.signingSheet(item.id)
        if (fenetre) fenetre.location.href = URL.createObjectURL(blob)
        else telecharger(blob, `Feuille d’émargement à signer ${titre}.pdf`)
        onToast('Feuille d’émargement rangée dans le dossier de l’AG')
      } catch (e) {
        fenetre?.close()
        onToast(e.message)
      }
    }
    corps = (
      <>
        {ag.summary.convoked > 0 && (
          <button type="button" className="dx-btn dx-btn--ghost af-emargement" onClick={() => setEmargement(true)}>
            Feuille d’émargement (le jour de l’AG)
          </button>
        )}
        {ag.summary.none > 0 && !(ag.summary.starts_at && new Date(ag.summary.starts_at) <= new Date()) && (
          <AssemblyRemind
            file={file}
            api={api}
            count={ag.summary.none}
            onToast={onToast}
            onSent={async () => setAg(await api.assembly(item.id))}
          />
        )}
        <Results content={c} rows={rows} summary={ag.summary.convoked ? ag.summary : null} />
      </>
    )
    bas = (
      <>
        <button type="button" className="dx-btn" onClick={() => fichier('summary.pdf', `Récapitulatif ${titre}.pdf`)}>
          Télécharger le récapitulatif
        </button>
        <button type="button" className="dx-btn dx-btn--ghost" onClick={() => fichier('summary.xlsx', `Récapitulatif ${titre}.xlsx`)}>
          Excel
        </button>
        {/* Seb, 21 octobre : le PDF à signer, ouvert dans la visionneuse PDF. */}
        <button type="button" className="dx-btn dx-btn--ghost" onClick={produireFeuille}>
          Produire la feuille d’émargement
        </button>
      </>
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

  if (emargement) {
    return (
      <Emargement
        file={file}
        api={api}
        onToast={onToast}
        onClose={async () => {
          setEmargement(false)
          setAg(await api.assembly(item.id))
        }}
      />
    )
  }

  return (
    // Sous l'en-tête de l'appli, qui porte ← le nom, l'état, qui a accès et ⋮
    // (Seb, 21 octobre).
    <div className="dx-panel af" role="dialog" aria-label={file.name} style={{ top: `max(var(--panneau-haut, 0px), ${hautEntete}px)` }}>
      <TitreEntete>
        {/* `dx` : les styles de Docs (pastille d'état…) valent aussi dans l'en-tête. */}
        <div className="dx af-entete">
          <button type="button" className="dx-ico af-retour" onClick={fermer} aria-label="Retour">←</button>
          <h1 className="af-titre-entete" title={file.name}>{file.name}</h1>
          <button type="button" className={`af-status af-status--${statut}`} onClick={() => setSheet('status')} disabled={!file.can_edit && !file.can_manage}>
            <StatusIcon status={statut} />
            {STATUSES[statut].label}
            {file.can_edit && <span className="af-chev" aria-hidden="true">▾</span>}
          </button>
          {/* « 1. Préparer » : menu Mode, Aperçu par défaut ou Édition (Seb, 21 octobre). */}
          {file.can_edit && (tab === 'prep' || tab === 'preview') && (
            <label className="af-mode">
              <span className="af-mode__mot">Mode</span>
              <select
                aria-label="Mode"
                value={tab === 'prep' ? 'prep' : size === 'desktop' ? 'desktop' : 'phone'}
                onChange={(e) => {
                  if (e.target.value === 'prep') setTab('prep')
                  else {
                    setSize(e.target.value)
                    setTab('preview')
                  }
                }}
              >
                {MODES.map(([cle, texte]) => (
                  <option key={cle} value={cle}>
                    {texte}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </TitreEntete>
      <ActionsEntete>
        <div className="dx af-entete">
          <button type="button" className="dx-ico" onClick={() => onShare(lienShare)} aria-label="Partager : qui a accès ?" disabled={file.space === 'personal'}>
            <ShareIcon />
          </button>
          <button type="button" className="dx-ico" onClick={() => setSheet('more')} aria-label="Plus d’actions">⋮</button>
        </div>
      </ActionsEntete>
      <div className="af-sub">
        {/* Convocation et PV d'AG : la nature ne s'affiche pas, le parcours la
            cache (procurations.md §6, Seb 21 octobre). */}
        {!assemblyBlock(c) && !minutesBlock(c) && !signe && (
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
        )}
        {saving && (tab === 'prep' || tab === 'preview') && <span className="af-saved">{saving === 'pending' ? 'Enregistrement…' : 'Enregistré'}</span>}
      </div>
      {file.can_edit && (
        <div className="af-tabs" role="tablist" style={{ '--n': onglets.length }}>
          {onglets.map(([cle, texte]) => {
            const r = cle === 'etape1' ? null : raisonOnglet(cle)
            const actif = cle === 'etape1' ? tab === 'prep' || tab === 'preview' : tab === cle
            return (
              <button
                key={cle}
                type="button"
                role="tab"
                aria-selected={actif}
                className={r ? 'af-tab--off' : ''}
                title={r ?? undefined}
                onClick={() => (r ? onToast(r) : !actif && setTab(cle === 'etape1' ? 'preview' : cle))}
              >
                {texte}
              </button>
            )
          })}
        </div>
      )}
      <div className="dx-body af-body">{corps}</div>
      {bas && <div className="dx-footer">{bas}</div>}

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
                        <span className="dx-s">
                          {interdit ??
                            (signe
                              ? { draft: statut === 'draft' ? 'On prépare le document à signer' : 'Pour corriger : les signatures déjà faites sont annulées', validated: 'Document figé, prêt à faire signer', official: 'Signé par tous' }
                              : minutesBlock(c)
                              ? { draft: statut === 'draft' ? 'On écrit le procès-verbal' : 'Pour corriger le texte : les signatures déjà faites s’effacent', validated: 'Texte figé, prêt à envoyer pour signature', official: 'Signé par tous' }
                              : { draft: 'On prépare, rien n’est diffusé', validated: 'Relu, prêt à être diffusé', official: 'Contenu figé, on collecte les réponses' })[cle]}
                        </span>
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
