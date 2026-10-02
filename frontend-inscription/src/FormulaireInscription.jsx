import { useMemo, useState } from 'react'
import {
  creerInscription,
  enregistrerEleveDepuisFiche,
  supprimerFiche,
  uploaderPhotoEleve,
} from './api/backend.js'
import { formaterCout } from './cout.js'
import { COURS_PUBLICS } from './coursPublics.js'
import { calculerTarifIndicatif, LIBELLE_PALIER } from './tarifs.js'

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
  reductionFamilleDemandee: false,
}

// Champ du formulaire -> champ lu sur une fiche papier (voir
// backend/src/inscriptions/lecture_fiche.py:FicheLue).
const CHAMP_FICHE = {
  eleveNom: 'eleve_nom',
  elevePrenom: 'eleve_prenom',
  eleveDateNaissance: 'eleve_date_naissance',
  eleveAdresse: 'eleve_adresse',
  eleveTelephone: 'eleve_telephone',
  eleveEmail: 'eleve_email',
  contactNom: 'contact_urgence_nom',
  contactPrenom: 'contact_urgence_prenom',
  contactLien: 'contact_urgence_lien',
  contactTelephone: 'contact_urgence_telephone',
  coursIds: 'cours_ids',
  allergies: 'allergies',
  traitementMedical: 'traitement_medical',
  informationsImportantes: 'informations_importantes',
  droitImageAutorise: 'droit_image_autorise',
  droitImageSite: 'droit_image_site',
  droitImageReseaux: 'droit_image_reseaux',
  droitImageAffiches: 'droit_image_affiches',
  reglementLuApprouve: 'reglement_signe',
  signataireNom: 'signataire_nom',
}

// Valeurs de départ : vides pour une famille, lues sur la fiche papier
// pour un admin. Un cours lu mais absent du formulaire (voir
// coursPublics.js) est écarté : il compterait dans le tarif sans pouvoir
// être décoché.
function valeursDeDepart(fiche, cours) {
  if (!fiche) return VIDE
  const proposes = new Set(COURS_PUBLICS.map((cp) => cp.coursNom))
  const idsProposes = new Set(cours.filter((c) => proposes.has(c.nom)).map((c) => c.id))
  const valeurs = { ...VIDE }
  for (const [nom, champFiche] of Object.entries(CHAMP_FICHE)) {
    const lu = fiche.donnees[champFiche]
    if (lu != null) valeurs[nom] = lu
  }
  valeurs.coursIds = (fiche.donnees.cours_ids ?? []).filter((id) => idsProposes.has(id))
  return valeurs
}

