// Petits textes de l'explorateur : tailles, dates, historique.

export function formatSize(octets) {
  if (octets == null) return ''
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`
  return `${(octets / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`
}

// Dates du serveur : UTC sans fuseau (voir documents/models.py utcnow).
function versDate(iso) {
  return new Date(iso.endsWith('Z') ? iso : `${iso}Z`)
}

export function formatDate(iso) {
  if (!iso) return ''
  const d = versDate(iso)
  const aujourdhui = new Date()
  const hier = new Date()
  hier.setDate(aujourdhui.getDate() - 1)
  const heure = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  if (d.toDateString() === aujourdhui.toDateString()) return `aujourd'hui ${heure}`
  if (d.toDateString() === hier.toDateString()) return `hier ${heure}`
  const options = { day: 'numeric', month: 'short' }
  if (d.getFullYear() !== aujourdhui.getFullYear()) options.year = 'numeric'
  return d.toLocaleDateString('fr-FR', options)
}

export function subtitle(item) {
  if (item.kind === 'folder') {
    const n = item.child_count ?? 0
    if (item.closed_period) return `${n} élément${n > 1 ? 's' : ''} · saison terminée`
    return `${n} élément${n > 1 ? 's' : ''}`
  }
  return [formatSize(item.size), formatDate(item.updated_at), item.updated_by].filter(Boolean).join(' · ')
}

// Ligne d'un élément du bac Échanges (§4.7 ter) : « De Marie · pour vous · reste 12 j ».
export function exchangeSubtitle(item) {
  const jours = Math.max(0, Math.ceil((versDate(item.exchange_until) - new Date()) / 86400000))
  const pour = item.for_me ? 'pour vous' : item.for_label ? `pour ${item.for_label}` : ''
  return [
    item.sent_by_me ? 'Déposé par vous' : item.sender && `De ${item.sender}`,
    pour,
    item.sent_by_me && item.for_label && item.picked ? 'récupéré' : '',
    jours > 1 ? `reste ${jours} j` : 'part demain à la corbeille',
  ]
    .filter(Boolean)
    .join(' · ')
}

const LEVELS = { view: 'Peut voir', edit: 'Peut modifier', manage: 'Gère tout' }
export const levelLabel = (level) => LEVELS[level] ?? ''

const STATUS_NAMES = { draft: 'Brouillon', validated: 'Validé', official: 'Officiel' }

export function historyText(h) {
  const d = h.detail ?? {}
  const qui = h.by ?? 'Quelqu’un'
  switch (h.action) {
    case 'created':
      return `${qui} a créé le dossier`
    case 'uploaded':
      return `${qui} a importé le fichier`
    case 'new_version':
      return `${qui} a envoyé une nouvelle version`
    case 'renamed':
      return `${qui} a renommé « ${d.from} » en « ${d.to} »`
    case 'moved':
      return `${qui} a déplacé de ${d.from} vers ${d.to}`
    case 'copied':
      return `${qui} a créé cette copie de « ${d.from} »`
    case 'status':
      return d.to ? `${qui} a passé en ${STATUS_NAMES[d.to]}` : `${qui} a retiré le statut`
    case 'deleted':
      return `${qui} a mis à la corbeille`
    case 'restored':
      return `${qui} a restauré depuis la corbeille`
    case 'shared':
      return `${qui} a partagé avec ${d.who} (${d.level === 'edit' ? 'peut modifier' : 'peut voir'})`
    case 'unshared':
      return `${qui} a retiré l’accès de ${d.who}`
    case 'edited':
      return `${qui} a modifié le contenu (version ${d.version})`
    case 'family':
      return `${qui} a changé la nature`
    case 'template':
      return `${qui} en a fait le modèle « ${d.name} »`
    case 'restricted':
      return `${qui} a restreint l’accès`
    case 'reminded':
      return `Rappel envoyé à ${d.count} membre${d.count > 1 ? 's' : ''} sans réponse`
    case 'unrestricted':
      return `${qui} a remis l’accès comme le dossier`
    default:
      return `${qui} : ${h.action}`
  }
}
