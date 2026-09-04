import { useState } from 'react'
import Logo from '../components/Logo.jsx'
import { currentUser } from '../data/mockData.js'

// Écran de connexion (voir spec/SPEC.md section 2 et images/login.png).
// Maquette : les champs sont pré-remplis avec l'exemple admin, tout
// "Se connecter" mène à la maquette (pas de vraie vérification ici).
export default function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState(currentUser.email)
  const [code, setCode] = useState('ADMIN2026')

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={110} />
        <h1>Contretemps</h1>
        <p>École de danse au Beausset</p>
      </div>

      <form
        className="login-screen__form"
        onSubmit={(e) => {
          e.preventDefault()
          onLogin()
        }}
      >
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="s.dubois@mail.com"
        />

        <label htmlFor="login-code">Code</label>
        <input
          id="login-code"
          type="password"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <p className="login-screen__hint">
          Ce code détermine votre rôle (parent, professeur, admin)
        </p>

        <button type="submit" className="btn btn--primary btn--block">
          Se connecter
        </button>
        <button type="button" className="btn btn--link">
          Code oublié ?
        </button>
      </form>
    </div>
  )
}
