import { useEffect, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'

// Les blogs de l'école, sous la case Publications de Fonctionnalités
// (spec/modules/actualites.md §12.3, maquette spec/maquettes/blog.html) :
// pour chacun son nom (celui de son onglet et de son droit de publier), son
// logo, « Avec des catégories », « Avec les niveaux… » ; puis « + Ajouter un
// blog ». Chaque réglage s'enregistre tout de suite. La ligne est
// l'étiquette de la case : un clic hors d'un bouton ou d'un champ ne doit
// pas la cocher.

const LOGOS = [
  ['news', 'journal'],
  ['books', 'livres'],
  ['video', 'caméra'],
  ['cap', 'toque'],
  ['star', 'étoile'],
  ['cup', 'coupe'],
]

function Interrupteur({ libelle, valeur, onChanger }) {
  return (
    <div className="blogs__option">
      <span>{libelle}</span>
      <button type="button" role="switch" aria-checked={valeur} aria-label={libelle} className="actus__interrupteur" onClick={() => onChanger(!valeur)} />
    </div>
  )
}

function UnBlog({ blog, onChanger, onSupprimer }) {
  const [nom, setNom] = useState(blog.nom)
  useEffect(() => setNom(blog.nom), [blog.nom])
  return (
    <div className="blogs__blog">
      <input
        className="blogs__nom"
        aria-label="Nom du blog"
        value={nom}
        onChange={(e) => setNom(e.target.value)}
        onBlur={() => (nom.trim() && nom.trim() !== blog.nom ? onChanger({ name: nom.trim() }) : setNom(blog.nom))}
      />
      <div className="blogs__logos" role="group" aria-label="Logo de l’onglet">
        {LOGOS.map(([cle, libelle]) => (
          <button key={cle} type="button" aria-label={`Logo ${libelle}`} aria-pressed={blog.icone === cle} onClick={() => onChanger({ icon: cle })}>
            <Icon name={cle} size={22} />
          </button>
        ))}
      </div>
      <Interrupteur libelle="Avec des catégories" valeur={blog.avecCategories} onChanger={(v) => onChanger({ with_categories: v })} />
      <Interrupteur libelle="Avec les niveaux Important, Normal, Brève" valeur={blog.avecNiveaux} onChanger={(v) => onChanger({ with_levels: v })} />
      {onSupprimer && (
        <button type="button" className="blogs__supprimer" onClick={onSupprimer}>
          Supprimer ce blog
        </button>
      )}
    </div>
  )
}

export default function Blogs({ ecole, enabled }) {
  const [blogs, setBlogs] = useState([])
  const [ajout, setAjout] = useState(null) // le nom du nouveau blog, ou null
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    if (enabled) api.lireBlogs(ecole.id).then(setBlogs)
  }, [ecole.id, enabled])

  async function agir(action) {
    setErreur('')
    try {
      await action()
      setBlogs(await api.lireBlogs(ecole.id))
      // La barre du bas suit (nom, logo, nouvel onglet).
      window.dispatchEvent(new Event('publications:blogs'))
    } catch (e) {
      setErreur(e.message)
    }
  }

  if (!enabled) return null
  return (
    // Un clic dans la liste ne coche pas la case du module.
    <div className="blogs" onClick={(e) => !e.target.closest('button, input') && e.preventDefault()}>
      {blogs.map((b) => (
        <UnBlog
          key={b.id}
          blog={b}
          onChanger={(changement) => agir(() => api.changerBlog(ecole.id, b.id, changement))}
          // Seulement un blog vide, jamais le dernier (§12.10).
          onSupprimer={blogs.length > 1 ? () => agir(() => api.supprimerBlog(ecole.id, b.id)) : null}
        />
      ))}
      {ajout === null ? (
        <button type="button" className="blogs__ajouter" onClick={() => setAjout('')}>
          + Ajouter un blog
        </button>
      ) : (
        <div className="editeur__lien">
          <input aria-label="Nom du blog" placeholder="Nom du blog" value={ajout} autoFocus onChange={(e) => setAjout(e.target.value)} />
          <button
            type="button"
            disabled={!ajout.trim()}
            onClick={() =>
              agir(async () => {
                await api.ajouterBlog(ecole.id, ajout.trim())
                setAjout(null)
              })
            }
          >
            OK
          </button>
        </div>
      )}
      {erreur && <p className="parametres__erreur">{erreur}</p>}
    </div>
  )
}