// `fiche` : brouillon d'une fiche papier lue automatiquement (voir
// App.jsx) — le formulaire est alors rempli par un admin, qui corrige la
// lecture. Les champs incertains sont signalés jusqu'à ce qu'il y touche.
export default function FormulaireInscription({
  ecole,
  cours,
  fiche = null,
  onAnnuler,
  onEleveEnregistre,
  onSoumis,
}) {
  const [valeurs, setValeurs] = useState(() => valeursDeDepart(fiche, cours))
  const [douteux, setDouteux] = useState(() => new Set(fiche?.champsDouteux ?? []))
  const [elevePhoto, setElevePhoto] = useState(null)
  const [apercuPhoto, setApercuPhoto] = useState(null)
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const [erreur, setErreur] = useState(null)
  // Fiche papier : un élève du même nom existe déjà, à confirmer.
  const [homonyme, setHomonyme] = useState(false)

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
  // Résout chaque entrée de COURS_PUBLICS (libellé "grand public") vers
  // le vrai cours (et son horaire réel, voir cours.js) — une entrée dont
  // le nom ne correspond à aucun cours réel (renommé/supprimé côté
  // Admin) est silencieusement ignorée, jamais une case cassée. Plusieurs
  // entrées peuvent pointer vers le même cours réel (ex. "Éveil +
  // Classique Initiation" et "Classique Initiation", voir
  // coursPublics.js) — cocher l'une coche alors aussi l'autre, c'est
  // voulu (même cours réel, juste 2 façons de le retrouver).
  const coursAffiches = useMemo(() => {
    const parNom = new Map(cours.map((c) => [c.nom, c]))
    return COURS_PUBLICS.map((cp) => {
      const reel = parNom.get(cp.coursNom)
      if (!reel) return null
      // Créneaux en plus, rares (voir cours/models.py:Cours.horaires_
      // supplementaires — ex. "Éveil" proposé aussi un autre jour) :
      // affichés à la suite, séparés par "ou".
      const horaires = [
        reel.jour && `${reel.jour} ${reel.heure_debut}-${reel.heure_fin}`,
        ...(reel.horaires_supplementaires ?? []).map(
          (h) => `${h.jour} ${h.heure_debut}-${h.heure_fin}`
        ),
      ].filter(Boolean)
      return { libelle: cp.libelle, id: reel.id, horaire: horaires.join(' ou ') }
    }).filter(Boolean)
  }, [cours])
  const tarif = useMemo(
    () => calculerTarifIndicatif(nomsCoursChoisis, valeurs.reductionFamilleDemandee),
    [nomsCoursChoisis, valeurs.reductionFamilleDemandee]
  )

  // Un champ que l'admin a repris n'est plus « à vérifier ».
  function verifie(nom) {
    const champFiche = CHAMP_FICHE[nom]
    setDouteux((d) => {
      if (!d.has(champFiche)) return d
      const suivant = new Set(d)
      suivant.delete(champFiche)
      return suivant
    })
  }

  function aVerifier(...noms) {
    return noms.some((nom) => douteux.has(CHAMP_FICHE[nom]))
  }

  function classeChamp(nom) {
    return aVerifier(nom) ? 'champ champ--douteux' : 'champ'
  }

  function champ(nom) {
    return {
      value: valeurs[nom],
      onChange: (e) => {
        verifie(nom)
        setValeurs((v) => ({ ...v, [nom]: e.target.value }))
      },
    }
  }

  function basculerCoche(nom) {
    verifie(nom)
    setValeurs((v) => ({ ...v, [nom]: !v[nom] }))
  }

  async function annuler() {
    setEnvoiEnCours(true)
    await supprimerFiche(fiche.jeton).catch(() => {})
    onAnnuler()
  }

  function basculerCours(id) {
    verifie('coursIds')
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
    if (!fiche && !valeurs.eleveEmail.trim()) {
      return "L'email est obligatoire (il sert à recevoir la confirmation et, si choisi, à payer par carte bancaire)."
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
      const donnees = {
        eleve_nom: valeurs.eleveNom.trim(),
        eleve_prenom: valeurs.elevePrenom.trim(),
        eleve_date_naissance: valeurs.eleveDateNaissance,
        eleve_adresse: valeurs.eleveAdresse || null,
        eleve_telephone: valeurs.eleveTelephone || null,
        eleve_email: valeurs.eleveEmail.trim() || null,
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
        // Pas de moyen_paiement ici : c'est l'étape 2 (voir
        // PaiementEtape.jsx) qui le fixe, une fois les informations
        // validées (voir spec/SPEC-inscription.md).
        reduction_famille_demandee: valeurs.reductionFamilleDemandee,
      }
      // Fiche papier : l'élève entre directement dans la liste officielle
      // de l'école, sans étape de paiement (décision du 2026-10-02).
      if (fiche) {
        onEleveEnregistre(await enregistrerEleveDepuisFiche(fiche.jeton, donnees, homonyme))
        return
      }
      const resultat = await creerInscription(ecole.id, donnees)

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
      setHomonyme(Boolean(err.homonyme))
      setErreur(err.message || "L'inscription n'a pas pu être envoyée. Réessayez.")
    } finally {
      setEnvoiEnCours(false)
    }
  }

  return (
    <form onSubmit={soumettre}>
      {erreur && <p className="erreur-globale">{erreur}</p>}

      {fiche && (
        <section className="section fiche-lue">
          <h2>Fiche papier lue automatiquement</h2>
          <p>
            Vérifiez chaque champ en le comparant à la fiche. Les champs{' '}
            <span className="fiche-lue__marque">surlignés</span> sont ceux dont la lecture est
            incertaine.
          </p>
          {fiche.remarques && <p className="alerte">{fiche.remarques}</p>}
          <p>
            Coût de la lecture : <strong>{formaterCout(fiche.coutUsd)}</strong>
          </p>
          <details>
            <summary>Voir la fiche ({fiche.pages.length} page{fiche.pages.length > 1 ? 's' : ''})</summary>
            <div className="fiche-lue__pages">
              {fiche.pages.map((page, i) => (
                <a key={page.url} href={page.url} target="_blank" rel="noopener">
                  {page.type.startsWith('image/') ? (
                    <img src={page.url} alt={`Page ${i + 1} de la fiche`} />
                  ) : (
                    `Page ${i + 1} (PDF)`
                  )}
                </a>
              ))}
            </div>
          </details>
        </section>
      )}

      <section className="section">
        <h2>Élève</h2>
        <div className="grille-2">
          <div className={classeChamp('eleveNom')}>
            <label htmlFor="eleve-nom">Nom *</label>
            <input id="eleve-nom" required placeholder="Dupont" {...champ('eleveNom')} />
          </div>
          <div className={classeChamp('elevePrenom')}>
            <label htmlFor="eleve-prenom">Prénom *</label>
            <input id="eleve-prenom" required placeholder="Julie" {...champ('elevePrenom')} />
          </div>
        </div>
        <div className={classeChamp('eleveDateNaissance')}>
          <label htmlFor="eleve-naissance">Date de naissance *</label>
          <input id="eleve-naissance" type="date" required {...champ('eleveDateNaissance')} />
          {/* Un input date n'affiche jamais son "placeholder" (ignoré par
              tous les navigateurs) — texte d'aide séparé, jamais une
              vraie valeur, donc aucun risque de fausse date oubliée. */}
          <small className="champ__aide">Exemple : 10/05/2015</small>
        </div>
        <div className={classeChamp('eleveAdresse')}>
          <label htmlFor="eleve-adresse">Adresse</label>
          <input
            id="eleve-adresse"
            placeholder="12 rue des Oliviers, 83330 Le Beausset"
            {...champ('eleveAdresse')}
          />
        </div>
        <div className="grille-2">
          <div className={classeChamp('eleveTelephone')}>
            <label htmlFor="eleve-telephone">Téléphone</label>
            <input
              id="eleve-telephone"
              type="tel"
              placeholder="06 12 34 56 78"
              {...champ('eleveTelephone')}
            />
          </div>
          <div className={classeChamp('eleveEmail')}>
            <label htmlFor="eleve-email">Email{fiche ? '' : ' *'}</label>
            <input
              id="eleve-email"
              type="email"
              required={!fiche}
              placeholder="julie.dupont@email.fr"
              {...champ('eleveEmail')}
            />
          </div>
        </div>
        {!fiche && <div className="champ">
          <label htmlFor="eleve-photo">Photo de l'élève</label>
          <input id="eleve-photo" type="file" accept="image/*" onChange={choisirPhoto} />
          {apercuPhoto && (
            <img src={apercuPhoto} alt="Aperçu de la photo de l'élève" className="photo-apercu" />
          )}
        </div>}
      </section>

      <section className="section">
        <h2>Contact d'urgence</h2>
        <div className="grille-2">
          <div className={classeChamp('contactNom')}>
            <label htmlFor="contact-nom">Nom</label>
            <input id="contact-nom" placeholder="Dupont" {...champ('contactNom')} />
          </div>
          <div className={classeChamp('contactPrenom')}>
            <label htmlFor="contact-prenom">Prénom</label>
            <input id="contact-prenom" placeholder="Marie" {...champ('contactPrenom')} />
          </div>
        </div>
        <div className="grille-2">
          <div className={classeChamp('contactLien')}>
            <label htmlFor="contact-lien">Lien avec l'élève</label>
            <input id="contact-lien" placeholder="Père, mère, tuteur…" {...champ('contactLien')} />
          </div>
          <div className={classeChamp('contactTelephone')}>
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
        <h2>
          Cours souhaités *
          {aVerifier('coursIds') && <span className="a-verifier">à vérifier</span>}
        </h2>
        <div className="cours-grille">
          {coursAffiches.map((c) => (
            <label
              key={c.libelle}
              className={`case ${valeurs.coursIds.includes(c.id) ? 'case--coche' : ''}`}
            >
              <input
                type="checkbox"
                checked={valeurs.coursIds.includes(c.id)}
                onChange={() => basculerCours(c.id)}
              />
              <span>
                {c.libelle}
                {c.horaire && (
                  <>
                    <br />
                    <small>{c.horaire}</small>
                  </>
                )}
              </span>
            </label>
          ))}
        </div>
        <p className="compteur-cours">
          Nombre de cours/semaine :{' '}
          <strong>{valeurs.coursIds.length}</strong>
          {' '}— le tarif dépend de ce nombre (voir ci-dessous).
        </p>
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
        <div className={classeChamp('allergies')}>
          <label htmlFor="allergies">Allergies</label>
          <textarea id="allergies" rows={2} placeholder="Aucune" {...champ('allergies')} />
        </div>
        <div className={classeChamp('traitementMedical')}>
          <label htmlFor="traitement">Traitement médical</label>
          <textarea id="traitement" rows={2} placeholder="Aucun" {...champ('traitementMedical')} />
        </div>
        <div className={classeChamp('informationsImportantes')}>
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
        <h2>
          Droit à l'image
          {aVerifier('droitImageAutorise', 'droitImageSite', 'droitImageReseaux', 'droitImageAffiches') && <span className="a-verifier">à vérifier</span>}
        </h2>
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
        <h2>
          Règlement intérieur *
          {aVerifier('reglementLuApprouve') && <span className="a-verifier">à vérifier</span>}
        </h2>
        <label className="checkbox-ligne">
          <input
            type="checkbox"
            required
            checked={valeurs.reglementLuApprouve}
            onChange={() => basculerCoche('reglementLuApprouve')}
          />
          <span>J'ai lu et j'approuve le règlement intérieur de l'école.</span>
        </label>
        <div className={classeChamp('signataireNom')} style={{ marginTop: 10 }}>
          <label htmlFor="signataire">Nom du signataire (responsable légal, ou l'élève si majeur) *</label>
          <input id="signataire" required placeholder="Marie Dupont" {...champ('signataireNom')} />
        </div>
      </section>

      <button
        className="bouton"
        type="submit"
        disabled={envoiEnCours || valeurs.coursIds.length === 0}
      >
        {envoiEnCours && <span className="spinner" aria-hidden="true" />}
        {envoiEnCours
          ? 'Validation en cours…'
          : !fiche
            ? 'Valider et continuer vers le paiement'
            : homonyme
              ? "Enregistrer quand même l'élève"
              : "Enregistrer l'élève"}
      </button>
      {fiche && (
        <button className="bouton bouton--secondaire" type="button" disabled={envoiEnCours} onClick={annuler}>
          Annuler
        </button>
      )}
      {!envoiEnCours && valeurs.coursIds.length === 0 && (
        <p className="envoi-note">Choisissez au moins un cours pour continuer.</p>
      )}
      {envoiEnCours && !fiche && (
        <p className="envoi-note">
          Enregistrement des informations — l'étape suivante propose le choix du paiement.
        </p>
      )}
    </form>
  )
}
