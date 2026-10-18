import { normaliserRecherche } from '../../utils/recherche.js'

// Outils communs aux écrans « Nouvelle discussion », « Nouveau groupe » et
// « Qui est dans le groupe ? » (spec/modules/messagerie-instantanee.md §2-3).

// Avatar Admin/Professeur dans une couleur distincte de celui d'un élève
// (voir .avatar--staff dans App.css).
export function estStaff(role) {
  return role === 'admin' || role === 'professeur'
}

export function initiales(compte) {
  return `${compte.prenom?.[0] ?? ''}${compte.nom?.[0] ?? ''}`.toUpperCase()
}

// Prénom puis nom, sans accents ni majuscules (spec §2.3).
export function trierParNom(liste, nomDe = (c) => `${c.prenom} ${c.nom}`) {
  return [...liste].sort((a, b) =>
    normaliserRecherche(nomDe(a)).localeCompare(normaliserRecherche(nomDe(b)), 'fr'),
  )
}

// Tous les comptes de l'école, une seule fois chacun, avec leur `role`
// (professeurs.js et eleves.js ne le portent pas, voir
// ConversationListScreen.jsx).
export function tousLesComptes(admins, professeurs, eleves) {
  const parId = new Map()
  for (const [liste, role] of [
    [admins, 'admin'],
    [professeurs, 'professeur'],
    [eleves, 'eleve'],
  ]) {
    for (const c of liste) if (!parId.has(c.id)) parId.set(c.id, { ...c, role: c.role ?? role })
  }
  return [...parId.values()]
}

// Les personnes réellement dans le groupe, à plat (spec §3.2) : chaque
// cours remplacé par ses élèves et ses profs, même règle que le serveur
// (backend/src/messagerie/conversations.py: membres_resolus). Chaque
// personne n'apparaît qu'une fois, avec `directe` (ajoutée elle-même) et
// `parCours` (noms des cours par lesquels elle est là).
export function personnesDuGroupe(membres, { admins, professeurs, eleves, cours, compteId }) {
  const comptes = new Map(tousLesComptes(admins, professeurs, eleves).map((c) => [c.id, c]))
  const resultat = new Map()
  function noter(compte, origine) {
    if (!compte) return
    const p = resultat.get(compte.id) ?? { ...compte, directe: false, parCours: [], moi: compte.id === compteId }
    if (origine === null) p.directe = true
    else if (!p.parCours.includes(origine)) p.parCours.push(origine)
    resultat.set(compte.id, p)
  }
  for (const m of membres) {
    if (m.type !== 'cours') {
      noter(comptes.get(m.id), null)
      continue
    }
    const c = cours.find((x) => x.id === m.id)
    if (!c) continue
    for (const el of eleves) if (el.coursIds?.includes(c.id)) noter(comptes.get(el.id), c.nom)
    for (const pr of professeurs) if (pr.coursIds?.includes(c.id)) noter(comptes.get(pr.id), c.nom)
  }
  // Le créateur est toujours ajouté au groupe (voir NouveauGroupeModal.jsx).
  noter(comptes.get(compteId), null)
  return trierParNom([...resultat.values()])
}

// Découpe `texte` autour de la partie qui correspond à `requete` (sans
// accents ni majuscules), pour la surligner : [avant, trouvé, après], ou
// null si rien ne correspond. La correspondance se cherche sur le texte
// normalisé, puis se reporte sur le texte d'origine caractère par
// caractère (un « é » normalisé peut compter 2 caractères).
export function decouperSurlignage(texte, requete) {
  const q = normaliserRecherche(requete.trim())
  if (!q) return null
  let normalise = ''
  const origine = []
  for (let i = 0; i < texte.length; i++) {
    const n = normaliserRecherche(texte[i])
    normalise += n
    for (let k = 0; k < n.length; k++) origine.push(i)
  }
  const debut = normalise.indexOf(q)
  if (debut < 0) return null
  const a = origine[debut]
  const b = origine[debut + q.length - 1] + 1
  return [texte.slice(0, a), texte.slice(a, b), texte.slice(b)]
}
