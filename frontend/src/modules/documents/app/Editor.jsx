import '@blocknote/core/fonts/inter.css'
import '@blocknote/mantine/style.css'
import { useMemo, useState } from 'react'
import {
  BlockNoteSchema,
  defaultBlockSpecs,
  filterSuggestionItems,
  insertOrUpdateBlockForSlashMenu,
} from '@blocknote/core'
import { SuggestionMenu } from '@blocknote/core/extensions'
import { fr } from '@blocknote/core/locales'
import { BlockNoteView } from '@blocknote/mantine'
import {
  SuggestionMenuController,
  createReactBlockSpec,
  getDefaultReactSlashMenuItems,
  useCreateBlockNote,
} from '@blocknote/react'
import { ACT_TYPES, BLOCKS, FAMILY_TYPES, LAYOUT_TYPES, QUESTION_TYPES, RESULT_TYPES, euros, label } from './blocks.js'

// Préparer : les deux formulaires s'éditent avec BlockNote, en « ce que vous
// voyez est ce que vous obtenez » (fichier-de-base.md §2.1). BlockNote lit et
// écrit le même JSON que le chat et que le serveur ; nos blocs (questions,
// paiement, résultats) y sont déclarés comme blocs BlockNote.

// Les questions du formulaire d'entrée, pour les réglages des blocs de
// résultat (graphique, total) : un éditeur n'en connaît qu'un formulaire.
const questionsParEditeur = new WeakMap()

const stop = (e) => e.stopPropagation()

function Carte({ block, editor, children, act }) {
  const b = BLOCKS[block.type]
  return (
    <div className={`ae-card${act ? ' ae-card--act' : ''}${RESULT_TYPES.includes(block.type) ? ' ae-card--result' : ''}`} contentEditable={false}>
      <div className="ae-tag">
        <span aria-hidden="true">{b.icon}</span> {b.label}
        {act && ' · Agir'}
      </div>
      {children}
      {!editor.isEditable && null}
    </div>
  )
}

function Champ({ block, editor, prop, placeholder, multiline }) {
  const commun = {
    className: multiline ? 'ae-input ae-input--multi' : 'ae-input',
    value: block.props[prop] ?? '',
    placeholder,
    disabled: !editor.isEditable,
    onKeyDown: stop,
    onChange: (e) => editor.updateBlock(block, { props: { [prop]: e.target.value } }),
  }
  return multiline ? <textarea rows={3} {...commun} /> : <input {...commun} />
}

function Case({ block, editor, prop, children }) {
  return (
    <label className="ae-check">
      <input
        type="checkbox"
        checked={Boolean(block.props[prop])}
        disabled={!editor.isEditable}
        onChange={(e) => editor.updateBlock(block, { props: { [prop]: e.target.checked } })}
      />
      {children}
    </label>
  )
}

// Réglages du bloc Présence et procuration (procurations.md §3.1) ; la
// sorte et la date viennent de « Convoquer l’AG ».
function AssemblyFields({ block, editor }) {
  const p = block.props
  const changer = (props) => editor.updateBlock(block, { props })
  return (
    <>
      <span className="ae-help">Je viens · Je donne procuration (signée au doigt) · Je ne viens pas</span>
      <label className="ae-amount">
        Pouvoirs par personne, au plus
        <input
          className="ae-input"
          type="number"
          min="0"
          max="50"
          value={p.maxProxies}
          disabled={!editor.isEditable}
          onKeyDown={stop}
          onChange={(e) => changer({ maxProxies: Math.max(0, Math.min(50, Number(e.target.value) || 0)) })}
        />
      </label>
      <span className="ae-help">0 : sans limite. Les pouvoirs en blanc ne comptent pas.</span>
      <span className="ae-help">Pouvoir en blanc : confié par le bureau, à défaut à</span>
      <Champ block={block} editor={editor} prop="blankTo" placeholder="Nom de la présidente ou du président" />
      <span className="ae-help">Lieu</span>
      <Champ block={block} editor={editor} prop="place" placeholder="Salle, adresse" />
      <select className="ae-input" aria-label="Quorum" value={p.quorum} disabled={!editor.isEditable} onChange={(e) => changer({ quorum: e.target.value })}>
        <option value="none">Pas de quorum</option>
        <option value="quarter">Quorum : un quart des membres</option>
        <option value="third">Quorum : un tiers des membres</option>
        <option value="half">Quorum : la moitié des membres</option>
      </select>
    </>
  )
}

