import { useEffect, useState } from 'react'
import * as auth from '../api/auth.js'
import Logo from '../components/Logo.jsx'

// Choix de l'école (Superuser seulement, voir spec/SPEC.md §2.5) : juste
// après sa connexion, ou via "Changer d'école" dans Profil. Le Superuser
// n'appartient à aucune école ; il voit ensuite celle choisie comme un
// Owner. Il est aussi le seul à pouvoir créer une école (en bas).
export default function ChoixEcoleScreen({ onChoisir, onLogout }) {
  const [ecoles, setEcoles] = useState(null)
  const [erreur, setErreur] = useState('')
  const [creationOuverte, setCreationOuverte] = useState(false)

  useEffect(() => {
    auth
      .listerEcoles()
      .then(setEcoles)
      .catch((err) => setErreur(err.message))
  }, [])

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={80} />
        <h1>Choisir une école</h1>
        <p>Accès Super User</p>
      </div>

      <div className="login-screen__form">
        {ecoles === null && !erreur && <p className="muted">Chargement…</p>}
        {ecoles?.length === 0 && <p className="muted">Aucune école pour l’instant.</p>}
        {ecoles?.map((e) => (
          <button key={e.id} type="button" className="btn btn--primary btn--block" onClick={() => onChoisir(e)}>
            {e.nom} ({e.codePostal})
          </button>
        ))}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        {creationOuverte ? (
          <NouvelleEcoleForm onCreee={onChoisir} onAnnuler={() => setCreationOuverte(false)} />
        ) : (
          <button type="button" className="btn btn--link" onClick={() => setCreationOuverte(true)}>
            Créer une école
          </button>
        )}
        <button type="button" className="btn btn--link" onClick={onLogout}>
          Se déconnecter
        </button>
      </div>
    </div>
  )
}

// Nom + code postal (le couple doit être unique, §6.1) + les 3 codes
// d'accès. Le premier administrateur se crée ensuite depuis Admin > École
// (menu ⋮ > "Créer nouvel administrateur") : il en deviendra l'Owner.
function NouvelleEcoleForm({ onCreee, onAnnuler }) {
  const [champs, setChamps] = useState({
    nom: '',
    codePostal: '',
    codeAccesAdmin: '',
    codeAccesProf: '',
    codeAccesEleve: '',
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const complet = Object.values(champs).every((v) => v.trim())

  function changer(cle) {
    return (e) => setChamps((c) => ({ ...c, [cle]: e.target.value }))
  }

  async function creer(e) {
    e.preventDefault()
    if (!complet || enCours) return
    setErreur('')
    setEnCours(true)
    try {
      onCreee(await auth.creerEcole(Object.fromEntries(Object.entries(champs).map(([k, v]) => [k, v.trim()]))))
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <form className="login-screen__form" onSubmit={creer}>
      <label htmlFor="nouvelle-ecole-nom">Nom de l’école</label>
      <input id="nouvelle-ecole-nom" value={champs.nom} onChange={changer('nom')} />
      <label htmlFor="nouvelle-ecole-cp">Code postal</label>
      <input id="nouvelle-ecole-cp" value={champs.codePostal} onChange={changer('codePostal')} />
      <label htmlFor="nouvelle-ecole-admin">Code d’accès Admin</label>
      <input id="nouvelle-ecole-admin" value={champs.codeAccesAdmin} onChange={changer('codeAccesAdmin')} />
      <label htmlFor="nouvelle-ecole-prof">Code d’accès Professeur</label>
      <input id="nouvelle-ecole-prof" value={champs.codeAccesProf} onChange={changer('codeAccesProf')} />
      <label htmlFor="nouvelle-ecole-eleve">Code d’accès Élève</label>
      <input id="nouvelle-ecole-eleve" value={champs.codeAccesEleve} onChange={changer('codeAccesEleve')} />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button type="submit" className="btn btn--primary btn--block" disabled={!complet || enCours}>
        Créer l’école
      </button>
      <button type="button" className="btn btn--link" onClick={onAnnuler}>
        Annuler
      </button>
    </form>
  )
}
