import { useEffect, useState } from 'react'
import * as administrateurs from '../api/administrateurs.js'
import * as auth from '../api/auth.js'
import * as sessionApi from '../api/session.js'
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

// Nom + code postal (le couple doit être unique, §6.1), et le premier
// administrateur (spec core.md §1, Seb 28 octobre) : prénom, nom, email.
// « Créer l'école » crée l'école, puis cet administrateur, qui en devient
// l'administrateur principal, puis lui envoie son invitation. L'école
// s'ouvre ensuite sur Admin › École, avec un mot d'accueil
// (AdminParametres.jsx : ACCUEIL).
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function NouvelleEcoleForm({ onCreee, onAnnuler }) {
  const [champs, setChamps] = useState({
    nom: '',
    codePostal: '',
    adminPrenom: '',
    adminNom: '',
    adminEmail: '',
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const complet = Object.values(champs).every((v) => v.trim()) && EMAIL.test(champs.adminEmail.trim())

  function changer(cle) {
    return (e) => setChamps((c) => ({ ...c, [cle]: e.target.value }))
  }

  async function creer(e) {
    e.preventDefault()
    if (!complet || enCours) return
    setErreur('')
    setEnCours(true)
    const c = Object.fromEntries(Object.entries(champs).map(([k, v]) => [k, v.trim()]))
    let ecole
    try {
      ecole = await auth.creerEcole({ nom: c.nom, codePostal: c.codePostal })
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
      return
    }
    // Le premier administrateur, puis son invitation. Si l'un des deux
    // échoue, l'école existe déjà : le mot d'accueil dit quoi refaire
    // (Admin › École, menu ⋮ › Ajouter un administrateur, ou Inviter).
    let accueil
    try {
      const admin = await administrateurs.creer(ecole.id, { nom: c.adminNom, prenom: c.adminPrenom, email: c.adminEmail, owner: true })
      try {
        await auth.inviter(ecole.id, [admin.id])
        accueil = { admin: `${c.adminPrenom} ${c.adminNom}`, email: c.adminEmail, invite: true }
      } catch (err) {
        accueil = { admin: `${c.adminPrenom} ${c.adminNom}`, email: c.adminEmail, invite: false, erreur: err.message }
      }
    } catch (err) {
      accueil = { admin: null, erreur: err.message }
    }
    sessionApi.sauvegarderEcran('accueil-ecole', JSON.stringify({ ecoleId: ecole.id, ...accueil }))
    sessionApi.sauvegarderEcran('admin', 'ecole')
    setEnCours(false)
    onCreee(ecole)
  }

  return (
    <form className="login-screen__form" onSubmit={creer}>
      <label htmlFor="nouvelle-ecole-nom">Nom de l’école</label>
      <input id="nouvelle-ecole-nom" value={champs.nom} onChange={changer('nom')} />
      <label htmlFor="nouvelle-ecole-cp">Code postal</label>
      <input id="nouvelle-ecole-cp" value={champs.codePostal} onChange={changer('codePostal')} />
      <p className="nouvelle-ecole__titre">Premier administrateur (administrateur principal)</p>
      <label htmlFor="nouvelle-ecole-admin-prenom">Prénom</label>
      <input id="nouvelle-ecole-admin-prenom" value={champs.adminPrenom} onChange={changer('adminPrenom')} />
      <label htmlFor="nouvelle-ecole-admin-nom">Nom</label>
      <input id="nouvelle-ecole-admin-nom" value={champs.adminNom} onChange={changer('adminNom')} />
      <label htmlFor="nouvelle-ecole-admin-email">Email</label>
      <input id="nouvelle-ecole-admin-email" type="email" inputMode="email" autoComplete="off" value={champs.adminEmail} onChange={changer('adminEmail')} />
      <p className="muted">Il recevra une invitation par email pour créer son mot de passe.</p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <button type="submit" className="btn btn--primary btn--block" disabled={!complet || enCours}>
        {enCours ? 'Création…' : 'Créer l’école'}
      </button>
      <button type="button" className="btn btn--link" onClick={onAnnuler}>
        Annuler
      </button>
    </form>
  )
}
