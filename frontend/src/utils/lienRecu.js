// Lien reçu par mail (voir spec/SPEC.md §2.2) : invitation
// (…/activer?jeton=…) ou mot de passe oublié (…/reinitialiser?jeton=…).
// L'appli s'ouvre alors sur « Créer mon mot de passe » (voir App.jsx et
// screens/CreerMotDePasseScreen.jsx) au lieu de l'écran habituel.

export function lienRecu() {
  const chemin = location.pathname.replace(/\/$/, '')
  if (!/\/(activer|reinitialiser)$/.test(chemin)) return null
  return new URLSearchParams(location.search).get('jeton') || null
}

// Retour à l'adresse normale de l'appli une fois le lien traité : ni un
// rechargement ni un favori ne doivent rouvrir cet écran avec un lien qui
// ne sert qu'une fois.
export function oublierLienRecu() {
  history.replaceState(null, '', import.meta.env.BASE_URL)
}

// Lien du mail de rappel (personne qui a déjà son mot de passe, voir
// backend auth/mails.py : rappel) : …/?identifiant=Prénom+Nom. L'écran de
// connexion s'ouvre avec « Nom Prénom ou Email » déjà rempli. Lu une seule
// fois, puis retiré de l'adresse.
export function identifiantPropose() {
  const url = new URL(location.href)
  const valeur = url.searchParams.get('identifiant')
  if (valeur === null) return ''
  url.searchParams.delete('identifiant')
  history.replaceState(history.state, '', url)
  return valeur.trim()
}
