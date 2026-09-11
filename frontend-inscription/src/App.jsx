import { useEffect, useState } from 'react'
import { listerCours, resoudreEcoleReelle, verifierPaiementHelloAsso } from './api/backend.js'
import Confirmation from './Confirmation.jsx'
import FormulaireInscription from './FormulaireInscription.jsx'
import { saisonActuelle } from './saison.js'

export default function App() {
  const [etat, setEtat] = useState({ statut: 'chargement' }) // chargement | verification-paiement | pret | erreur
  const [confirmation, setConfirmation] = useState(null)

  useEffect(() => {
    let annule = false
    async function charger() {
      // Retour d'un paiement HelloAsso (voir Confirmation.jsx :
      // window.location.href = redirectUrl) — la redirection recharge
      // entièrement la page, l'état React de la soumission initiale est
      // perdu. Le token voyage donc dans l'URL de retour.
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      if (token && params.get('paiement') === 'retour') {
        if (!annule) setEtat({ statut: 'verification-paiement' })
        try {
          // LE check qui fait foi (jamais confiance au simple retour
          // navigateur, voir spec/SPEC-inscription.md §4) : ré-interroge
          // HelloAsso côté serveur avant d'afficher quoi que ce soit.
          const resultat = await verifierPaiementHelloAsso(token)
          // Nettoie l'URL : un rechargement de page ne doit pas
          // re-déclencher cette vérification indéfiniment.
          window.history.replaceState({}, '', window.location.pathname)
          if (!annule) {
            setConfirmation(resultat)
            setEtat({ statut: 'pret', ecole: null, cours: [] })
          }
        } catch (erreur) {
          if (!annule) setEtat({ statut: 'erreur', message: erreur.message })
        }
        return
      }

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

  if (etat.statut === 'chargement' || etat.statut === 'verification-paiement') {
    return (
      <div className="page">
        <p className="chargement">
          {etat.statut === 'verification-paiement'
            ? 'Vérification du paiement en cours…'
            : 'Chargement du formulaire…'}
        </p>
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
