import { useMemo, useState } from 'react'
import { creerInscription, uploaderPhotoEleve } from './api/backend.js'
import { saisonActuelle } from './saison.js'
import { calculerTarifIndicatif, LIBELLE_PALIER, moisEncaissementsAVenir } from './tarifs.js'

const VIDE = {
  eleveNom: '',
  elevePrenom: '',
  eleveDateNaissance: '',
  eleveAdresse: '',
  eleveTelephone: '',
  eleveEmail: '',
  contactNom: '',
  contactPrenom: '',
  contactLien: '',
  contactTelephone: '',
  coursIds: [],
  allergies: '',
  traitementMedical: '',
  informationsImportantes: '',
  droitImageAutorise: false,
  droitImageSite: false,
  droitImageReseaux: false,
  droitImageAffiches: false,
  reglementLuApprouve: false,
  signataireNom: '',
  moyenPaiement: 'cheque',
  paiementNbEcheances: 1,
  reductionFamilleDemandee: false,
}

export default function FormulaireInscription({ ecole, cours, onSoumis }) {
  const [valeurs, setValeurs] = useState(VIDE)
  const [elevePhoto, setElevePhoto] = useState(null)
  const [apercuPhoto, setApercuPhoto] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)

  function choisirPhoto(e) {
    const fichier = e.target.files?.[0] ?? null
    setElevePhoto(fichier)
    setApercuPhoto((ancien) => {
      if (ancien) URL.revokeObjectURL(ancien)
      return fichier ? URL.createObjectURL(fichier) : null
    })
  }

  const nomsCoursChoisis = useMemo(
    () => cours.filter((c) => valeurs.coursIds.includes(c.id)).map((c) => c.nom),
    [cours, valeurs.coursIds]
  )
  const tarif = useMemo(
    () => calculerTarifIndicatif(nomsCoursChoisis, valeurs.reductionFamilleDemandee),
    [nomsCoursChoisis, valeurs.reductionFamilleDemandee]
  )

  function champ(nom) {
    return {
      value: valeurs[nom],
      onChange: (e) => setValeurs((v) => ({ ...v, [nom]: e.target.value })),
    }
  }

  function basculerCoche(nom) {
    setValeurs((v) => ({ ...v, [nom]: !v[nom] }))
  }

  function basculerCours(id) {
    setValeurs((v) => ({
      ...v,
      coursIds: v.coursIds.includes(id)
        ? v.coursIds.filter((c) => c !== id)
        : [...v.coursIds, id],
    }))
  }

  function validite() {
    if (!valeurs.eleveNom.trim() || !valeurs.elevePrenom.trim()) {
      return "Le nom et le prénom de l'élève sont obligatoires."
    }
    if (!valeurs.eleveDateNaissance) {
      return 'La date de naissance est obligatoire.'
    }
    if (!valeurs.eleveEmail.trim()) {
      return "L'email est obligatoire (il sert à recevoir la confirmation et, si choisi, à payer avec HelloAsso)."
    }
    if (valeurs.coursIds.length === 0) {
      return 'Choisissez au moins un cours.'
    }
    if (!valeurs.reglementLuApprouve) {
      return "Vous devez approuver le règlement intérieur pour valider l'inscription."
    }
    if (!valeurs.signataireNom.trim()) {
      return 'Le nom du signataire est obligatoire.'
    }
    return null
  }

  async function soumettre(e) {
    e.preventDefault()
    const message = validite()
    if (message) {
      setErreur(message)
      return
    }
    setErreur(null)
    setEnvoiEnCours(true)
    try {
      const resultat = await creerInscription(ecole.id, {
        eleve_nom: valeurs.eleveNom.trim(),
        eleve_prenom: valeurs.elevePrenom.trim(),
        eleve_date_naissance: valeurs.eleveDateNaissance,
        eleve_adresse: valeurs.eleveAdresse || null,
        eleve_telephone: valeurs.eleveTelephone || null,
        eleve_email: valeurs.eleveEmail || null,
        cours_ids: valeurs.coursIds,
        allergies: valeurs.allergies || null,
        traitement_medical: valeurs.traitementMedical || null,
        informations_importantes: valeurs.informationsImportantes || null,
        contact_urgence_nom: valeurs.contactNom || null,
        contact_urgence_prenom: valeurs.contactPrenom || null,
        contact_urgence_lien: valeurs.contactLien || null,
        contact_urgence_telephone: valeurs.contactTelephone || null,
        droit_image_autorise: valeurs.droitImageAutorise,
        droit_image_site: valeurs.droitImageAutorise && valeurs.droitImageSite,
        droit_image_reseaux: valeurs.droitImageAutorise && valeurs.droitImageReseaux,
        droit_image_affiches: valeurs.droitImageAutorise && valeurs.droitImageAffiches,
        reglement_lu_approuve: valeurs.reglementLuApprouve,
        signataire_nom: valeurs.signataireNom.trim(),
        moyen_paiement: valeurs.moyenPaiement,
        paiement_nb_echeances: valeurs.paiementNbEcheances,
        reduction_famille_demandee: valeurs.reductionFamilleDemandee,
      })

      let photoEnvoyee = false
      if (elevePhoto) {
        try {
          await uploaderPhotoEleve(resultat.token_public, elevePhoto)
          photoEnvoyee = true
        } catch {
          // Jamais bloquant : l'inscription est déjà enregistrée (voir
          // api/backend.js) — juste signalé sur l'écran de confirmation.
        }
      }
      onSoumis({ ...resultat, photoEnvoyee, photoChoisie: Boolean(elevePhoto) })
    } catch (err) {
      setErreur(err.message || "L'inscription n'a pas pu être envoyée. Réessayez.")
    } finally {
      setEnvoiEnCours(false)
    }
  }

  return (
    <form onSubmit={soumettre}>
      {erreur && <p className="erreur-globale">{erreur}</p>}

      <section className="section">
        <h2>Élève</h2>
        <div className="grille-2">
          <div className="champ">
            <label htmlFor="eleve-nom">Nom *</label>
            <input id="eleve-nom" required placeholder="Dupont" {...champ('eleveNom')} />
          </div>
          <div className="champ">
            <label htmlFor="eleve-prenom">Prénom *</label>
            <input id="eleve-prenom" required placeholder="Julie" {...champ('elevePrenom')} />
          </div>
        </div>
        <div className="champ">
          <label htmlFor="eleve-naissance">Date de naissance *</label>
          <input id="eleve-naissance" type="date" required {...champ('eleveDateNaissance')} />
          {/* Un input date n'affiche jamais son "placeholder" (ignoré par
              tous les navigateurs) — texte d'aide séparé, jamais une
              vraie valeur, donc aucun risque de fausse date oubliée. */}
          <small className="champ__aide">Exemple : 10/05/2015</small>
        </div>
        <div className="champ">
          <label htmlFor="eleve-adresse">Adresse</label>
          <input
            id="eleve-adresse"
            placeholder="12 rue des Oliviers, 83330 Le Beausset"
            {...champ('eleveAdresse')}
          />
        </div>
        <div className="grille-2">
          <div className="champ">
            <label htmlFor="eleve-telephone">Téléphone</label>
            <input
              id="eleve-telephone"
              type="tel"
              placeholder="06 12 34 56 78"
              {...champ('eleveTelephone')}
            />
          </div>
          <div className="champ">
            <label htmlFor="eleve-email">Email *</label>
            <input
              id="eleve-email"
              type="email"
              required
              placeholder="julie.dupont@email.fr"
              {...champ('eleveEmail')}
            />
          </div>
        </div>
        <div className="champ">
          <label htmlFor="eleve-photo">Photo de l'élève</label>
          <input id="eleve-photo" type="file" accept="image/*" onChange={choisirPhoto} />
          {apercuPhoto && (
            <img src={apercuPhoto} alt="Aperçu de la photo de l'élève" className="photo-apercu" />
          )}
        </div>
      </section>

      <section className="section">
        <h2>Contact d'urgence</h2>
        <div className="grille-2">
          <div className="champ">
            <label htmlFor="contact-nom">Nom</label>
            <input id="contact-nom" placeholder="Dupont" {...champ('contactNom')} />
          </div>
          <div className="champ">
            <label htmlFor="contact-prenom">Prénom</label>
            <input id="contact-prenom" placeholder="Marie" {...champ('contactPrenom')} />
          </div>
        </div>
        <div className="grille-2">
          <div className="champ">
            <label htmlFor="contact-lien">Lien avec l'élève</label>
            <input id="contact-lien" placeholder="Père, mère, tuteur…" {...champ('contactLien')} />
          </div>
          <div className="champ">
            <label htmlFor="contact-telephone">Téléphone</label>
            <input
              id="contact-telephone"
              type="tel"
              placeholder="06 98 76 54 32"
              {...champ('contactTelephone')}
            />
          </div>
        </div>
      </section>

      <section className="section">
        <h2>Cours souhaités *</h2>
        <p className="compteur-cours">
          {valeurs.coursIds.length === 0
            ? 'Aucun cours sélectionné'
            : `${valeurs.coursIds.length} cours par semaine sélectionné${valeurs.coursIds.length > 1 ? 's' : ''}`}
          {' '}— le tarif dépend de ce nombre (voir ci-dessous).
        </p>
        <div className="cours-grille">
          {cours.map((c) => (
            <label
              key={c.id}
              className={`case ${valeurs.coursIds.includes(c.id) ? 'case--coche' : ''}`}
            >
              <input
                type="checkbox"
                checked={valeurs.coursIds.includes(c.id)}
                onChange={() => basculerCours(c.id)}
              />
              <span>
                {c.nom}
                {c.jour && (
                  <>
                    <br />
                    <small>
                      {c.jour} {c.heure_debut}-{c.heure_fin}
                    </small>
                  </>
                )}
              </span>
            </label>
          ))}
        </div>
      </section>

      {tarif && (
        <section className="section">
          <h2>Tarif indicatif</h2>
          <div className="tarif-apercu">
            <div>Cours choisis ({nomsCoursChoisis.length}) : {nomsCoursChoisis.join(', ')}</div>

            <label className="checkbox-ligne" style={{ margin: '8px 0' }}>
              <input
                type="checkbox"
                checked={valeurs.reductionFamilleDemandee}
                onChange={() => basculerCoche('reductionFamilleDemandee')}
              />
              <span>
                Réduction famille (-5 €/trimestre) : adhésion dégressive dès deux membres d'une
                même famille.
              </span>
            </label>

            <div className="tarif-apercu__ligne">
              <span>Adhésion</span>
              <span>{tarif.montantAdhesion} €</span>
            </div>
            <div className="tarif-apercu__ligne">
              <span>
                3 trimestres à {valeurs.coursIds.length} cours/semaine (palier «{' '}
                {LIBELLE_PALIER[tarif.palier]} » {tarif.montantTrimestrielBrut} €
                {tarif.reductionFamilleAppliquee && ' — famille : -5 €'})
              </span>
              <span>{tarif.montantTroisTrimestres} €</span>
            </div>
            <div className="tarif-apercu__ligne tarif-apercu__ligne--total">
              <span>Total année</span>
              <span className="montant">{tarif.totalAnnee} €</span>
            </div>

            {tarif.alertePalierMixte && (
              <div className="alerte">
                Les cours choisis touchent plusieurs paliers tarifaires — palier le plus élevé
                retenu.
              </div>
            )}
          </div>
        </section>
      )}

      <section className="section">
        <h2>Informations médicales</h2>
        <div className="champ">
          <label htmlFor="allergies">Allergies</label>
          <textarea id="allergies" rows={2} placeholder="Aucune" {...champ('allergies')} />
        </div>
        <div className="champ">
          <label htmlFor="traitement">Traitement médical</label>
          <textarea id="traitement" rows={2} placeholder="Aucun" {...champ('traitementMedical')} />
        </div>
        <div className="champ">
          <label htmlFor="infos-importantes">Autres informations importantes</label>
          <textarea
            id="infos-importantes"
            rows={2}
            placeholder="Ex. porte des lunettes"
            {...champ('informationsImportantes')}
          />
        </div>
      </section>

      <section className="section">
        <h2>Droit à l'image</h2>
        <label className="checkbox-ligne">
          <input
            type="checkbox"
            checked={valeurs.droitImageAutorise}
            onChange={() => basculerCoche('droitImageAutorise')}
          />
          <span>J'autorise l'école à utiliser l'image de l'élève.</span>
        </label>
        {valeurs.droitImageAutorise && (
          <div className="sous-cases">
            <label>
              <input
                type="checkbox"
                checked={valeurs.droitImageSite}
                onChange={() => basculerCoche('droitImageSite')}
              />
              Site internet
            </label>
            <label>
              <input
                type="checkbox"
                checked={valeurs.droitImageReseaux}
                onChange={() => basculerCoche('droitImageReseaux')}
              />
              Réseaux sociaux
            </label>
            <label>
              <input
                type="checkbox"
                checked={valeurs.droitImageAffiches}
                onChange={() => basculerCoche('droitImageAffiches')}
              />
              Affiches
            </label>
          </div>
        )}
      </section>

      <section className="section">
        <h2>Règlement intérieur *</h2>
        <label className="checkbox-ligne">
          <input
            type="checkbox"
            required
            checked={valeurs.reglementLuApprouve}
            onChange={() => basculerCoche('reglementLuApprouve')}
          />
          <span>J'ai lu et j'approuve le règlement intérieur de l'école.</span>
        </label>
        <div className="champ" style={{ marginTop: 10 }}>
          <label htmlFor="signataire">Nom du signataire (responsable légal, ou l'élève si majeur) *</label>
          <input id="signataire" required placeholder="Marie Dupont" {...champ('signataireNom')} />
        </div>
      </section>

      <section className="section">
        <h2>Paiement</h2>
        <div className="paiement-options">
          <label className="paiement-option">
            <input
              type="radio"
              name="paiement"
              value="cheque"
              checked={valeurs.moyenPaiement === 'cheque'}
              onChange={() => setValeurs((v) => ({ ...v, moyenPaiement: 'cheque' }))}
            />
            Chèque
          </label>
          <label className="paiement-option">
            <input
              type="radio"
              name="paiement"
              value="helloasso"
              checked={valeurs.moyenPaiement === 'helloasso'}
              onChange={() => setValeurs((v) => ({ ...v, moyenPaiement: 'helloasso' }))}
            />
            HelloAsso (carte bancaire)
          </label>
          <label className="paiement-option paiement-option--desactive">
            <input type="radio" name="paiement" disabled />
            Carte bancaire (Stripe)
            <span className="badge-bientot">Bientôt disponible</span>
          </label>
        </div>

        {valeurs.moyenPaiement === 'cheque' && (
          <div className="sous-cases" style={{ marginTop: 10 }}>
            <label>
              <input
                type="radio"
                name="nb-echeances"
                checked={valeurs.paiementNbEcheances === 1}
                onChange={() => setValeurs((v) => ({ ...v, paiementNbEcheances: 1 }))}
              />
              En 1 fois
            </label>
            <label>
              <input
                type="radio"
                name="nb-echeances"
                checked={valeurs.paiementNbEcheances === 3}
                onChange={() => setValeurs((v) => ({ ...v, paiementNbEcheances: 3 }))}
              />
              En 3 fois (1 chèque par trimestre)
            </label>
            <p className="champ__aide">
              Un chèque de 40 € à l'ordre de Contretemps à l'inscription, puis le solde{' '}
              {valeurs.paiementNbEcheances === 3 ? (
                <>
                  en 3 chèques, encaissés en{' '}
                  {moisEncaissementsAVenir(saisonActuelle()).join(', ') || 'ce mois-ci'}.
                </>
              ) : (
                "en 1 chèque, remis avec celui de l'adhésion."
              )}
            </p>
          </div>
        )}

        {valeurs.moyenPaiement === 'helloasso' && (
          <div className="sous-cases" style={{ marginTop: 10 }}>
            <label>
              <input
                type="radio"
                name="nb-echeances"
                checked={valeurs.paiementNbEcheances === 1}
                onChange={() => setValeurs((v) => ({ ...v, paiementNbEcheances: 1 }))}
              />
              En 1 fois
            </label>
            <label>
              <input
                type="radio"
                name="nb-echeances"
                checked={valeurs.paiementNbEcheances === 3}
                onChange={() => setValeurs((v) => ({ ...v, paiementNbEcheances: 3 }))}
              />
              En 3 fois (1 fois par trimestre)
            </label>
          </div>
        )}
      </section>

      <button className="bouton" type="submit" disabled={envoiEnCours}>
        {envoiEnCours && <span className="spinner" aria-hidden="true" />}
        {envoiEnCours ? 'Envoi en cours…' : "Valider l'inscription"}
      </button>
      {envoiEnCours && (
        <p className="envoi-note">
          Enregistrement, génération des PDF et envoi de l'email de confirmation — ça peut prendre
          quelques secondes.
        </p>
      )}
    </form>
  )
}
