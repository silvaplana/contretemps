import { useEffect, useState } from 'react'
import Logo from '../components/Logo.jsx'
import Modal from '../components/Modal.jsx'
import { currentUser } from '../data/mockData.js'

// Écran de connexion (voir spec/SPEC.md §2.2 et §2.3).
// Maquette : identifiant = nom+prénom OU email, code d'accès par rôle et par
// école. Pas de vraie vérification ici, "Se connecter" mène toujours à la
// même maquette (mono-école pour l'instant, le multi-écoles est pour le
// backend, voir §2.1).
export default function LoginScreen({ onLogin }) {
  const [identifiant, setIdentifiant] = useState(`${currentUser.prenom} ${currentUser.nom}`)
  const [code, setCode] = useState('ADMIN2026')
  const [showNouvelleEcole, setShowNouvelleEcole] = useState(false)

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={110} />
        <h1>Contretemps</h1>
        <p>Gestion d'école de danse</p>
      </div>

      <form
        className="login-screen__form"
        onSubmit={(e) => {
          e.preventDefault()
          onLogin()
        }}
      >
        <label htmlFor="login-identifiant">Nom Prénom ou Email</label>
        <input
          id="login-identifiant"
          type="text"
          value={identifiant}
          onChange={(e) => setIdentifiant(e.target.value)}
          placeholder="Valérie Petit ou v.petit@contretemps.fr"
        />

        <label htmlFor="login-code">Code d’accès</label>
        <input
          id="login-code"
          type="password"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />

        <button type="submit" className="btn btn--primary btn--block">
          Se connecter
        </button>
        <button type="button" className="btn btn--link">
          Code oublié ?
        </button>
        <button
          type="button"
          className="btn btn--link"
          onClick={() => setShowNouvelleEcole(true)}
        >
          Nouvelle école ?
        </button>
      </form>

      {showNouvelleEcole && (
        <NouvelleEcoleModal
          onClose={() => setShowNouvelleEcole(false)}
          onCreated={(prenom, nom) => {
            setIdentifiant(`${prenom} ${nom}`)
            setShowNouvelleEcole(false)
          }}
        />
      )}
    </div>
  )
}

// Code par défaut proposé pour un rôle donné (voir spec §2.3 et §6.1) :
// ADMIN_ECOLE_ANNEE, avec ÉCOLE = nom de l'école en majuscules sans espaces.
function codeParDefaut(prefixe, nomEcole) {
  const slug = nomEcole.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '')
  const annee = new Date().getFullYear()
  return `${prefixe}_${slug || 'ECOLE'}_${annee}`
}

// Formulaire "Nouvelle école ?" (voir spec §2.3). Maquette : la création
// n'est pas persistée (pas de backend), on affiche juste le récapitulatif
// puis on repropose la connexion avec l'identité du premier admin saisi.
function NouvelleEcoleModal({ onClose, onCreated }) {
  const [nomEcole, setNomEcole] = useState('')
  const [codeAdmin, setCodeAdmin] = useState(codeParDefaut('ADMIN', ''))
  const [codeProf, setCodeProf] = useState(codeParDefaut('PROF', ''))
  const [codeEleve, setCodeEleve] = useState(codeParDefaut('ELEVE', ''))
  const [touched, setTouched] = useState({ admin: false, prof: false, eleve: false })
  const [adminNom, setAdminNom] = useState('')
  const [adminPrenom, setAdminPrenom] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [creee, setCreee] = useState(false)

  // Les 3 codes suivent le nom de l'école tant que l'utilisateur ne les a
  // pas modifiés à la main (ils restent "éditables avant validation").
  useEffect(() => {
    if (!touched.admin) setCodeAdmin(codeParDefaut('ADMIN', nomEcole))
    if (!touched.prof) setCodeProf(codeParDefaut('PROF', nomEcole))
    if (!touched.eleve) setCodeEleve(codeParDefaut('ELEVE', nomEcole))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nomEcole])

  const valide = nomEcole && adminNom && adminPrenom && adminEmail

  if (creee) {
    return (
      <Modal title="École créée" onClose={onClose}>
        <p>
          <strong>{nomEcole}</strong> est prête, avec {adminPrenom} {adminNom} comme premier
          administrateur.
        </p>
        <div className="checkbox-list">
          <div className="checkbox-list__item">Code Admin : {codeAdmin}</div>
          <div className="checkbox-list__item">Code Professeur : {codeProf}</div>
          <div className="checkbox-list__item">Code Élève : {codeEleve}</div>
        </div>
        <p className="muted">
          Ces codes sont modifiables ensuite par tout admin, depuis Admin → Paramètres école.
        </p>
        <button
          type="button"
          className="btn btn--primary btn--block"
          onClick={() => onCreated(adminPrenom, adminNom)}
        >
          Se connecter
        </button>
      </Modal>
    )
  }

  return (
    <Modal
      title="Nouvelle école"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!valide}
          onClick={() => setCreee(true)}
        >
          Créer l’école
        </button>
      }
    >
      <label htmlFor="ecole-nom">Nom de l’école</label>
      <input
        id="ecole-nom"
        value={nomEcole}
        onChange={(e) => setNomEcole(e.target.value)}
        placeholder="Ex. EcoleTest"
      />

      <label htmlFor="ecole-code-admin">Code d’accès Admin</label>
      <input
        id="ecole-code-admin"
        value={codeAdmin}
        onChange={(e) => {
          setCodeAdmin(e.target.value)
          setTouched((t) => ({ ...t, admin: true }))
        }}
      />

      <label htmlFor="ecole-code-prof">Code d’accès Professeur</label>
      <input
        id="ecole-code-prof"
        value={codeProf}
        onChange={(e) => {
          setCodeProf(e.target.value)
          setTouched((t) => ({ ...t, prof: true }))
        }}
      />

      <label htmlFor="ecole-code-eleve">Code d’accès Élève</label>
      <input
        id="ecole-code-eleve"
        value={codeEleve}
        onChange={(e) => {
          setCodeEleve(e.target.value)
          setTouched((t) => ({ ...t, eleve: true }))
        }}
      />

      <p className="section-label">Premier administrateur</p>
      <label htmlFor="ecole-admin-prenom">Prénom</label>
      <input
        id="ecole-admin-prenom"
        value={adminPrenom}
        onChange={(e) => setAdminPrenom(e.target.value)}
      />
      <label htmlFor="ecole-admin-nom">Nom</label>
      <input id="ecole-admin-nom" value={adminNom} onChange={(e) => setAdminNom(e.target.value)} />
      <label htmlFor="ecole-admin-email">Email</label>
      <input
        id="ecole-admin-email"
        type="email"
        value={adminEmail}
        onChange={(e) => setAdminEmail(e.target.value)}
      />
    </Modal>
  )
}
