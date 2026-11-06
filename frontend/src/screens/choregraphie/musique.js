// Musique d'une chorégraphie (Seb, 6 novembre) : auteur, titre et durée,
// tous facultatifs. La durée s'écrit « 3:45 » et se garde en secondes.

// 225 → "3:45" ; null → "".
export function formatDuree(secondes) {
  if (secondes == null) return ''
  return `${Math.floor(secondes / 60)}:${String(secondes % 60).padStart(2, '0')}`
}

// "3:45" → 225 ; "" → null ; texte illisible → undefined.
export function lireDuree(texte) {
  const t = texte.trim()
  if (!t) return null
  const m = /^(\d{1,3}):([0-5]\d)$/.exec(t)
  return m ? Number(m[1]) * 60 + Number(m[2]) : undefined
}

// « Auteur, Titre (3:45) », ou "" s'il n'y a rien.
export function texteMusique(ch) {
  const texte = [ch.musicAuthor, ch.musicTitle].filter(Boolean).join(', ')
  const duree = formatDuree(ch.musicDurationSeconds)
  return [texte, duree && `(${duree})`].filter(Boolean).join(' ')
}