function QuestionCard({ block, editor }) {
  const act = ACT_TYPES.includes(block.type)
  return (
    <Carte block={block} editor={editor} act={act}>
      <Champ block={block} editor={editor} prop="label" placeholder={BLOCKS[block.type].label} />
      {block.type === 'choice' && (
        <>
          <span className="ae-help">Un choix par ligne</span>
          <Champ block={block} editor={editor} prop="options" multiline />
          <Case block={block} editor={editor} prop="multiple">Plusieurs réponses possibles</Case>
        </>
      )}
      {block.type === 'payment' && (
        <label className="ae-amount">
          Montant
          <input
            className="ae-input"
            type="number"
            min="1"
            max="10000"
            value={block.props.amount}
            disabled={!editor.isEditable}
            onKeyDown={stop}
            onChange={(e) => editor.updateBlock(block, { props: { amount: Number(e.target.value) || 0 } })}
          />
          €
        </label>
      )}
      {block.type === 'assembly' && <AssemblyFields block={block} editor={editor} />}
      {block.type === 'member' && <span className="ae-help">Nom, prénom, email, téléphone : relié à la fiche du membre</span>}
      {block.type !== 'payment' && block.type !== 'assembly' && <Case block={block} editor={editor} prop="required">Réponse obligatoire</Case>}
      {block.type === 'payment' && <span className="ae-help">Le paiement en ligne (HelloAsso) arrive avec Diffuser. En essai : {euros(block.props.amount)}, rien n’est payé.</span>}
    </Carte>
  )
}

function ResultCard({ block, editor }) {
  const qs = questionsParEditeur.get(editor) ?? []
  const choix = block.type === 'choiceChart' ? qs.filter((q) => q.type === 'choice' || q.type === 'yesNo') : qs.filter((q) => q.type === 'payment' || q.type === 'number')
  return (
    <Carte block={block} editor={editor}>
      {block.type === 'responseCount' && <span className="ae-help">« 12 / 30 ont répondu »</span>}
      {block.type === 'responseTable' && <span className="ae-help">Une ligne par personne, une colonne par question</span>}
      {block.type === 'assemblyQuorum' && <span className="ae-help">Viennent, procurations, ne viennent pas, sans réponse, quorum</span>}
      {block.type === 'assemblyProxies' && <span className="ae-help">Chaque représentant et les pouvoirs qu’il porte</span>}
      {(block.type === 'choiceChart' || block.type === 'total') && (
        <select
          className="ae-input"
          value={block.props.questionId}
          disabled={!editor.isEditable}
          onChange={(e) => editor.updateBlock(block, { props: { questionId: e.target.value } })}
        >
          <option value="">Choisir la question…</option>
          {choix.map((q) => (
            <option key={q.id} value={q.id}>{label(q)}</option>
          ))}
        </select>
      )}
    </Carte>
  )
}

const meta = { selectable: false }
const q = (type, props = {}) =>
  createReactBlockSpec(
    { type, propSchema: { label: { default: '' }, required: { default: false }, ...props }, content: 'none' },
    { render: QuestionCard, meta },
  )
const r = (type, props = {}) => createReactBlockSpec({ type, propSchema: props, content: 'none' }, { render: ResultCard, meta })

