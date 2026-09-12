import { urlDossierPdf, urlFacturePdf } from './api/backend.js'
import { LIBELLE_PALIER, moisEncaissementsAVenir } from './tarifs.js'

const LIBELLE_MOYEN_PAIEMENT = { cheque: 'Chèque', helloasso: 'Carte bancaire' }

// Écran final (étape 3, voir spec/SPEC-inscription.md) : affiché
// uniquement une fois le paiement réellement acquis — chèque confirmé
// (PaiementEtape.jsx) ou paiement HelloAsso vérifié "payé" (App.jsx, au
// retour). Un échec HelloAsso ne passe jamais par ici : App.jsx renvoie
// alors à PaiementEtape (étape 2), jamais à cet écran.
export default function Confirmation({ resultat, onNouvelleInscription }) {
  const montantTroisTrimestres = resultat.montant_trimestriel * 3
  const totalAnnee = resultat.montant_adhesion + montantTroisTrimestres
  // Le serveur ne renvoie que le montant DÉJÀ réduit (montant_trimestriel,
  // voir inscriptions.py) — reconstruit le prix brut du palier pour
  // l'affichage (voir tarifs.js:montantTrimestrielBrut, même logique
  // côté formulaire), sans jamais changer le montant réellement dû
  // ci-dessus.
  const montantTrimestrielBrut =
    resultat.montant_trimestriel + (resultat.reduction_famille_appliquee ? 5 : 0)

  return (
    <div className="section">
      <h2>Inscription enregistrée ✅</h2>
      <p>
        Merci ! L'inscription de <strong>{resultat.eleve_prenom} {resultat.eleve_nom}</strong> pour
        la saison <strong>{resultat.saison}</strong> a bien été prise en compte.
      </p>
      <p>Cours choisis : {resultat.cours_choisis.join(', ')}</p>

      {resultat.photoChoisie && !resultat.photoEnvoyee && (
        <p className="erreur-globale">
          La photo n'a pas pu être envoyée — l'inscription est bien enregistrée sans elle, vous
          pourrez la donner à l'école autrement.
        </p>
      )}

      {resultat.doublon_possible && (
        <p className="erreur-globale">
          Une inscription très similaire existe déjà pour cette saison — l'école vérifiera avec
          vous s'il ne s'agit pas d'un doublon.
        </p>
      )}

      <div className="tarif-apercu" style={{ marginBottom: 16 }}>
        <div className="tarif-apercu__ligne">
          <span>Adhésion</span>
          <span>{resultat.montant_adhesion} €</span>
        </div>
        <div className="tarif-apercu__ligne">
          <span>
            3 trimestres à {resultat.nb_cours_semaine} cours/semaine (palier «{' '}
            {LIBELLE_PALIER[resultat.palier_tarifaire] ?? resultat.palier_tarifaire} »{' '}
            {montantTrimestrielBrut} €
            {resultat.reduction_famille_appliquee && ' — famille : -5 €'})
          </span>
          <span>{montantTroisTrimestres} €</span>
        </div>
        <div className="tarif-apercu__ligne tarif-apercu__ligne--total">
          <span>Total année</span>
          <span className="montant">{totalAnnee} €</span>
        </div>
        {resultat.alerte_palier_mixte && (
          <div className="alerte">
            Cours choisis touchant plusieurs paliers tarifaires — palier le plus élevé retenu.
          </div>
        )}
      </div>

      <p>
        Moyen de paiement choisi :{' '}
        <strong>{LIBELLE_MOYEN_PAIEMENT[resultat.moyen_paiement] ?? resultat.moyen_paiement}</strong>
        {resultat.moyen_paiement === 'cheque' && (
          <>
            {' '}: un chèque de {resultat.montant_adhesion} € à l'ordre de Contretemps à remettre à
            l'école, puis le solde de {montantTroisTrimestres} €{' '}
            {resultat.paiement_nb_echeances === 3 ? (
              <>
                en 3 chèques de {resultat.montant_trimestriel} € chacun, encaissés en{' '}
                {moisEncaissementsAVenir(resultat.saison).join(', ') || 'ce mois-ci'}
              </>
            ) : (
              "en 1 chèque, remis avec celui de l'adhésion"
            )}
          </>
        )}
        {resultat.moyen_paiement === 'helloasso' && ' : paiement confirmé, merci !'}
        .
      </p>

      <a className="lien-pdf" href={urlDossierPdf(resultat.token_public)} target="_blank" rel="noreferrer">
        📄 Télécharger le dossier rempli (PDF)
      </a>
      <a className="lien-pdf" href={urlFacturePdf(resultat.token_public)} target="_blank" rel="noreferrer">
        🧾 Télécharger la facture (PDF)
      </a>

      <p>
        {!resultat.eleve_email ? (
          <>
            Vous n'avez pas indiqué d'email : aucune confirmation n'a été envoyée. Conservez cette
            page ou téléchargez les PDF ci-dessus.
          </>
        ) : resultat.email_envoye ? (
          <>
            Un email récapitulatif (avec ces 2 PDF en pièces jointes) a été envoyé à{' '}
            <strong>{resultat.eleve_email}</strong>.
          </>
        ) : (
          <>
            L'email de confirmation n'a pas pu être envoyé à <strong>{resultat.eleve_email}</strong>.
            Conservez cette page ou téléchargez les PDF ci-dessus.
          </>
        )}
      </p>

      <button className="bouton bouton--secondaire" type="button" onClick={onNouvelleInscription}>
        Inscrire un autre élève
      </button>
    </div>
  )
}
