// Dates de la messagerie, façon WhatsApp (spec/modules/messagerie-instantanee.md
// §4.8).

// Le serveur renvoie ses dates en UTC sans fuseau (SQLite) : sans le « Z »,
// le navigateur les lirait en heure locale, deux heures trop tôt en été.
export function dateServeur(texte) {
  if (!texte) return null
  return new Date(/Z|[+-]\d\d:\d\d$/.test(texte) ? texte : `${texte}Z`)
}

function debutDuJour(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function joursEcoules(date, maintenant) {
  return Math.round((debutDuJour(maintenant) - debutDuJour(date)) / 86_400_000)
}

function majuscule(texte) {
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

// Séparateur entre les messages : « Aujourd'hui », « Hier », le jour de la
// semaine passée, puis la date (l'année seulement si ce n'est pas celle-ci).
export function libelleJour(date, maintenant = new Date()) {
  const jours = joursEcoules(date, maintenant)
  if (jours === 0) return "Aujourd'hui"
  if (jours === 1) return 'Hier'
  if (jours < 7) return majuscule(date.toLocaleDateString('fr-FR', { weekday: 'long' }))
  const annee = date.getFullYear() === maintenant.getFullYear() ? undefined : 'numeric'
  return date.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: annee })
}

// À droite d'une ligne de la liste : l'heure aujourd'hui, sinon le jour.
export function libelleListe(date, maintenant = new Date()) {
  const jours = joursEcoules(date, maintenant)
  if (jours === 0) return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  if (jours === 1) return 'Hier'
  if (jours < 7) return majuscule(date.toLocaleDateString('fr-FR', { weekday: 'long' }))
  return date.toLocaleDateString('fr-FR')
}

// Un message encore dans la boîte d'envoi n'a pas de date : il est d'à l'instant.
export function dateDuMessage(m) {
  return dateServeur(m.envoyeLe) ?? new Date()
}

// Moment qui classe une conversation dans la liste : son dernier message,
// sinon sa création. Les plus récentes en haut.
export function dernierMoment(c) {
  const dernier = c.messages[c.messages.length - 1]
  if (dernier) return dateDuMessage(dernier)
  return dateServeur(c.creeLe)
}

export function plusRecentesDabord(conversations) {
  return [...conversations].sort(
    (a, b) => (dernierMoment(b)?.getTime() ?? 0) - (dernierMoment(a)?.getTime() ?? 0) || b.id - a.id,
  )
}
