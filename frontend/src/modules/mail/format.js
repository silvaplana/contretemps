// Dates, tailles et noms de la boîte mail, comme Sambo Admin (Webmail.jsx).

export function dateListe(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const maintenant = new Date()
  if (date.toDateString() === maintenant.toDateString()) {
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  }
  if (date.getFullYear() === maintenant.getFullYear()) {
    return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
  }
  return date.toLocaleDateString('fr-FR')
}

export function dateComplete(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function taille(octets) {
  if (octets == null) return ''
  if (octets < 1024) return `${octets} o`
  if (octets < 1024 * 1024) return `${Math.round(octets / 1024)} Ko`
  return `${(octets / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`
}

export const nom = (personne) => (personne ? personne.name || personne.address : '')

export const adresse = (personne) => (personne.name ? `${personne.name} <${personne.address}>` : personne.address)

export function initiales(texte) {
  const mots = (texte || '?').replace(/[<>"@.]/g, ' ').trim().split(/\s+/)
  return mots
    .slice(0, 2)
    .map((m) => m[0] ?? '')
    .join('')
    .toUpperCase()
}
