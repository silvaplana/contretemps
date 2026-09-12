import { useState } from 'react'
import { choisirPaiement, initierPaiementHelloAsso } from './api/backend.js'
import { LIBELLE_PALIER, moisEncaissementsAVenir } from './tarifs.js'

// Étape 2 du flux (voir spec/SPEC-inscription.md) : les informations de
// l'élève sont déjà validées et enregistrées (étape 1, voir
// FormulaireInscription.jsx) — reste à choisir le moyen de paiement.
// Chèque : confirme tout de suite (rien à payer en ligne), passe direct
// à l'écran de confirmation. HelloAsso : redirige vers HelloAsso ; en
// cas d'échec au retour, App.jsx réaffiche CET écran (retour à l'étape
// 2), jamais l'écran de confirmation.
export default function PaiementEtape({ inscription, messageEchec, onPaiementParCheque, onRetourFormulaire }) {
  const [moyen, setMoyen] = useState(inscription.moyen_paiement === 'helloasso' ? 'helloasso' : 'cheque')
  const [nbEcheances, setNbEcheances] = useState(inscription.paiement_nb_echeances === 3 ? 3 : 1)
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  const montantTroisTrimestres = inscription.montant_trimestriel * 3
  const totalAnnee = inscription.montant_adhesion + montantTroisTrimestres
  // Le serveur ne renvoie que le montant DÉJÀ réduit — reconstruit le
  // prix brut du palier pour l'affichage (voir tarifs.js, même logique
  // côté formulaire), sans jamais changer le montant réellement dû.
  const montantTrimestrielBrut =
    inscription.montant_trimestriel + (inscription.reduction_famille_appliquee ? 5 : 0)

  async function valider() {
    setErreur(null)
    setEnCours(true)
    try {
      if (moyen === 'cheque') {
        const resultat = await choisirPaiement(inscription.token_public, 'cheque', nbEcheances)
        onPaiementParCheque(resultat)
        return
      }
      // Le token voyage dans l'URL de retour : la redirection HelloAsso
      // recharge entièrement la page (voir App.jsx qui la détecte).
      await choisirPaiement(inscription.token_public, 'helloasso', nbEcheances)
      const retourUrl =
        `${window.location.origin}${window.location.pathname}` +
        `?token=${inscription.token_public}&paiement=retour`
      const { redirect_url } = await initierPaiementHelloAsso(inscription.token_public, retourUrl)
      window.location.href = redirect_url
    } catch (err) {
      setErreur(
        err.message || 'Le paiement est momentanément indisponible. Réessayez, ou payez par chèque.'
      )
      setEnCours(false)
    }
  }

  return (
    <div className="section">
      <h2>Paiement</h2>

      {messageEchec && (
        <>
          <p className="erreur-globale">{messageEchec}</p>
          <button
            className="bouton bouton--secondaire"
            type="button"
            onClick={onRetourFormulaire}
            style={{ marginBottom: 16 }}
          >
            ◀ Revenir en arrière et modifier mes informations
          </button>
        </>
      )}

      <div className="tarif-apercu" style={{ marginBottom: 16 }}>
        <div className="tarif-apercu__ligne">
          <span>Adhésion</span>
          <span>{inscription.montant_adhesion} €</span>
        </div>
        <div className="tarif-apercu__ligne">
          <span>
            3 trimestres à {inscription.nb_cours_semaine} cours/semaine (palier «{' '}
            {LIBELLE_PALIER[inscription.palier_tarifaire] ?? inscription.palier_tarifaire} »{' '}
            {montantTrimestrielBrut} €
            {inscription.reduction_famille_appliquee && ' — famille : -5 €'})
          </span>
          <span>{montantTroisTrimestres} €</span>
        </div>
        <div className="tarif-apercu__ligne tarif-apercu__ligne--total">
          <span>Total année</span>
          <span className="montant">{totalAnnee} €</span>
        </div>
      </div>

      {erreur && (
        <>
          <p className="erreur-globale">{erreur}</p>
          <button
            className="bouton bouton--secondaire"
            type="button"
            onClick={onRetourFormulaire}
            style={{ marginBottom: 16 }}
          >
            ◀ Revenir en arrière et modifier mes informations
          </button>
        </>
      )}

      <div className="paiement-options">
        <label className="paiement-option">
          <input
            type="radio"
            name="paiement"
            checked={moyen === 'cheque'}
            onChange={() => setMoyen('cheque')}
          />
          Chèque
        </label>
        <label className="paiement-option">
          <input
            type="radio"
            name="paiement"
            checked={moyen === 'helloasso'}
            onChange={() => setMoyen('helloasso')}
          />
          Carte bancaire
        </label>
      </div>

      <div className="sous-cases" style={{ marginTop: 10 }}>
        <label>
          <input
            type="radio"
            name="nb-echeances"
            checked={nbEcheances === 1}
            onChange={() => setNbEcheances(1)}
          />
          En 1 fois
        </label>
        <label>
          <input
            type="radio"
            name="nb-echeances"
            checked={nbEcheances === 3}
            onChange={() => setNbEcheances(3)}
          />
          En 3 fois (1 {moyen === 'cheque' ? 'chèque' : 'fois'} par trimestre)
        </label>
        {moyen === 'cheque' && (
          <p className="champ__aide">
            Un chèque de {inscription.montant_adhesion} € à l'ordre de Contretemps à l'inscription,
            puis le solde de {montantTroisTrimestres} €{' '}
            {nbEcheances === 3 ? (
              <>
                en 3 chèques de {inscription.montant_trimestriel} € chacun, encaissés en{' '}
                {moisEncaissementsAVenir(inscription.saison).join(', ') || 'ce mois-ci'}.
              </>
            ) : (
              "en 1 chèque, remis avec celui de l'adhésion."
            )}
          </p>
        )}
        {moyen === 'helloasso' && nbEcheances === 3 && (
          <p className="champ__aide">
            {(() => {
              // Un trimestre déjà entamé au moment de l'inscription est
              // prélevé tout de suite avec l'adhésion (impossible de
              // programmer un prélèvement à une date déjà passée) — voir
              // backend/src/inscriptions/tarifs.py:calculer_echeances_helloasso,
              // même règle ici pour rester exact.
              const moisAVenir = moisEncaissementsAVenir(inscription.saison)
              const nbDejaDus = 3 - moisAVenir.length
              const montantImmediat =
                inscription.montant_adhesion + nbDejaDus * inscription.montant_trimestriel
              return (
                <>
                  {montantImmediat} € prélevés tout de suite (adhésion
                  {nbDejaDus > 0 ? ' + trimestre déjà entamé' : ''}), puis{' '}
                  {moisAVenir.length > 0 ? (
                    <>
                      le solde en {moisAVenir.length} prélèvement{moisAVenir.length > 1 ? 's' : ''} de{' '}
                      {inscription.montant_trimestriel} € chacun, au début de chaque trimestre :{' '}
                      {moisAVenir.join(', ')}.
                    </>
                  ) : (
                    'aucun autre prélèvement (les 3 trimestres sont déjà entamés).'
                  )}
                </>
              )
            })()}
          </p>
        )}
      </div>

      <button className="bouton" type="button" onClick={valider} disabled={enCours}>
        {enCours && <span className="spinner" aria-hidden="true" />}
        {enCours
          ? 'Un instant…'
          : moyen === 'cheque'
            ? 'Confirmer le paiement par chèque'
            : `Payer par carte bancaire en ${nbEcheances === 3 ? '3 fois' : '1 fois'}`}
      </button>
    </div>
  )
}
