import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import Logo from '../components/Logo.jsx'
import Modal from '../components/Modal.jsx'
import * as auth from '../api/auth.js'

// Écran de connexion (voir spec/SPEC.md §2.2 et §2.3) — toujours réel,
// via api/auth.js (le mode maquette a été retiré, voir spec/SPEC.md §8).
export default function LoginScreen({ onLogin }) {
  const [identifiant, setIdentifiant] = useState('')
  const [code, setCode] = useState('ADMIN')
  const [showNouvelleEcole, setShowNouvelleEcole] = useState(false)
  const [showCodeOublie, setShowCodeOublie] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [codeVisible, setCodeVisible] = useState(false)

  async function seConnecter(e) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const resultat = await auth.login({ identifiant, code })
      onLogin(resultat)
    } catch (err) {
      setErreur(err.message || 'Connexion impossible')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={110} />
        <h1>Contretemps</h1>
        <p>Gestion d'école de danse du cours au gala</p>
      </div>

      <form className="login-screen__form" onSubmit={seConnecter}>
        <label htmlFor="login-identifiant">Nom Prénom ou Email</label>
        <input
          id="login-identifiant"
          type="text"
          value={identifiant}
          onChange={(e) => setIdentifiant(e.target.value)}
          placeholder="Julia Dho ou jd@contretemps.fr"
        />

        <label htmlFor="login-code">Code d’accès</label>
        <div className="login-screen__champ-code">
          <input
            id="login-code"
            type={codeVisible ? 'text' : 'password'}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <button
            type="button"
            className="icon-btn login-screen__toggle-code"
            onClick={() => setCodeVisible((v) => !v)}
            aria-label={codeVisible ? 'Masquer le code' : 'Afficher le code'}
          >
            <Icon name={codeVisible ? 'eyeOff' : 'eye'} size={20} />
          </button>
        </div>

        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        <button type="submit" className="btn btn--primary btn--block" disabled={enCours}>
          Se connecter
        </button>
        <button type="button" className="btn btn--link" onClick={() => setShowCodeOublie(true)}>
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

      {showCodeOublie && (
        <CodeOublieModal
          identifiantInitial={identifiant}
          onClose={() => setShowCodeOublie(false)}
          onLogin={(resultat) => {
            setShowCodeOublie(false)
            onLogin(resultat)
          }}
        />
      )}
    </div>
  )
}

// Modale "Code oublié ?" (voir spec §2.2/§2.3) — l'identifiant n'est PAS
// redemandé : celui déjà tapé dans le champ "Nom Prénom ou Email" du
// formulaire de connexion (identifiantInitial) sert directement à
// résoudre le compte (voir auth.js: verifierRecuperation), dès
// l'ouverture de la modale (demande) :
// - admin -> directement la question de récupération ("Code de
//   récupération : nom de votre 1er animal de compagnie") ; bonne
//   réponse -> connecté direct (comme "Se connecter").
// - professeur/élève -> juste le contact de l'admin à qui demander
//   directement, pas de libre-service pour ces 2 rôles.
function CodeOublieModal({ identifiantInitial, onClose, onLogin }) {
  const [resultat, setResultat] = useState(null) // réponse de verifierRecuperation
  const [reponseQuestion, setReponseQuestion] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(true)

  useEffect(() => {
    auth
      .verifierRecuperation(identifiantInitial)
      .then(setResultat)
      .catch((err) => setErreur(err.message || 'Identifiant introuvable'))
      .finally(() => setEnCours(false))
  }, [identifiantInitial])

  async function repondre(e) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      onLogin(await auth.repondreRecuperation(identifiantInitial, reponseQuestion))
    } catch (err) {
      setErreur(err.message || 'Réponse incorrecte')
      setEnCours(false)
    }
  }

  // admin -> la question de récupération, directement.
  if (resultat?.role === 'admin') {
    return (
      <Modal title="Code oublié" onClose={onClose}>
        <form onSubmit={repondre}>
          <label htmlFor="recup-reponse">Code de récupération : nom de votre 1er animal de compagnie</label>
          <input
            id="recup-reponse"
            value={reponseQuestion}
            onChange={(e) => setReponseQuestion(e.target.value)}
            autoFocus
          />
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
          <button type="submit" className="btn btn--primary btn--block" disabled={enCours || !reponseQuestion}>
            Valider
          </button>
        </form>
      </Modal>
    )
  }

  // professeur/élève -> pas de libre-service, juste le contact.
  if (resultat) {
    return (
      <Modal title="Code oublié" onClose={onClose}>
        <p>
          Contactez l’administrateur <strong>{resultat.admin_prenom} {resultat.admin_nom}</strong> de
          l’école <strong>{resultat.ecole_nom}</strong>
          {resultat.admin_email ? <> par mail (<strong>{resultat.admin_email}</strong>)</> : null} pour
          qu’il vous indique votre code.
        </p>
        <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
          Fermer
        </button>
      </Modal>
    )
  }

  // Identifiant introuvable (ou vérification encore en cours).
  return (
    <Modal title="Code oublié" onClose={onClose}>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {enCours && !erreur && <p className="muted">Vérification…</p>}
    </Modal>
  )
}

// Code par défaut proposé pour un rôle donné (voir spec §2.3 et §6.1) :
// ADMIN_ECOLE_ANNEE, avec ÉCOLE = nom de l'école en majuscules sans espaces.
function codeParDefaut(prefixe, nomEcole) {
  const slug = nomEcole.trim().toUpperCase().replace(/[^A-Z0-9]+/g, '')
  const annee = new Date().getFullYear()
  return `${prefixe}_${slug || 'ECOLE'}_${annee}`
}

