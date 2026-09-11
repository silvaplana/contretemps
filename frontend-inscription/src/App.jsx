import { useEffect, useState } from 'react'
import { listerCours, resoudreEcoleReelle } from './api/backend.js'
import Confirmation from './Confirmation.jsx'
import FormulaireInscription from './FormulaireInscription.jsx'
import { saisonActuelle } from './saison.js'

export default function App() {
  const [etat, setEtat] = useState({ statut: 'chargement' }) // chargement | pret | erreur
  const [confirmation, setConfirmation] = useState(null)

  useEffect(() => {
    let annule = false
    async function charger() {
      try {
        const ecole = await resoudreEcoleReelle()
        const cours = await listerCours(ecole.id)
        if (!annule) setEtat({ statut: 'pret', ecole, cours })
      } catch (erreur) {
        if (!annule) setEtat({ statut: 'erreur', message: erreur.message })
      }
    }
    charger()
    return () => {
      annule = true
    }
  }, [])

  if (etat.statut === 'chargement') {
    return (
      <div className="page">
        <p className="chargement">Chargement du formulaire…</p>
      </div>
    )
  }

  if (etat.statut === 'erreur') {
    return (
      <div className="page">
        <p className="erreur-page">
          Impossible de charger le formulaire d'inscription pour le moment.
          <br />
          <small>{etat.message}</small>
        </p>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="entete">
        <h1>
          Inscription — École de danse <span className="entete__logo">Contretemps</span>
        </h1>
        <p>
          Saison {saisonActuelle()} — remplissez ce formulaire pour inscrire votre élève.
        </p>
      </header>

      {confirmation ? (
        <Confirmation resultat={confirmation} onNouvelleInscription={() => setConfirmation(null)} />
      ) : (
        <FormulaireInscription
          ecole={etat.ecole}
          cours={etat.cours}
          onSoumis={setConfirmation}
        />
      )}
    </div>
  )
}
