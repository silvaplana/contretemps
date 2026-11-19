// Texte mis en forme (Seb, 19 novembre ; maquette « Texte mis en forme »,
// spec actualites.md §12.15) : gras, souligné et deux tailles, gardés dans le
// texte par de petites balises — [g]gras[/g], [s]souligné[/s],
// [grand]…[/grand], [petit]…[/petit] — que le serveur lit pareil
// (backend publications/formatting.py) pour le mail et les notifications.

const BALISE = /\[(\/?)(g|s|grand|petit)\]/g

// Le texte en morceaux : [{ texte, g, s, taille }] (taille : 'grand',
// 'petit' ou null). Une balise fermée sans être ouverte est ignorée.
export function analyser(texte) {
  const morceaux = []
  const etat = { g: false, s: false, taille: null }
  let position = 0
  const pousser = (bout) => bout && morceaux.push({ texte: bout, ...etat })
  for (const m of (texte ?? '').matchAll(BALISE)) {
    pousser(texte.slice(position, m.index))
    position = m.index + m[0].length
    const [, fermer, nom] = m
    if (nom === 'g' || nom === 's') etat[nom] = !fermer
    else if (!fermer) etat.taille = nom
    else if (etat.taille === nom) etat.taille = null
  }
  pousser((texte ?? '').slice(position))
  return morceaux
}

// Le texte sans ses balises (nom d'un brouillon, recherche…).
export const sansBalises = (texte) => (texte ?? '').replace(BALISE, '')

// Pour WhatsApp, qui écrit le gras *ainsi* et n'a ni souligné ni tailles.
export const pourWhatsApp = (texte) =>
  analyser(texte)
    // Ligne par ligne : WhatsApp ne met pas en gras d'une ligne à l'autre.
    .map((m) => (m.g ? m.texte.replace(/^([ \t]*)(\S.*?)([ \t]*)$/gm, '$1*$2*$3') : m.texte))
    .join('')

// --- L'éditeur (un bloc modifiable du navigateur) ---

// Les tailles de execCommand('fontSize') : 2 petit, 3 normal, 5 grand.
export const TAILLES = { petit: '2', normal: '3', grand: '5' }
const tailleDe = (valeur) => (Number(valeur) <= 2 ? 'petit' : Number(valeur) >= 5 ? 'grand' : null)

// Le contenu du bloc modifiable, en texte à balises. Ce que le navigateur
// ajoute d'autre (un collage, une police) est oublié : seul le texte reste.
export function versBalises(racine) {
  const morceaux = []
  const etat = { g: false, s: false, taille: null }
  const ajouter = (texte) => texte && morceaux.push({ texte, ...etat })
  const parcourir = (noeud, premier) => {
    if (noeud.nodeType === Node.TEXT_NODE) return ajouter(noeud.nodeValue.replace(/ /g, ' '))
    if (noeud.nodeType !== Node.ELEMENT_NODE) return undefined
    const nom = noeud.nodeName
    if (nom === 'BR') return ajouter('\n')
    // Chrome met chaque nouvelle ligne dans un <div>.
    if ((nom === 'DIV' || nom === 'P') && !premier) ajouter('\n')
    const avant = { ...etat }
    if (nom === 'B' || nom === 'STRONG' || Number(noeud.style?.fontWeight) >= 600) etat.g = true
    if (nom === 'U' || noeud.style?.textDecorationLine?.includes('underline')) etat.s = true
    if (nom === 'FONT' && noeud.getAttribute('size')) etat.taille = tailleDe(noeud.getAttribute('size'))
    noeud.childNodes.forEach((enfant, i) => parcourir(enfant, premier && i === 0))
    Object.assign(etat, avant)
    return undefined
  }
  racine.childNodes.forEach((enfant, i) => parcourir(enfant, i === 0))
  // Le <br> que Chrome laisse au bout d'une ligne vide.
  if (morceaux.length && morceaux[morceaux.length - 1].texte === '\n') morceaux.pop()
  return ecrire(morceaux)
}

// Des morceaux au texte à balises, sans balise inutile.
function ecrire(morceaux) {
  let sortie = ''
  let avant = { g: false, s: false, taille: null }
  const fermer = (a, b) => {
    if (a.taille && a.taille !== b.taille) sortie += `[/${a.taille}]`
    if (a.s && !b.s) sortie += '[/s]'
    if (a.g && !b.g) sortie += '[/g]'
  }
  const ouvrir = (a, b) => {
    if (b.g && !a.g) sortie += '[g]'
    if (b.s && !a.s) sortie += '[s]'
    if (b.taille && a.taille !== b.taille) sortie += `[${b.taille}]`
  }
  for (const m of morceaux) {
    // Fermer puis rouvrir garde les balises bien rangées.
    fermer(avant, m)
    ouvrir(avant, m)
    sortie += m.texte
    avant = m
  }
  fermer(avant, { g: false, s: false, taille: null })
  return sortie
}

// Remplit le bloc modifiable avec un texte à balises (en créant les éléments
// un à un : jamais de HTML tiré du texte).
export function remplir(racine, texte) {
  racine.replaceChildren()
  for (const m of analyser(texte)) {
    m.texte.split('\n').forEach((ligne, i) => {
      if (i > 0) racine.append(document.createElement('br'))
      if (!ligne) return
      let noeud = document.createTextNode(ligne)
      if (m.taille) {
        const font = document.createElement('font')
        font.setAttribute('size', TAILLES[m.taille])
        font.append(noeud)
        noeud = font
      }
      if (m.s) {
        const u = document.createElement('u')
        u.append(noeud)
        noeud = u
      }
      if (m.g) {
        const b = document.createElement('b')
        b.append(noeud)
        noeud = b
      }
      racine.append(noeud)
    })
  }
}