const CUSTOM = {
  shortText: q('shortText'),
  longText: q('longText'),
  choice: q('choice', { options: { default: 'Oui\nNon' }, multiple: { default: false } }),
  date: q('date'),
  number: q('number'),
  yesNo: q('yesNo'),
  // `minutesOf` : la convocation dont ce bloc signe le procès-verbal (0 : aucune).
  signature: q('signature', { minutesOf: { default: 0 } }),
  member: q('member'),
  payment: q('payment', { amount: { default: 10 } }),
  assembly: q('assembly', {
    kind: { default: 'ordinary' },
    startsAt: { default: '' },
    place: { default: '' },
    maxProxies: { default: 2 },
    blankTo: { default: '' },
    quorum: { default: 'none' },
  }),
  responseCount: r('responseCount'),
  responseTable: r('responseTable'),
  choiceChart: r('choiceChart', { questionId: { default: '' } }),
  total: r('total', { questionId: { default: '' } }),
  assemblyQuorum: r('assemblyQuorum'),
  assemblyProxies: r('assemblyProxies'),
}

function schemaFor(form, family) {
  const types = form === 'result' ? [...LAYOUT_TYPES, ...RESULT_TYPES] : FAMILY_TYPES[family]
  const specs = {}
  for (const t of types) {
    if (defaultBlockSpecs[t]) specs[t] = defaultBlockSpecs[t]
    else specs[t] = CUSTOM[t]()
  }
  return BlockNoteSchema.create({ blockSpecs: specs })
}

function groupe(t) {
  if (RESULT_TYPES.includes(t)) return 'Résultats'
  if (ACT_TYPES.includes(t)) return 'Agir dans l’appli'
  return 'Questions'
}

export default function Editor({ blocks, form, family, entryQuestions, editable, onChange }) {
  const schema = useMemo(() => schemaFor(form, family), [form, family])
  const [depart] = useState(blocks)
  const editor = useCreateBlockNote(
    {
      schema,
      dictionary: fr,
      initialContent: depart.length ? depart : undefined,
    },
    [schema],
  )
  questionsParEditeur.set(editor, entryQuestions ?? [])
  const ag = (entryQuestions ?? []).some((x) => x.type === 'assembly')
  const nos = (form === 'result' ? RESULT_TYPES : [...QUESTION_TYPES, ...(family === 'act' ? ACT_TYPES : [])].filter((t) => FAMILY_TYPES[family].includes(t)))
    // Les blocs d'AG : seulement dans une convocation (un seul bloc de présence).
    .filter((t) => (t === 'assemblyQuorum' || t === 'assemblyProxies' ? ag : t === 'assembly' ? !ag : true))

  // « + Ajouter un bloc » toujours visible (le + de BlockNote n'apparaît
  // qu'au survol, absent sur téléphone).
  function ajouter() {
    const doc = editor.document
    const dernier = doc[doc.length - 1]
    const vide = dernier && Array.isArray(dernier.content) && dernier.content.length === 0
    const cible = vide ? dernier : editor.insertBlocks([{ type: 'paragraph' }], dernier, 'after')[0]
    editor.setTextCursorPosition(cible)
    editor.focus()
    editor.getExtension(SuggestionMenu)?.openSuggestionMenu('/')
  }

  return (
    <div className="ae">
      <BlockNoteView
        editor={editor}
        editable={editable}
        theme="light"
        slashMenu={false}
        onChange={() => onChange(editor.document)}
      >
        <SuggestionMenuController
          triggerCharacter="/"
          getItems={async (query) =>
            filterSuggestionItems(
              [
                ...getDefaultReactSlashMenuItems(editor),
                ...nos.map((t) => ({
                  title: BLOCKS[t].label,
                  subtext: BLOCKS[t].hint,
                  group: groupe(t),
                  icon: <span className="ae-menuicon">{BLOCKS[t].icon}</span>,
                  aliases: [t],
                  onItemClick: () => insertOrUpdateBlockForSlashMenu(editor, { type: t }),
                })),
              ],
              query,
            )
          }
        />
      </BlockNoteView>
      {editable && (
        <button type="button" className="ae-add" onClick={ajouter}>
          + Ajouter un bloc
        </button>
      )}
    </div>
  )
}
