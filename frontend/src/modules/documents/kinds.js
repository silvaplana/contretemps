// Statuts, familles et types de fichiers (spec documents.md §7.1 bis, §7.1 ter).

export const STATUSES = {
  draft: { label: 'Brouillon', className: 'brouillon' },
  refused: { label: 'Refusé', className: 'refuse' },
  validated: { label: 'Validé', className: 'valide' },
  official: { label: 'Officiel', className: 'officiel' },
}

export const FAMILIES = {
  inform: { label: 'Informer', glyph: 'i', color: '#0e8a8a' },
  question: { label: 'Questionner', glyph: '?', color: '#7c4dce' },
  act: { label: 'Agir', glyph: '⚡', color: '#e07a2f' },
}

const EXTENSIONS = [
  [/\.pdf$/i, 'PDF', '#d9443a'],
  [/\.(docx?|odt|rtf)$/i, 'W', '#2f6fde'],
  [/\.(xlsx?|ods|csv)$/i, 'X', '#1f8a4c'],
  [/\.(pptx?|odp)$/i, 'P', '#d35230'],
  [/\.(jpe?g|png|gif|webp|heic|svg)$/i, 'IMG', '#7c4dce'],
  [/\.(mp4|mov|webm|avi)$/i, 'VID', '#3a2410'],
  [/\.(mp3|wav|m4a|ogg)$/i, '♪', '#3a2410'],
  [/\.(zip|rar|7z)$/i, 'ZIP', '#8a6a4a'],
  [/\.(txt|md)$/i, 'TXT', '#8a6a4a'],
]

export function fileType(name = '') {
  for (const [motif, label, color] of EXTENSIONS) {
    if (motif.test(name)) return { label, color }
  }
  return { label: '', color: '#8a6a4a' }
}

export function isImage(item) {
  return (item.mime ?? '').startsWith('image/')
}

export function isPdf(item) {
  return item.mime === 'application/pdf'
}

const extension = (item) => (item.name.match(/\.[^.]+$/)?.[0] ?? '').toLowerCase()

// Texte brut : affiché et modifiable dans l'appli.
export function isTexte(item) {
  return ['.txt', '.md', '.csv', '.log'].includes(extension(item)) || (item.mime ?? '').startsWith('text/plain')
}

// Word, Excel, PowerPoint (et OpenDocument) : aperçu en PDF fait par le serveur.
export function isOffice(item) {
  return ['.doc', '.docx', '.odt', '.rtf', '.xls', '.xlsx', '.ods', '.ppt', '.pptx', '.odp'].includes(extension(item))
}
