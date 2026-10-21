// Fichier de base (spec fichier-de-base.md) : ce qui est commun à l'éditeur,
// à l'aperçu et aux résultats. Le contenu est un JSON de blocs à la forme de
// BlockNote, contrôlé par le serveur (backend/src/documents/app_content.py).

export const LAYOUT_TYPES = ['paragraph', 'heading', 'quote', 'bulletListItem', 'numberedListItem', 'checkListItem', 'divider']
export const QUESTION_TYPES = ['shortText', 'longText', 'choice', 'date', 'number', 'yesNo', 'signature', 'assembly']
export const ACT_TYPES = ['member', 'payment']
export const RESULT_TYPES = ['responseCount', 'responseTable', 'choiceChart', 'total', 'assemblyQuorum', 'assemblyProxies']

export const FAMILY_TYPES = {
  inform: LAYOUT_TYPES,
  question: [...LAYOUT_TYPES, ...QUESTION_TYPES],
  act: [...LAYOUT_TYPES, ...QUESTION_TYPES, ...ACT_TYPES],
}

export const FAMILY_TEXT = {
  inform: { hint: 'À lire, personne ne répond', examples: 'Page de cours, compte rendu, présentation' },
  question: { hint: 'Chacun répond, les réponses restent ici', examples: 'Sondage, convocation, appel à bénévoles' },
  act: { hint: 'On répond et ça crée quelque chose', examples: 'Inscription, adhésion, paiement' },
}

// Libellé et pictogramme de chaque bloc maison (menu « / », cartes).
export const BLOCKS = {
  shortText: { label: 'Réponse courte', icon: '✎', hint: 'Un nom, une ville…' },
  longText: { label: 'Réponse longue', icon: '¶', hint: 'Une remarque, un message' },
  choice: { label: 'Choix', icon: '◉', hint: 'Une ou plusieurs réponses dans une liste' },
  date: { label: 'Date', icon: '◷', hint: 'Une date à choisir' },
  number: { label: 'Nombre', icon: '#', hint: 'Un âge, une quantité' },
  yesNo: { label: 'Oui / non', icon: '✓', hint: 'Une case à cocher' },
  signature: { label: 'Signature', icon: '✍', hint: 'Signer au doigt' },
  assembly: { label: 'Présence et procuration', icon: '⚖', hint: 'Je viens, je donne procuration, je ne viens pas' },
  member: { label: 'Coordonnées', icon: '⚡', hint: 'Nom, email, téléphone : met à jour le membre' },
  payment: { label: 'Paiement', icon: '€', hint: 'Une somme à régler' },
  responseCount: { label: 'Compteur', icon: '①', hint: 'Combien ont répondu' },
  responseTable: { label: 'Tableau des réponses', icon: '▦', hint: 'Une ligne par personne' },
  choiceChart: { label: 'Graphique', icon: '▮', hint: 'Les réponses d’une question à choix' },
  total: { label: 'Total', icon: 'Σ', hint: 'La somme d’un paiement ou d’un nombre' },
  assemblyQuorum: { label: 'Présences et quorum', icon: '⚖', hint: 'Viennent, procurations, quorum' },
  assemblyProxies: { label: 'Qui représente qui', icon: '⇄', hint: 'Les pouvoirs reçus' },
}

export const MEMBER_FIELDS = [
  ['last_name', 'Nom'],
  ['first_name', 'Prénom'],
  ['email', 'Email'],
  ['phone', 'Téléphone'],
]

export function walk(blocks = []) {
  const out = []
  for (const b of blocks) {
    out.push(b)
    out.push(...walk(b.children ?? []))
  }
  return out
}

export function questions(content) {
  return walk(content?.entry?.blocks).filter((b) => QUESTION_TYPES.includes(b.type) || ACT_TYPES.includes(b.type))
}

export function options(block) {
  return String(block.props?.options ?? '')
    .split('\n')
    .map((o) => o.trim())
    .filter(Boolean)
}

export function label(block) {
  return block.props?.label || BLOCKS[block.type]?.label || 'Question'
}

// Le contenu sans les blocs qui n'existent pas dans cette nature
// (changement de nature, fichier-de-base.md §1).
export function dropForFamily(content, family) {
  const permis = FAMILY_TYPES[family]
  const garder = (blocs = []) =>
    blocs.filter((b) => permis.includes(b.type)).map((b) => ({ ...b, children: garder(b.children) }))
  return {
    schema: 1,
    entry: { blocks: garder(content.entry?.blocks) },
    result: { blocks: family === 'inform' ? [] : (content.result?.blocks ?? []) },
  }
}

