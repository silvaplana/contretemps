import { useEffect, useState } from 'react'
import * as api from './api.js'

// Catégories d'un blog (spec/modules/actualites.md §12.6, maquette
// spec/maquettes/blog.html) : l'onglet « Catégories », et le choix de la
// catégorie dans l'éditeur. Une catégorie existe tant qu'une publication y
// est rangée ; pas d'écran de gestion à part.

const alpha = (a, b) => a.localeCompare(b, 'fr', { sensitivity: 'base' })
const total = (c) => c.nombre + c.sous.reduce((n, s) => n + s.nombre, 0)
const sansAccent = (texte) => texte.normalize('NFD').replace(/[̀-ͯ]/g, '')
const lettre = (nom) => sansAccent(nom.trim().charAt(0)).toUpperCase()

function trouver(arbre, id) {
  for (const c of arbre) {
    if (c.id === id) return { categorie: c, parent: null }
    const s = c.sous.find((x) => x.id === id)
    if (s) return { categorie: s, parent: c }
  }
  return null
}

const Retour = ({ onClick }) => (
  <button type="button" className="actus__retour" aria-label="Retour" onClick={onClick}>
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M19 12H5M11 18l-6-6 6-6" />
    </svg>
  </button>
)

// Ce que contient une publication, sur sa ligne : « Vidéo », « Photo »…
function nature(a) {
  if (a.media.some((m) => m.video)) return 'Vidéo'
  if (a.media.some((m) => m.lien)) return 'Lien'
  if (a.media.length) return 'Photo'
  if (a.document) return 'Document'
  return 'Texte'
}

function Ligne({ nom, detail, onClick }) {
  return (
    <button type="button" className="categories__ligne" onClick={onClick}>
      <span>{nom}</span>
      <small>{detail}</small>
    </button>
  )
}

// L'onglet Catégories : la liste par lettre, puis une catégorie (ses
// sous-catégories et ses publications), puis une publication seule. ←
// remonte d'un cran.
export default function Categories({ lieu, version, publications, ouverte, onOuvrir, peutRenommer, onRenomme, rendreCarte }) {
  const [arbre, setArbre] = useState(null)
  const [erreur, setErreur] = useState('')
  const [billet, setBillet] = useState(null) // la publication ouverte seule
  const [nom, setNom] = useState(null) // le nouveau nom en cours, ou null

  useEffect(() => {
    api.lireCategories(lieu).then(setArbre, (e) => setErreur(e.message))
  }, [lieu, version])
  useEffect(() => {
    setBillet(null)
    setNom(null)
  }, [ouverte])

  if (erreur) return <p className="actus__vide">{erreur}</p>
  if (!arbre) return null

  if (billet) {
    const a = publications.find((p) => p.id === billet)
    return (
      <div className="categories">
        <div className="actus__entete">
          <Retour onClick={() => setBillet(null)} />
          <strong>{a ? [...a.categories.map((c) => c.nom), a.titre].join(' › ') : ''}</strong>
        </div>
        {a && rendreCarte(a)}
      </div>
    )
  }

  const trouvee = ouverte != null ? trouver(arbre, ouverte) : null
  if (!trouvee) {
    if (!arbre.length) return <p className="actus__vide">Pas encore de catégorie.</p>
    const triees = [...arbre].sort((a, b) => alpha(a.nom, b.nom))
    return (
      <div className="categories">
        {triees.map((c, i) => (
          <div key={c.id}>
            {(i === 0 || lettre(c.nom) !== lettre(triees[i - 1].nom)) && <div className="actus__periode">{lettre(c.nom)}</div>}
            <Ligne nom={c.nom} detail={total(c)} onClick={() => onOuvrir(c.id)} />
          </div>
        ))}
      </div>
    )
  }

  const { categorie, parent } = trouvee
  const dedans = publications
    .filter((a) => a.categories[a.categories.length - 1]?.id === categorie.id)
    .sort((a, b) => alpha(a.titre, b.titre))

  async function renommer(e) {
    e.preventDefault()
    try {
      const nouvelArbre = await api.renommerCategorie(lieu, categorie.id, nom.trim())
      setArbre(nouvelArbre)
      setNom(null)
      // Réunie avec une autre : on ouvre celle qui reste.
      if (!trouver(nouvelArbre, categorie.id)) {
        const meme = (liste) => liste.find((c) => alpha(c.nom, nom.trim()) === 0)
        const reste = parent ? meme(trouver(nouvelArbre, parent.id)?.categorie.sous ?? []) : meme(nouvelArbre)
        onOuvrir(reste?.id ?? parent?.id ?? null)
      }
      onRenomme()
    } catch (erreur) {
      window.alert(erreur.message)
    }
  }

  return (
    <div className="categories">
      <div className="actus__entete">
        <Retour onClick={() => onOuvrir(parent?.id ?? null)} />
        <strong>{parent ? `${parent.nom} › ${categorie.nom}` : categorie.nom}</strong>
      </div>
      {peutRenommer &&
        (nom === null ? (
          <button type="button" className="categories__renommer" onClick={() => setNom(categorie.nom)}>
            Renommer « {categorie.nom} »
          </button>
        ) : (
          <form className="editeur__lien" onSubmit={renommer}>
            <input aria-label="Nouveau nom" value={nom} autoFocus onChange={(e) => setNom(e.target.value)} />
            <button type="submit" disabled={!nom.trim()}>
              OK
            </button>
          </form>
        ))}
      {[...categorie.sous]
        .sort((a, b) => alpha(a.nom, b.nom))
        .map((s) => (
          <Ligne key={s.id} nom={s.nom} detail={s.nombre} onClick={() => onOuvrir(s.id)} />
        ))}
      {dedans.length > 0 && categorie.sous.length > 0 && <div className="actus__periode">Rangées ici</div>}
      {dedans.map((a) => (
        <Ligne key={a.id} nom={a.titre} detail={a.publieeLe ? nature(a) : `${nature(a)} · Brouillon`} onClick={() => setBillet(a.id)} />
      ))}
    </div>
  )
}