// Utilisée uniquement pour l'exemple en placeholder des 3 champs de code
// (tant que "Nom de l'école" est vide, voir NouvelleEcoleModal) — l'année
// suit toujours la vraie date, jamais "2026" en dur.
const ANNEE_EXEMPLE = new Date().getFullYear()

// Formulaire "Nouvelle école ?" (voir spec §2.3). ⚠️ Pas encore branché
// au backend (pas de POST /ecoles ici) : affiche juste le récapitulatif
// puis repropose la connexion avec l'identité du premier admin saisi —
// à corriger avant une vraie mise en prod multi-écoles (voir spec §8).
function NouvelleEcoleModal({ onClose, onCreated }) {
  const [nomEcole, setNomEcole] = useState('')
  const [codePostal, setCodePostal] = useState('')
  const [codeAdmin, setCodeAdmin] = useState('')
  const [codeProf, setCodeProf] = useState('')
  const [codeEleve, setCodeEleve] = useState('')
  const [touched, setTouched] = useState({ admin: false, prof: false, eleve: false })
  const [adminNom, setAdminNom] = useState('')
  const [adminPrenom, setAdminPrenom] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminTelephone, setAdminTelephone] = useState('')
  const [adminCodeRecuperation, setAdminCodeRecuperation] = useState('')
  const [creee, setCreee] = useState(false)

  // Les 3 codes suivent le nom de l'école tant que l'utilisateur ne les a
  // pas modifiés à la main (ils restent "éditables avant validation").
  // Tant que le nom de l'école n'est pas encore saisi, les champs restent
  // vides (avec un exemple en placeholder, voir plus bas) plutôt que de
  // proposer un "ADMIN_ECOLE_2026" générique qui ne correspond à rien.
  useEffect(() => {
    if (!touched.admin) setCodeAdmin(nomEcole ? codeParDefaut('ADMIN', nomEcole) : '')
    if (!touched.prof) setCodeProf(nomEcole ? codeParDefaut('PROF', nomEcole) : '')
    if (!touched.eleve) setCodeEleve(nomEcole ? codeParDefaut('ELEVE', nomEcole) : '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nomEcole])

  const valide =
    nomEcole && codePostal && adminNom && adminPrenom && adminEmail && adminTelephone && adminCodeRecuperation

  if (creee) {
    return (
      <Modal title="École créée" onClose={onClose}>
        <p>
          <strong>
            {nomEcole} ({codePostal})
          </strong>{' '}
          est prête, avec {adminPrenom} {adminNom} comme premier administrateur.
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

      <label htmlFor="ecole-cp">Code postal</label>
      {/* Sert à distinguer 2 écoles qui porteraient le même nom (voir spec
          §6.1) : le couple nom + code postal doit être unique, pas le nom
          seul — donc obligatoire dès la création. */}
      <input
        id="ecole-cp"
        value={codePostal}
        onChange={(e) => setCodePostal(e.target.value)}
        placeholder="Ex. 83330"
      />

      <label htmlFor="ecole-code-admin">Code d’accès Admin</label>
      <input
        id="ecole-code-admin"
        value={codeAdmin}
        onChange={(e) => {
          setCodeAdmin(e.target.value)
          setTouched((t) => ({ ...t, admin: true }))
        }}
        placeholder={`Ex. ADMIN_ECOLE_TEST_${ANNEE_EXEMPLE}`}
      />

      <label htmlFor="ecole-code-prof">Code d’accès Professeur</label>
      <input
        id="ecole-code-prof"
        value={codeProf}
        onChange={(e) => {
          setCodeProf(e.target.value)
          setTouched((t) => ({ ...t, prof: true }))
        }}
        placeholder={`Ex. PROF_ECOLE_TEST_${ANNEE_EXEMPLE}`}
      />

      <label htmlFor="ecole-code-eleve">Code d’accès Élève</label>
      <input
        id="ecole-code-eleve"
        value={codeEleve}
        onChange={(e) => {
          setCodeEleve(e.target.value)
          setTouched((t) => ({ ...t, eleve: true }))
        }}
        placeholder={`Ex. ELEVE_ECOLE_TEST_${ANNEE_EXEMPLE}`}
      />

      <p className="section-label">Premier administrateur</p>
      <label htmlFor="ecole-admin-prenom">Prénom</label>
      <input
        id="ecole-admin-prenom"
        value={adminPrenom}
        onChange={(e) => setAdminPrenom(e.target.value)}
        placeholder="Ex. Claire"
      />
      <label htmlFor="ecole-admin-nom">Nom</label>
      <input
        id="ecole-admin-nom"
        value={adminNom}
        onChange={(e) => setAdminNom(e.target.value)}
        placeholder="Ex. Martin"
      />
      <label htmlFor="ecole-admin-email">Email</label>
      <input
        id="ecole-admin-email"
        type="email"
        value={adminEmail}
        onChange={(e) => setAdminEmail(e.target.value)}
        placeholder="Ex. claire.martin@ecole-test.fr"
      />
      <label htmlFor="ecole-admin-telephone">Téléphone</label>
      <input
        id="ecole-admin-telephone"
        type="tel"
        value={adminTelephone}
        onChange={(e) => setAdminTelephone(e.target.value)}
        placeholder="Ex. 06 00 00 00 00"
      />

      {/* Voir "Code oublié ?" à l'écran de connexion : demandé à la
          création d'un admin, comme une question de sécurité classique. */}
      <label htmlFor="ecole-admin-code-recuperation">
        Code de récupération : nom de votre 1er animal de compagnie
      </label>
      <input
        id="ecole-admin-code-recuperation"
        value={adminCodeRecuperation}
        onChange={(e) => setAdminCodeRecuperation(e.target.value)}
        placeholder="Ex. Rex"
      />
    </Modal>
  )
}