const nouvelId = () => (crypto.randomUUID ? crypto.randomUUID() : `b${Date.now()}${Math.random().toString(16).slice(2)}`)

// Formulaire de résultat fabriqué tout seul à partir des questions
// (fichier-de-base.md §2.1) : compteur, un graphique par choix, un total par
// paiement ou nombre, puis le tableau.
export function defaultResultBlocks(content) {
  const qs = questions(content)
  const bloc = (type, props = {}) => ({ id: nouvelId(), type, props, children: [] })
  const ag = qs.some((q) => q.type === 'assembly') ? [bloc('assemblyQuorum'), bloc('assemblyProxies')] : []
  return [
    ...ag,
    bloc('responseCount'),
    ...qs.filter((q) => q.type === 'choice' || q.type === 'yesNo').map((q) => bloc('choiceChart', { questionId: q.id })),
    ...qs.filter((q) => q.type === 'payment' || q.type === 'number').map((q) => bloc('total', { questionId: q.id })),
    bloc('responseTable'),
  ]
}

export function resultBlocks(content) {
  const blocs = content?.result?.blocks ?? []
  return blocs.length ? blocs : defaultResultBlocks(content)
}

// Une valeur de réponse en texte court (tableau, export).
export function formatValue(q, v) {
  if (v == null || v === '') return ''
  if (q.type === 'yesNo') return v ? 'Oui' : 'Non'
  if (q.type === 'choice') return Array.isArray(v) ? v.join(', ') : String(v)
  if (q.type === 'signature') return 'Signé'
  if (q.type === 'assembly') {
    if (v.answer !== 'proxy') return ASSEMBLY_ANSWERS[v.answer] ?? ''
    return `Procuration à ${v.proxy_to === 'blank' ? 'le bureau' : v.proxy_name ?? '?'}`
  }
  if (q.type === 'payment') return `${euros(v.amount)}${v.test ? ' (essai)' : ''}`
  if (q.type === 'member') return [v.first_name, v.last_name, v.email].filter(Boolean).join(' ')
  if (q.type === 'date') return new Date(`${v}T12:00`).toLocaleDateString('fr-FR')
  if (q.type === 'number') return Number(v).toLocaleString('fr-FR')
  return String(v)
}

export const ASSEMBLY_ANSWERS = { attend: 'Vient', proxy: 'Procuration', absent: 'Ne vient pas', none: 'Pas encore répondu' }

export const assemblyBlock = (content) => walk(content?.entry?.blocks).find((b) => b.type === 'assembly')
// Procès-verbal d'AG : son bloc Signature porte l'id de la convocation.
export const minutesBlock = (content) => walk(content?.entry?.blocks).find((b) => b.type === 'signature' && b.props?.minutesOf > 0)

export const euros = (n) => `${Number(n ?? 0).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 })} €`

// Onglet d'ouverture et onglets disponibles selon l'état
// (fichier-de-base.md §2.2 et §4).
export function tabReason(tab, status) {
  if (tab === 'prep') return status === 'draft' || !status ? null : 'Repassez en Brouillon pour modifier'
  if (tab === 'diffuse') return status === 'draft' || !status ? 'Validez d’abord le fichier' : null
  if (tab === 'results') return status === 'official' ? null : 'Les résultats s’ouvrent quand le fichier est Officiel'
  return null
}

export function openingTab(file) {
  if (!file.can_edit) return 'preview'
  if (file.status === 'validated') return 'diffuse'
  if (file.status === 'official') return file.family === 'inform' ? 'preview' : 'results'
  return 'prep'
}

// Un fichier reçu du serveur, enregistré par le navigateur.
export function telecharger(blob, nom) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nom
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// Aperçu modifiable (procurations.md §1.3, Seb 21 octobre) : le texte brut
// d'un bloc, et le bloc `id` (cherché aussi dans les enfants) avec son
// nouveau texte. Le style est gardé s'il était le même sur tout le bloc.
export function texteBrut(content) {
  if (typeof content === 'string') return content
  return (content ?? []).map((m) => (m.type === 'link' ? texteBrut(m.content) : m.text ?? '')).join('')
}

export function avecTexte(blocks, id, texte) {
  return blocks.map((b) => {
    if (b.id === id) {
      const morceaux = Array.isArray(b.content) ? b.content : []
      const styles = morceaux.length && morceaux.every((m) => JSON.stringify(m.styles ?? {}) === JSON.stringify(morceaux[0].styles ?? {}))
        ? morceaux[0].styles ?? {}
        : {}
      return { ...b, content: texte ? [{ type: 'text', text: texte, styles }] : [] }
    }
    return b.children?.length ? { ...b, children: avecTexte(b.children, id, texte) } : b
  })
}
