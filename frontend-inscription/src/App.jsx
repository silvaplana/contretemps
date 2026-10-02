import { useEffect, useState } from 'react'
import {
  listerCours,
  obtenirFiche,
  resoudreEcole,
  resoudreEcoleReelle,
  verifierPaiementHelloAsso,
} from './api/backend.js'
import Confirmation from './Confirmation.jsx'
import { formaterCout } from './cout.js'
import FormulaireInscription from './FormulaireInscription.jsx'
import PaiementEtape from './PaiementEtape.jsx'
import { saisonActuelle } from './saison.js'

// Fiche papier : le formulaire est affiché DANS l'appli principale (voir
// frontend/src/screens/admin/AjoutEleveOcr.jsx, dans un cadre). Quand la
// saisie se termine, on le lui dit ; elle ferme le cadre et revient à la
// saisie d'une nouvelle fiche. Renvoie false si la page est ouverte seule.
function prevenirAppli(message) {
  if (window.parent === window) return false
  window.parent.postMessage({ type: 'contretemps-fiche', ...message }, '*')
  return true
}

export default function App() {
  const [etat, setEtat] = useState({ statut: 'chargement' }) // chargement | verification-paiement | pret | erreur
  // Flux en 3 étapes (voir spec/SPEC-inscription.md) : 'formulaire'
  // (informations, sans paiement) -> 'paiement' (choix chèque/HelloAsso)
  // -> 'confirmation' (paiement acquis). Un échec HelloAsso ramène à
  // 'paiement', jamais à 'confirmation'.
  const [etape, setEtape] = useState('formulaire')
  const [inscription, setInscription] = useState(null)
  const [messageEchecPaiement, setMessageEchecPaiement] = useState(null)

  useEffect(() => {
    let annule = false
    async function charger() {
      // Retour d'un paiement HelloAsso (voir PaiementEtape.jsx :
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
            setInscription(resultat)
            if (resultat.statut_paiement === 'paye') {
              setEtape('confirmation')
            } else {
              // Échec (ou statut encore incertain) -> retour à l'étape
              // paiement, jamais à l'écran de confirmation.
              setMessageEchecPaiement(
                resultat.statut_paiement === 'echec'
                  ? 'Le paiement a échoué ou a été annulé. Choisissez à nouveau un moyen de paiement.'
                  : "Le paiement n'a pas pu être confirmé pour le moment. Choisissez à nouveau un moyen de paiement."
              )
              setEtape('paiement')
            }
            setEtat({ statut: 'pret', ecole: null, cours: [] })
          }
        } catch (erreur) {
          if (!annule) setEtat({ statut: 'erreur', message: erreur.message })
        }
        return
      }

      // Fiche papier lue automatiquement (appli principale : Admin >
      // Élèves > « Ajouter élève (OCR) ») : le formulaire s'ouvre
      // pré-rempli, pour un admin qui corrige puis valide.
      const jetonFiche = params.get('fiche')
      try {
        let fiche = null
        if (jetonFiche) {
          try {
            fiche = await obtenirFiche(jetonFiche)
          } catch {
            throw new Error('Cette fiche est introuvable ou a expiré : relancez la lecture depuis l’appli.')
          }
        }
        const ecole = fiche ? await resoudreEcole(fiche.ecoleId) : await resoudreEcoleReelle()
        const cours = await listerCours(ecole.id)
        if (!annule) setEtat({ statut: 'pret', ecole, cours, fiche })
      } catch (erreur) {
        if (!annule) setEtat({ statut: 'erreur', message: erreur.message })
      }
    }
    charger()
    return () => {
      annule = true
    }
  }, [])

  function recommencer() {
    setInscription(null)
    setMessageEchecPaiement(null)
    setEtape('formulaire')
  }

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

  // Fiche papier : l'élève est dans la liste officielle, pas de paiement.
  if (etat.statut === 'eleve-enregistre') {
    const { eleve } = etat
    return (
      <div className="page">
        <div className="section">
          <h2>Élève enregistré ✅</h2>
          <p>
            <strong>{eleve.eleve_prenom} {eleve.eleve_nom}</strong> est inscrit(e) pour la saison{' '}
            <strong>{eleve.saison}</strong> et figure dans la liste des élèves (Admin &gt; Élèves).
          </p>
          <p>
            {eleve.mail_envoye
              ? `Un mail avec le dossier rempli et les photos de la fiche a été envoyé à ${eleve.mail_adresse}.`
              : "Le mail avec le dossier rempli et les photos de la fiche n'a pas pu être envoyé."}
          </p>
          <p>
            Coût de la lecture : <strong>{formaterCout(eleve.cout_usd)}</strong>
          </p>
          <p className="chargement">Vous pouvez fermer cet onglet.</p>
        </div>
      </div>
    )
  }

  if (etat.statut === 'fiche-annulee') {
    return (
      <div className="page">
        <p className="chargement">
          Saisie annulée : la fiche et ses photos ont été effacées. Vous pouvez fermer cet onglet.
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
          Saison {saisonActuelle()} —{' '}
          {etat.fiche
            ? 'fiche papier lue automatiquement : vérifiez, corrigez, puis validez.'
            : 'remplissez ce formulaire pour inscrire votre élève.'}
        </p>
      </header>

      {etape === 'confirmation' && inscription ? (
        <Confirmation resultat={inscription} onNouvelleInscription={recommencer} />
      ) : etape === 'paiement' && inscription ? (
        <PaiementEtape
          inscription={inscription}
          messageEchec={messageEchecPaiement}
          onPaiementParCheque={(resultat) => {
            setInscription((precedente) => ({ ...precedente, ...resultat }))
            setEtape('confirmation')
          }}
          onRetourFormulaire={recommencer}
        />
      ) : (
        <FormulaireInscription
          ecole={etat.ecole}
          cours={etat.cours}
          fiche={etat.fiche}
          onAnnuler={() => {
            if (!prevenirAppli({ issue: 'annule' })) setEtat({ statut: 'fiche-annulee' })
          }}
          onEleveEnregistre={(eleve) => {
            window.history.replaceState({}, '', window.location.pathname)
            const dansAppli = prevenirAppli({
              issue: 'enregistre',
              prenom: eleve.eleve_prenom,
              nom: eleve.eleve_nom,
              saison: eleve.saison,
              mailEnvoye: eleve.mail_envoye,
            })
            // Dans l'appli, c'est elle qui reprend la main (retour à la
            // saisie d'une nouvelle fiche) : pas d'écran de fin ici.
            setEtat(dansAppli ? { statut: 'chargement' } : { statut: 'eleve-enregistre', eleve })
          }}
          onSoumis={(resultat) => {
            setInscription(resultat)
            setMessageEchecPaiement(null)
            setEtape('paiement')
          }}
        />
      )}
    </div>
  )
}