// Dans l'éditeur : la catégorie en gros boutons (ordre alphabétique) et
// « + Nouvelle » ; puis, de même, la sous-catégorie, facultative. Pas de
// hashtag tapé à la main : pas de doublon par faute de frappe.
// `onSaisie(quoi, texte)` : le nom tapé dans « + Nouvelle » avant OK, que
// l'éditeur garde s'il publie sans OK.
export function ChoixCategorie({ lieu, categorie, sousCategorie, onChanger, onSaisie = () => {} }) {
  const [arbre, setArbre] = useState([])
  const [nouvelle, setNouvelle] = useState(null) // 'cat' | 'sous' | null
  const [nom, setNom] = useState('')
  useEffect(() => {
    api.lireCategories(lieu).then(setArbre, () => setArbre([]))
  }, [lieu])

  const memeNom = (a, b) => alpha(a, b) === 0
  const existantes = arbre.map((c) => c.nom)
  const choisie = arbre.find((c) => memeNom(c.nom, categorie))
  const sousExistantes = choisie ? choisie.sous.map((s) => s.nom) : []
  // Une nouvelle, pas encore enregistrée, se montre avec les autres.
  const avec = (liste, valeur) => (valeur && !liste.some((n) => memeNom(n, valeur)) ? [...liste, valeur] : liste)

  function valider(e) {
    e.preventDefault()
    const valeur = nom.trim()
    if (!valeur) return
    if (nouvelle === 'cat') onChanger(valeur, '')
    else onChanger(categorie, valeur)
    onSaisie(nouvelle, '')
    setNouvelle(null)
    setNom('')
  }

  function puces(liste, valeur, quoi, choisir) {
    return (
      <div className="editeur__puces">
        {[...liste].sort(alpha).map((n) => (
          <button key={n} type="button" aria-pressed={memeNom(n, valeur)} onClick={() => choisir(memeNom(n, valeur) ? '' : n)}>
            {n}
          </button>
        ))}
        <button
          type="button"
          aria-pressed={nouvelle === quoi}
          onClick={() => {
            onSaisie(nouvelle ?? quoi, '')
            setNom('')
            setNouvelle(nouvelle === quoi ? null : quoi)
          }}
        >
          + Nouvelle
        </button>
      </div>
    )
  }

  const champ = (quoi) =>
    nouvelle === quoi && (
      <form className="editeur__lien" onSubmit={valider}>
        <input
          aria-label="Nom"
          placeholder={quoi === 'cat' ? 'Nouvelle catégorie' : 'Nouvelle sous-catégorie'}
          value={nom}
          autoFocus
          onChange={(e) => {
            setNom(e.target.value)
            onSaisie(quoi, e.target.value)
          }}
        />
        <button type="submit" disabled={!nom.trim()}>
          OK
        </button>
      </form>
    )

  return (
    <div className="editeur__categories">
      <div className="actus__periode">Catégorie</div>
      {puces(avec(existantes, categorie), categorie, 'cat', (n) => onChanger(n, ''))}
      {champ('cat')}
      {categorie && (
        <>
          <div className="actus__periode">Sous-catégorie (facultatif)</div>
          {puces(avec(sousExistantes, sousCategorie), sousCategorie, 'sous', (n) => onChanger(categorie, n))}
          {champ('sous')}
        </>
      )}
    </div>
  )
}
